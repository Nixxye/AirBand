#include <Arduino.h>
#include <Wire.h>
#include "MPU6050.h"

// Pinos I2C customizados
#define I2C_SDA 12 // D12
#define I2C_SCL 13 // D13

MPU6050 mpu;

// Variáveis para armazenar os dados do sensor
int16_t ax, ay, az;
int16_t gx, gy, gz;

void setup() {
    // Inicia a comunicação I2C nos pinos SDA e SCL especificados
    Wire.begin(I2C_SDA, I2C_SCL);

    // Inicia o monitor serial
    Serial.begin(115200);
    Serial.println("Inicializando MPU6050...");

    // Inicializa o MPU6050
    mpu.initialize();

    // Verifica a conexão
    if (mpu.testConnection()) {
        Serial.println("MPU6050 conectado com sucesso!");
    } else {
        Serial.println("Falha na conexão com MPU6050.");
        // Trava a execução se não conseguir conectar
        while (1);
    }
}

void loop() {
    // Lê as medições de aceleração e giroscópio
    mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);

    // Imprime os valores no console
    Serial.print("AcX: "); Serial.print(ax);
    Serial.print(" | AcY: "); Serial.print(ay);
    Serial.print(" | AcZ: "); Serial.print(az);
    Serial.print(" | GyX: "); Serial.print(gx);
    Serial.print(" | GyY: "); Serial.print(gy);
    Serial.print(" | GyZ: "); Serial.println(gz);

    delay(500); // Aguarda meio segundo antes da próxima leitura
}