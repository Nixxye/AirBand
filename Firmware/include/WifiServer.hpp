#ifndef WIFISERVER_HPP
#define WIFISERVER_HPP

#include "Arduino.h"
#include <WiFi.h>
#include <WiFiClient.h>

// Inclui os cabeçalhos das classes de sensores para obter seus dados
#include "../include/Gyroscope.hpp"
#include "../include/Magnetometer.hpp"
#include "../include/AnalogReader.hpp"

class WifiServer {
public:
    /**
     * @brief Obtém a instância Singleton e inicia o Servidor AP.
     * @param ssid O nome da rede Wi-Fi que a ESP32 criará.
     * @param password A senha para essa rede.
     */
    static WifiServer* Init_WifiServer(const char* ssid, const char* password);

    /**
     * @brief Loop principal. Gerencia conexões de clientes e envia dados.
     */
    void loop();

private:
    // Construtor privado (Singleton)
    WifiServer(const char* ssid, const char* password);
    ~WifiServer();

    static WifiServer* instance;

    // Funções internas
    void handleNewClient();
    void sendDataToClient();

    // Objetos do Servidor e Cliente
    WiFiServer* server; // Ponteiro para o servidor TCP
    WiFiClient client;  // O PC cliente conectado

    // Ponteiros para as outras classes (para obter dados)
    Gyroscope* gyro;
    Magnetometer* mag;
    AnalogReader* adcReader;

    // Controle de tempo para envio
    unsigned long lastSendTime;
    const long sendInterval = 100; // Envia dados 10x por segundo (100ms)

    // Credenciais do AP
    const char* ap_ssid;
    const char* ap_password;
};

#endif // WIFISERVER_HPP