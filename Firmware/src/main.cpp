#include <Arduino.h>
#include "Gyroscope.hpp"
#include "Magnetometer.hpp"
#include "ISR.hpp"

Gyroscope* gyro;
Magnetometer* mag;

void setup() {
    Serial.begin(115200);
    Serial.println("| MAIN | ---------- Iniciando setup --------");

    gyro = Gyroscope::Init_Gyroscope(); 
    mag = Magnetometer::Init_Magnetometer();

    // Init_ISR();
    vTaskDelay(10);
}

void loop() {
    gyro->loop();
    mag->loop();

    vTaskDelay(1);
}