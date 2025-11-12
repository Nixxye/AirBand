#include <Arduino.h>
#include "Gyroscope.hpp"
#include "Magnetometer.hpp"
#include "AnalogReader.hpp"
#include "WifiServer.hpp"
#include "ISR.hpp"

Gyroscope* gyro;
Magnetometer* mag;
AnalogReader* adcReader;
WifiServer* wifi;

#define WIFI_SSID "ALuvaQueTePariu"
#define WIFI_PASSWORD "teste1234"

void setup() {
    Serial.begin(115200);
    Serial.println("| MAIN | ---------- Iniciando setup --------");

    gyro = Gyroscope::Init_Gyroscope(); 
    mag = Magnetometer::Init_Magnetometer();
    adcReader = AnalogReader::Init_AnalogReader();
    wifi = WifiServer::Init_WifiServer(WIFI_SSID, WIFI_PASSWORD);

    // Init_ISR();
    vTaskDelay(10);
}

void loop() {
    gyro->loop();
    // mag->loop();
    adcReader->loop();
    wifi->loop();

    vTaskDelay(1);
}