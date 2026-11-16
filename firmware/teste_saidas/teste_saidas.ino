/*
 * Trabalho Final - Database Of Things - 270400
 * Alan Brum - 92305
 *
 * Teste das saidas: LED verde, LED vermelho e buzzer.
 * Nao faz parte do projeto final, serve so para conferir a montagem.
 *
 * Ligacoes:
 *   LED verde    : GPIO27 -> 330R -> perna longa do LED, perna curta -> GND
 *   LED vermelho : GPIO14 -> 330R -> perna longa do LED, perna curta -> GND
 *   Buzzer       : GPIO32 -> buzzer -> GND
 *
 * Abrir o Serial Monitor em 115200 para acompanhar.
 */

const int PINO_LED_VERDE    = 27;
const int PINO_LED_VERMELHO = 14;
const int PINO_BUZZER       = 32;

void bip(int frequencia, int duracaoMs) {
  long periodo = 1000000L / frequencia;
  long ciclos  = (long)duracaoMs * 1000L / periodo;
  for (long i = 0; i < ciclos; i++) {
    digitalWrite(PINO_BUZZER, HIGH);
    delayMicroseconds(periodo / 2);
    digitalWrite(PINO_BUZZER, LOW);
    delayMicroseconds(periodo / 2);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PINO_LED_VERDE, OUTPUT);
  pinMode(PINO_LED_VERMELHO, OUTPUT);
  pinMode(PINO_BUZZER, OUTPUT);
  Serial.println();
  Serial.println("Teste das saidas iniciado.");
}

void loop() {
  Serial.println("1) LED VERDE aceso por 2 segundos");
  digitalWrite(PINO_LED_VERDE, HIGH);
  delay(2000);
  digitalWrite(PINO_LED_VERDE, LOW);
  delay(500);

  Serial.println("2) LED VERMELHO aceso por 2 segundos");
  digitalWrite(PINO_LED_VERMELHO, HIGH);
  delay(2000);
  digitalWrite(PINO_LED_VERMELHO, LOW);
  delay(500);

  Serial.println("3) BUZZER: bip agudo e bip grave");
  bip(1600, 300);
  delay(200);
  bip(300, 400);
  delay(500);

  Serial.println("4) os dois LEDs juntos, piscando 3 vezes");
  for (int i = 0; i < 3; i++) {
    digitalWrite(PINO_LED_VERDE, HIGH);
    digitalWrite(PINO_LED_VERMELHO, HIGH);
    delay(300);
    digitalWrite(PINO_LED_VERDE, LOW);
    digitalWrite(PINO_LED_VERMELHO, LOW);
    delay(300);
  }

  Serial.println("--- fim do ciclo, repetindo em 2 segundos ---");
  Serial.println();
  delay(2000);
}
