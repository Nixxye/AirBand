#include "WifiServer.hpp"
#include <esp_wifi.h>

WifiServer* WifiServer::instance = nullptr;

volatile int16_t WifiServer::rx_ax = 0;
volatile int16_t WifiServer::rx_ay = 0;
volatile int16_t WifiServer::rx_az = 0;
volatile int16_t WifiServer::rx_gx = 0;
volatile int16_t WifiServer::rx_gy = 0;
volatile int16_t WifiServer::rx_gz = 0;

// Callback: Roda quando chega dado da Escrava
void WifiServer::OnDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
    slave_msg_t msg;
    
    if (len == sizeof(msg)) {
        memcpy(&msg, incomingData, sizeof(msg));
        
        // --- Salva Aceleração nas variáveis voláteis ---
        rx_ax = msg.ax;
        rx_ay = msg.ay;
        rx_az = msg.az;
        
        // Salva Giroscópio
        rx_gx = msg.gx;
        rx_gy = msg.gy;
        rx_gz = msg.gz;
    }
}

WifiServer::WifiServer(const char* ssid, const char* password) 
    : ap_ssid(ssid), ap_password(password), lastSendTime(0) 
{
    pcIP = IPAddress(192, 168, 4, 2);
    
    gyro = Gyroscope::Init_Gyroscope();
    mag = Magnetometer::Init_Magnetometer();
    adcReader = AnalogReader::Init_AnalogReader();

    // Configura Wi-Fi AP no Canal Específico
    WiFi.mode(WIFI_AP_STA);
    WiFi.setSleep(false);
    
    WiFi.softAP(ap_ssid, ap_password, WIFI_CHANNEL); 

    Serial.print("MAC Address da Mestra: ");
    Serial.println(WiFi.macAddress());

    // Inicia ESP-NOW
    if (esp_now_init() != ESP_OK) {
        Serial.println("Erro ESP-NOW");
    }
    esp_now_register_recv_cb(OnDataRecv);

    udp.begin(UDP_PORT);
}

WifiServer* WifiServer::Init_WifiServer(const char* ssid, const char* password) {
    if (instance == nullptr) instance = new WifiServer(ssid, password);
    return instance;
}

void WifiServer::sendDataToClient() {
    unsigned long now = millis();
    if (now - lastSendTime >= 10) { // 10ms = 100Hz
        lastSendTime = now;

        if (WiFi.softAPgetStationNum() > 0) {
            SensorPacket packet;

            // --- Sensores Locais (Mestra) ---
            int16_t temp;
            gyro->getData(&packet.ax, &packet.ay, &packet.az, &temp, &packet.gx, &packet.gy, &packet.gz);
            
            String trash;
            mag->getData((int*)&packet.mx, (int*)&packet.my, (int*)&packet.mz, &packet.heading, trash);
            adcReader->getData(&packet.v32, &packet.v33, &packet.v34, &packet.v35);

            // --- Sensores Remotos (Escrava) ---
            // Preenche Aceleração Escrava no pacote UDP
            packet.slave_ax = rx_ax;
            packet.slave_ay = rx_ay;
            packet.slave_az = rx_az;
            
            // Preenche Giroscópio Escrava
            packet.slave_gx = rx_gx;
            packet.slave_gy = rx_gy;
            packet.slave_gz = rx_gz;

            packet.timestamp = now;

            udp.beginPacket(pcIP, UDP_PORT);
            udp.write((const uint8_t*)&packet, sizeof(SensorPacket));
            udp.endPacket();
        }
    }
}

void WifiServer::loop() {
    sendDataToClient();
}