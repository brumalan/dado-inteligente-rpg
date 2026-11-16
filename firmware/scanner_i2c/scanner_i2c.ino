/*
 * Trabalho Final - Database Of Things - 270400
 * Alan Brum - 92305
 *
 * Scanner I2C: descobre o endereco do display LCD.
 * Nao faz parte do projeto final, serve so para diagnostico.
 *
 * Ligacoes: SDA -> GPIO21, SCL -> GPIO22
 * Abrir o Serial Monitor em 115200.
 */

#include <Wire.h>

void setup() {
  Serial.begin(115200);
  delay(1000);
  Wire.begin(21, 22);
  Serial.println();
  Serial.println("Scanner I2C iniciado.");
}

void loop() {
  int encontrados = 0;

  Serial.println("Procurando dispositivos I2C...");

  for (byte endereco = 1; endereco < 127; endereco++) {
    Wire.beginTransmission(endereco);
    byte erro = Wire.endTransmission();

    if (erro == 0) {
      Serial.print("  ENCONTRADO no endereco 0x");
      if (endereco < 16) {
        Serial.print("0");
      }
      Serial.println(endereco, HEX);
      encontrados++;
    }
  }

  if (encontrados == 0) {
    Serial.println("  Nenhum dispositivo encontrado. Confira os 4 fios do display.");
  }

  Serial.println();
  delay(3000);
}
