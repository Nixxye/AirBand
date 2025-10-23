#include <Arduino.h>
#include "Gyroscope.hpp"
#include "ISR.hpp"
Gyroscope* gyro;

void setup() {
  Serial.begin(115200);

  Serial.println("| MAIN | ---------- Iniciando setup --------");

  gyro = Gyroscope::Init_Gyroscope();
  Init_ISR();
 
  vTaskDelay(10);
}

void loop() {
  gyro->loop();
    
  vTaskDelay(1);
}