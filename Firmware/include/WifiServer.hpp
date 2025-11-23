#ifndef WIFISERVER_HPP
#define WIFISERVER_HPP

#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_now.h>
#include "Gyroscope.hpp"
#include "Magnetometer.hpp"
#include "AnalogReader.hpp"

#define UDP_PORT 8888
#define WIFI_CHANNEL 1 

// --- ESTRUTURA COMBINADA (Master + Slave) ---
#pragma pack(push, 1)
struct SensorPacket {
    // --- Mestra (Mão Esquerda) ---
    int16_t ax, ay, az;
    int16_t gx, gy, gz;
    int32_t mx, my, mz;
    float heading;
    float v32, v33, v34, v35;
    
    // --- Escrava (Mão Direita - Recebido via ESP-NOW) ---
    int16_t slave_gx, slave_gy, slave_gz; 

    uint32_t timestamp;
};
#pragma pack(pop)

typedef struct slave_msg_t {
  int16_t gx, gy, gz;
} slave_msg_t;

class WifiServer {
private:
    static WifiServer* instance;
    WiFiUDP udp;
    const char* ap_ssid;
    const char* ap_password;
    IPAddress pcIP;
    
    // Sensores Locais
    Gyroscope* gyro;
    Magnetometer* mag;
    AnalogReader* adcReader;

    unsigned long lastSendTime;
    
    // Dados voláteis da Escrava (atualizados na interrupção)
    static volatile int16_t rx_gx, rx_gy, rx_gz;

    WifiServer(const char* ssid, const char* password);

    // Callback estático do ESP-NOW
    static void OnDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len);

public:
    static WifiServer* Init_WifiServer(const char* ssid, const char* password);
    void loop();
    void sendDataToClient();
};

#endif