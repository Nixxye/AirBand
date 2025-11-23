#include <esp_now.h>
#include <WiFi.h>
#include <Wire.h>
#include "Gyroscope.hpp"
#include <esp_wifi.h>

// --- CONFIGURAÇÃO ---
// MAC Address da ESP32 MESTRA
uint8_t broadcastAddress[] = {0x6C, 0xC8, 0x40, 0x8B, 0x40, 0xD1}; 
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
  // Serial.print("\r\nStatus do Envio: ");
  // if (status == ESP_NOW_SEND_SUCCESS) {
  //   Serial.println("Entregue com Sucesso! (Mestra confirmou)");
  // } else {
  //   Serial.println("FALHA na entrega (Mestra desligada ou longe?)");
  // }
}

void setup() {
  Serial.begin(115200);
  
  // 1. Inicializa Sensor
  gyro = Gyroscope::Init_Gyroscope();

  // 2. Configura Wi-Fi em modo Station
  WiFi.mode(WIFI_STA);
  
  // TRUQUE: O ESP-NOW exige que o canal seja o mesmo do Receiver (AP da Mestra)
  // No modo STA, o esp tenta escanear. Vamos forçar o canal.
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);

  // 3. Inicia ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Erro ao iniciar ESP-NOW");
    return;
  }
  esp_now_register_send_cb(OnDataSent);

  // 4. Registra a Mestra como par
  memcpy(peerInfo.peer_addr, broadcastAddress, 6);
  peerInfo.channel = WIFI_CHANNEL;  
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    Serial.println("Falha ao adicionar par");
    return;
  }
}

void loop() {
  // Lê dados (Ajuste conforme sua lib Gyroscope)
  int16_t ax, ay, az, temp;
  gyro->getData(&ax, &ay, &az, &temp, &myData.gx, &myData.gy, &myData.gz);

  // Envia via ESP-NOW (Muito rápido < 1ms)
  esp_now_send(broadcastAddress, (uint8_t *) &myData, sizeof(myData));
  
  // Taxa de atualização (100Hz = 10ms)
  delay(10);
}