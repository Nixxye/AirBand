#include <Arduino.h>
#include "Gyroscope.hpp"
#include "Magnetometer.hpp"
#include "AnalogReader.hpp"
#include "ISR.hpp"

Gyroscope* gyro;
Magnetometer* mag;
AnalogReader* adcReader;

void setup() {
    Serial.begin(115200);
    Serial.println("| MAIN | ---------- Iniciando setup --------");

    gyro = Gyroscope::Init_Gyroscope(); 
    mag = Magnetometer::Init_Magnetometer();
    adcReader = AnalogReader::Init_AnalogReader();

    // Init_ISR();
    vTaskDelay(10);
}

void loop() {
    // gyro->loop();
    // mag->loop();
    adcReader->loop();

    vTaskDelay(1);
}