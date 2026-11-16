/*
 * Trabalho Final - Database Of Things - 270400
 * Alan Brum - 92305
 *
 * Dado inteligente para RPG de mesa.
 * Placa: ESP32 DevKit V1 (ESP32-WROOM-32, conversor USB CP2102)
 * Display: LCD 16x2 com modulo I2C PCF8574, endereco 0x27
 *
 * Funcionamento:
 *   - BOTAO_DADO percorre os tipos de dado: d4, d6, d8, d10, d12, d20
 *   - BOTAO_ROLAR sorteia o resultado, mostra no LCD e envia para a API
 *   - a API responde se foi acerto ou falha critica
 *   - LED verde + bip agudo   = acerto critico (20 no d20)
 *   - LED vermelho + bip grave = falha critica (1 no d20)
 *
 * Bibliotecas necessarias (Gerenciador de Bibliotecas da IDE Arduino):
 *   - LiquidCrystal I2C (Frank de Brabander)
 *   - ArduinoJson (versao 7)
 *
 * Ligacoes na protoboard:
 *   LCD 16x2 I2C   : GND=trilha -   VCC=trilha +   SDA=GPIO21 (D21)   SCL=GPIO22 (D22)
 *   Botao do dado  : GPIO25 -> botao -> trilha -   (pull-up interno)
 *   Botao de rolar : GPIO26 -> botao -> trilha -   (pull-up interno)
 *   LED verde      : GPIO27 -> 330R -> perna longa do LED, perna curta -> trilha -
 *   LED vermelho   : GPIO14 -> 330R -> perna longa do LED, perna curta -> trilha -
 *   Buzzer         : GPIO32 -> buzzer -> trilha -
 *   Alimentacao    : USB 5V do proprio ESP-32; perifericos em 3V3
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ---------------------------------------------------------------------------
// Configuracao - ajustar antes de gravar
// ---------------------------------------------------------------------------

const char* WIFI_SSID  = "COLOQUE_A_REDE";
const char* WIFI_SENHA = "COLOQUE_A_SENHA";

// Endereco da API. Na nuvem (Render) e https e funciona de qualquer rede
// com internet. Para usar a API rodando num computador da mesma rede,
// troque pelo IP dele, ex.: "http://192.168.0.100:8000".
const char* API_BASE = "https://dado-inteligente-rpg.onrender.com";

// o plano gratuito do Render hiberna a API e ela leva ate ~1 min para
// acordar; por isso o tempo limite das requisicoes e longo
const int TEMPO_LIMITE_HTTP = 20000;   // ms

// codigo deste dado fisico, usado pela API para saber de quem e a rolagem
const char* CODIGO_DISPOSITIVO = "esp32-01";

// ---------------------------------------------------------------------------
// Pinos e display
// ---------------------------------------------------------------------------

const int PINO_BOTAO_DADO   = 25;
const int PINO_BOTAO_ROLAR  = 26;
const int PINO_LED_VERDE    = 27;
const int PINO_LED_VERMELHO = 14;
const int PINO_BUZZER       = 32;

const int PINO_SDA = 21;
const int PINO_SCL = 22;

// endereco confirmado pelo scanner I2C nesta montagem
const int LCD_ENDERECO = 0x27;
const int LCD_COLUNAS  = 16;
const int LCD_LINHAS   = 2;

LiquidCrystal_I2C lcd(LCD_ENDERECO, LCD_COLUNAS, LCD_LINHAS);

// ---------------------------------------------------------------------------
// Estado
// ---------------------------------------------------------------------------

const char* NOMES_DOS_DADOS[] = {"d4", "d6", "d8", "d10", "d12", "d20"};
const int   FACES_DOS_DADOS[] = {  4,    6,    8,   10,    12,    20 };
const int   QUANTIDADE_DE_DADOS = 6;

int    dadoSelecionado  = 5;          // comeca no d20
String nomeDoPersonagem = "";
bool   vinculado = false;

unsigned long ultimoToqueDado  = 0;
unsigned long ultimoToqueRolar = 0;
const unsigned long TEMPO_DEBOUNCE = 250;   // ms

// ---------------------------------------------------------------------------
// Buzzer - onda quadrada feita na mao, funciona em qualquer versao do core
// ---------------------------------------------------------------------------

void bip(int frequencia, int duracaoMs) {
  long periodo = 1000000L / frequencia;        // microssegundos por ciclo
  long ciclos  = (long)duracaoMs * 1000L / periodo;
  for (long i = 0; i < ciclos; i++) {
    digitalWrite(PINO_BUZZER, HIGH);
    delayMicroseconds(periodo / 2);
    digitalWrite(PINO_BUZZER, LOW);
    delayMicroseconds(periodo / 2);
  }
}

void sinalizarAcertoCritico() {
  digitalWrite(PINO_LED_VERDE, HIGH);
  bip(1200, 120);
  bip(1600, 200);
  delay(300);
  digitalWrite(PINO_LED_VERDE, LOW);
}

void sinalizarFalhaCritica() {
  digitalWrite(PINO_LED_VERMELHO, HIGH);
  bip(300, 300);
  bip(200, 400);
  delay(200);
  digitalWrite(PINO_LED_VERMELHO, LOW);
}

// ---------------------------------------------------------------------------
// Tela - o LCD tem so 16 colunas por 2 linhas, entao todo texto e cortado
// ---------------------------------------------------------------------------

String cortar(String texto) {
  if (texto.length() > LCD_COLUNAS) {
    return texto.substring(0, LCD_COLUNAS);
  }
  return texto;
}

void mostrarDuasLinhas(String linha1, String linha2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(cortar(linha1));
  lcd.setCursor(0, 1);
  lcd.print(cortar(linha2));
}

void mostrarTelaPrincipal() {
  String primeira = vinculado ? nomeDoPersonagem : String("SEM VINCULO");
  String segunda  = "Dado: " + String(NOMES_DOS_DADOS[dadoSelecionado]);
  mostrarDuasLinhas(primeira, segunda);
}

void mostrarResultado(int resultado, String critico) {
  String primeira = String(NOMES_DOS_DADOS[dadoSelecionado]) + " = " + String(resultado);

  String segunda;
  if (critico == "acerto") {
    segunda = "ACERTO CRITICO!";
  } else if (critico == "falha") {
    segunda = "FALHA CRITICA!";
  } else if (critico == "enviando") {
    segunda = "enviando...";
  } else {
    segunda = "registrado";
  }

  mostrarDuasLinhas(primeira, segunda);
}

// ---------------------------------------------------------------------------
// Rede
// ---------------------------------------------------------------------------

WiFiClient       clienteSimples;   // para http://
WiFiClientSecure clienteSeguro;    // para https://

/*
 * Abre a requisicao com o cliente certo para o endereco.
 * No https, setInsecure() aceita o certificado sem conferir a cadeia:
 * a conexao fica criptografada, mas o ESP-32 nao valida quem e o servidor.
 */
bool abrirConexao(HTTPClient& http, const String& url) {
  bool ok;
  if (url.startsWith("https")) {
    clienteSeguro.setInsecure();
    ok = http.begin(clienteSeguro, url);
  } else {
    ok = http.begin(clienteSimples, url);
  }
  http.setConnectTimeout(TEMPO_LIMITE_HTTP);
  http.setTimeout(TEMPO_LIMITE_HTTP);
  return ok;
}

void conectarWiFi() {
  mostrarDuasLinhas("Dado inteligente", "Conectando WiFi");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_SENHA);

  int tentativas = 0;
  while (WiFi.status() != WL_CONNECTED && tentativas < 40) {
    delay(500);
    Serial.print(".");
    tentativas++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.print("Wi-Fi conectado. IP: ");
    Serial.println(WiFi.localIP());
    mostrarDuasLinhas("WiFi conectado", WiFi.localIP().toString());
    delay(1500);
  } else {
    Serial.println("\nFalha ao conectar no Wi-Fi.");
    mostrarDuasLinhas("WiFi FALHOU", "confira a rede");
    delay(2000);
  }
}

/*
 * GET /dispositivos/{codigo}/vinculo
 * Descobre a qual personagem e sessao este dado esta servindo.
 */
void consultarVinculo() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  HTTPClient http;
  String url = String(API_BASE) + "/dispositivos/" + CODIGO_DISPOSITIVO + "/vinculo";
  abrirConexao(http, url);
  int codigoHttp = http.GET();

  if (codigoHttp == 200) {
    String corpo = http.getString();
    JsonDocument json;
    DeserializationError erro = deserializeJson(json, corpo);
    if (!erro) {
      vinculado = json["vinculado"] | false;
      nomeDoPersonagem = json["personagem_nome"].isNull()
                           ? String("sem personagem")
                           : String((const char*)json["personagem_nome"]);
      Serial.println("Vinculo: " + nomeDoPersonagem);
    } else {
      Serial.println("JSON do vinculo invalido");
    }
  } else if (codigoHttp == 404) {
    vinculado = false;
    nomeDoPersonagem = "nao cadastrado";
    Serial.println("Dispositivo nao cadastrado na API");
  } else {
    vinculado = false;
    nomeDoPersonagem = "API offline";
    Serial.print("Falha no GET do vinculo: ");
    Serial.println(codigoHttp);
  }

  http.end();
}

/*
 * POST /rolagens
 * Envia a rolagem e devolve o critico calculado pela API
 * ("acerto", "falha" ou string vazia). Em caso de erro, devolve "erro".
 */
String enviarRolagem(int resultado) {
  if (WiFi.status() != WL_CONNECTED) {
    return "erro";
  }

  HTTPClient http;
  String url = String(API_BASE) + "/rolagens";
  abrirConexao(http, url);
  http.addHeader("Content-Type", "application/json");

  JsonDocument corpoJson;
  corpoJson["dispositivo"] = CODIGO_DISPOSITIVO;
  corpoJson["dado"]        = NOMES_DOS_DADOS[dadoSelecionado];
  corpoJson["resultado"]   = resultado;

  String corpo;
  serializeJson(corpoJson, corpo);

  int codigoHttp = http.POST(corpo);
  String critico = "";

  if (codigoHttp == 201) {
    String resposta = http.getString();
    JsonDocument json;
    if (!deserializeJson(json, resposta)) {
      if (!json["rolagem"]["critico"].isNull()) {
        critico = String((const char*)json["rolagem"]["critico"]);
      }
    }
  } else {
    Serial.print("Falha no POST da rolagem: ");
    Serial.println(codigoHttp);
    Serial.println(http.getString());
    critico = "erro";
    // 404 ou 409 significam que o vinculo mudou: vale reconsultar
    if (codigoHttp == 404 || codigoHttp == 409) {
      http.end();
      consultarVinculo();
      return "erro";
    }
  }

  http.end();
  return critico;
}

// ---------------------------------------------------------------------------
// setup e loop
// ---------------------------------------------------------------------------

void setup() {
  Serial.begin(115200);

  pinMode(PINO_BOTAO_DADO, INPUT_PULLUP);
  pinMode(PINO_BOTAO_ROLAR, INPUT_PULLUP);
  pinMode(PINO_LED_VERDE, OUTPUT);
  pinMode(PINO_LED_VERMELHO, OUTPUT);
  pinMode(PINO_BUZZER, OUTPUT);

  digitalWrite(PINO_LED_VERDE, LOW);
  digitalWrite(PINO_LED_VERMELHO, LOW);
  digitalWrite(PINO_BUZZER, LOW);

  Wire.begin(PINO_SDA, PINO_SCL);
  lcd.init();
  lcd.backlight();

  // semente do sorteio: ruido do conversor analogico de um pino solto
  randomSeed(analogRead(33) + millis());

  conectarWiFi();
  consultarVinculo();
  mostrarTelaPrincipal();
}

void loop() {
  // --- botao que troca o tipo de dado ---
  if (digitalRead(PINO_BOTAO_DADO) == LOW &&
      millis() - ultimoToqueDado > TEMPO_DEBOUNCE) {
    ultimoToqueDado = millis();
    dadoSelecionado = (dadoSelecionado + 1) % QUANTIDADE_DE_DADOS;
    bip(900, 40);
    mostrarTelaPrincipal();
  }

  // --- botao que rola o dado ---
  if (digitalRead(PINO_BOTAO_ROLAR) == LOW &&
      millis() - ultimoToqueRolar > TEMPO_DEBOUNCE) {
    ultimoToqueRolar = millis();

    int faces = FACES_DOS_DADOS[dadoSelecionado];
    int resultado = random(1, faces + 1);

    Serial.print("Rolagem: ");
    Serial.print(NOMES_DOS_DADOS[dadoSelecionado]);
    Serial.print(" = ");
    Serial.println(resultado);

    mostrarResultado(resultado, "enviando");
    String critico = enviarRolagem(resultado);

    if (critico == "erro") {
      mostrarDuasLinhas(String(NOMES_DOS_DADOS[dadoSelecionado]) + " = " + String(resultado),
                        "NAO registrado");
      bip(200, 150);
      bip(200, 150);
    } else {
      mostrarResultado(resultado, critico);
      if (critico == "acerto") {
        sinalizarAcertoCritico();
      } else if (critico == "falha") {
        sinalizarFalhaCritica();
      } else {
        bip(1000, 60);
      }
    }

    delay(2000);
    mostrarTelaPrincipal();
  }

  delay(20);
}
