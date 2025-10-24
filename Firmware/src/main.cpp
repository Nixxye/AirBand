#include <Arduino.h>
#include "Gyroscope.hpp"
#include "Magnetometer.hpp"
#include "ISR.hpp"

Gyroscope* gyro;
Magnetometer* mag;

void setup() {
    Serial.begin(115200);
    Serial.println("| MAIN | ---------- Iniciando setup --------");

    // É importante iniciar o Gyroscope primeiro,
    // pois ele chama o Wire.begin(PIN_SDA, PIN_SCL)
    gyro = Gyroscope::Init_Gyroscope(); 
    mag = Magnetometer::Init_Magnetometer(); // <-- INICIALIZE O MAGNETÔMETRO

    Init_ISR();
    vTaskDelay(10);
}

void loop() {
    // gyro->loop(); // Roda o loop do giroscópio (baseado em interrupção)
    mag->loop();  // Roda o loop do magnetômetro (baseado em polling/timer)

    vTaskDelay(1);
}