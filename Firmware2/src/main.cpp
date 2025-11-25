#include <Arduino.h>
#include <esp_now.h>
#include <WiFi.h>
#include <Wire.h>
#include <esp_wifi.h>
#include "Gyroscope.hpp"

// --- CONFIGURAÇÃO ---
uint8_t broadcastAddress[] = {0x6C, 0xC8, 0x40, 0x8B, 0x40, 0xD1}; 

#define WIFI_CHANNEL 1

// 1. ATUALIZAÇÃO DA ESTRUTURA
// Agora contém Aceleração (ax, ay, az) + Giroscópio (gx, gy, gz)
typedef struct struct_message {
  int16_t ax; // Adicionado
  int16_t ay; // Adicionado
  int16_t az; // Adicionado
  int16_t gx;
  int16_t gy;
  int16_t gz;
} struct_message;

struct_message myData;
esp_now_peer_info_t peerInfo;
Gyroscope* gyro;

void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  // Debug opcional
}

void setup() {
  Serial.begin(115200);
  
  gyro = Gyroscope::Init_Gyroscope();

  WiFi.mode(WIFI_STA);
  
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);

  if (esp_now_init() != ESP_OK) {
    Serial.println("Erro ao iniciar ESP-NOW");
    return;
  }
  esp_now_register_send_cb(OnDataSent);

  memcpy(peerInfo.peer_addr, broadcastAddress, 6);
  peerInfo.channel = WIFI_CHANNEL;  
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    Serial.println("Falha ao adicionar par");
    return;
  }
  
  Serial.println("Slave Iniciado! Enviando Accel + Gyro...");
}

void loop() {
  gyro->loop(); 

  int16_t temp; // Variável temporária para temperatura (não enviada)
  
  // Passamos os endereços das variáveis da struct diretamente
  gyro->getData(
    &myData.ax, &myData.ay, &myData.az, 
    &temp, 
    &myData.gx, &myData.gy, &myData.gz
  );

  esp_err_t result = esp_now_send(broadcastAddress, (uint8_t *) &myData, sizeof(myData));
  
  delay(10);
}