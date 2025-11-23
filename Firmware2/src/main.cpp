#include <Arduino.h>
#include <esp_now.h>
#include <WiFi.h>
#include <Wire.h>
#include <esp_wifi.h> // <--- NECESSÁRIO para mudar o canal
#include "Gyroscope.hpp"

// --- CONFIGURAÇÃO ---
// MAC Address da Mestra (Modo AP = MAC Base + 1)
// Base: 6C:C8:40:8B:40:D0 -> AP: ...D1
uint8_t broadcastAddress[] = {0x6C, 0xC8, 0x40, 0x8B, 0x40, 0xD1}; 

#define WIFI_CHANNEL 1

// Estrutura de envio (Deve dar match com a estrutura de recepção na Mestra)
typedef struct struct_message {
  int16_t gx;
  int16_t gy;
  int16_t gz;
} struct_message;

struct_message myData;
esp_now_peer_info_t peerInfo;
Gyroscope* gyro;

// Callback de confirmação de envio
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  // Opcional: Descomente para debug, mas pode poluir o serial em alta velocidade
  // Serial.print("Status: ");
  // Serial.println(status == ESP_NOW_SEND_SUCCESS ? "OK" : "FALHA");
}

void setup() {
  Serial.begin(115200);
  
  // 1. Inicializa Sensor (Sua implementação Singleton)
  gyro = Gyroscope::Init_Gyroscope();

  // 2. Configura Wi-Fi em modo Station
  WiFi.mode(WIFI_STA);
  
  // 3. Força o canal para coincidir com a Mestra (Canal 1)
  // Isso resolve o problema de as placas não se encontrarem
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);

  // 4. Inicia ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Erro ao iniciar ESP-NOW");
    return;
  }
  esp_now_register_send_cb(OnDataSent);

  // 5. Registra a Mestra como par
  memcpy(peerInfo.peer_addr, broadcastAddress, 6);
  peerInfo.channel = WIFI_CHANNEL;  
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    Serial.println("Falha ao adicionar par (Verifique o MAC)");
    return;
  }
  
  Serial.println("Slave Iniciado! Enviando dados...");
}

void loop() {
  // 1. ATUALIZA O SENSOR (CRÍTICO!)
  // Na sua classe Gyroscope, a leitura I2C acontece dentro de loop() -> readData()
  gyro->loop(); 

  // 2. Coleta os dados atualizados das variáveis internas da classe
  int16_t ax, ay, az, temp;
  gyro->getData(&ax, &ay, &az, &temp, &myData.gx, &myData.gy, &myData.gz);

  // 3. Envia via ESP-NOW
  esp_err_t result = esp_now_send(broadcastAddress, (uint8_t *) &myData, sizeof(myData));
  
  // Debug de erro grave apenas
  if (result != ESP_OK) {
    // Serial.println("Erro de envio ESP-NOW");
  }
  
  // 4. Taxa de atualização (10ms = 100Hz)
  delay(10);
}