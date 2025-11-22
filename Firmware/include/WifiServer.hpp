#ifndef WIFISERVER_HPP
#define WIFISERVER_HPP

#include <WiFi.h>
#include <WiFiUdp.h>
#include "Gyroscope.hpp"
#include "Magnetometer.hpp"
#include "AnalogReader.hpp"

// Configuração
#define UDP_PORT 8888
#define SEND_INTERVAL_MS 15

#pragma pack(push, 1)
struct SensorPacket {
    int16_t ax, ay, az;      // Acelerômetro
    int16_t gx, gy, gz;      // Giroscópio
    int32_t mx, my, mz;      // Magnetômetro (int32 para garantir compatibilidade)
    float heading;           // Heading
    float v32, v33, v34, v35;// Leituras ADC
    uint32_t timestamp;      // Tempo do pacote (bom para debug de latência)
};
#pragma pack(pop)
// ----------------------------------

class WifiServer {
private:
    static WifiServer* instance;
    
    // Objetos Wi-Fi
    WiFiUDP udp;
    const char* ap_ssid;
    const char* ap_password;
    
    IPAddress pcIP; 

    // Sensores
    Gyroscope* gyro;
    AnalogReader* adcReader;

    unsigned long lastSendTime;

    // Construtor privado (Singleton)
    WifiServer(const char* ssid, const char* password);

public:
    ~WifiServer();
    static WifiServer* Init_WifiServer(const char* ssid, const char* password);
    
    void loop();
    void sendDataToClient();
};

#endif