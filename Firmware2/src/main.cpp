#include <esp_now.h>
#include <WiFi.h>
#include <Wire.h>
#include "Gyroscope.hpp"

// --- CONFIGURAÇÃO ---
// MAC Address da ESP32 MESTRA
uint8_t broadcastAddress[] = {0x6C, 0xC8, 0x8B, 0x40, 0xD0}; 
#define WIFI_CHANNEL 1

// Estrutura de envio (Apenas dados do Slave)
typedef struct struct_message {
  int16_t gx;
  int16_t gy;
  int16_t gz;
} struct_message;

struct_message myData;
esp_now_peer_info_t peerInfo;
Gyroscope* gyro;

void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  // Opcional: Piscar LED se falhar
}

void setup() {
  Serial.begin(115200);
  
  // Inicializa Sensor
  gyro = Gyroscope::Init_Gyroscope();

  //Configura Wi-Fi em modo Station
  WiFi.mode(WIFI_STA);
  
  // O ESP-NOW exige que o canal seja o mesmo do Receiver (AP da Mestra)
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);

  // Inicia ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Erro ao iniciar ESP-NOW");
    return;
  }
  esp_now_register_send_cb(OnDataSent);

  // Registra a Mestra como par
  memcpy(peerInfo.peer_addr, broadcastAddress, 6);
  peerInfo.channel = WIFI_CHANNEL;  
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    Serial.println("Falha ao adicionar par");
    return;
  }
}

void loop() {
  int16_t ax, ay, az, temp;
  gyro->getData(&ax, &ay, &az, &temp, &myData.gx, &myData.gy, &myData.gz);

  // Envia via ESP-NOW
  esp_now_send(broadcastAddress, (uint8_t *) &myData, sizeof(myData));
  
  // Taxa de atualização (100Hz = 10ms)
  delay(10);
}