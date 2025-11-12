#include "../include/WifiServer.hpp"

// Define a porta do servidor
#define TCP_PORT 8888

WifiServer* WifiServer::instance = nullptr;

// Construtor: Inicia o Wi-Fi e o Servidor
WifiServer::WifiServer(const char* ssid, const char* password) 
    : ap_ssid(ssid), ap_password(password), lastSendTime(0) 
{
    Serial.println("|WifiServer| ------- Iniciando Servidor Wi-Fi ---------");

    // Obtém as instâncias dos sensores (assume que já foram inicializados)
    gyro = Gyroscope::Init_Gyroscope();
    mag = Magnetometer::Init_Magnetometer();
    adcReader = AnalogReader::Init_AnalogReader();
    
    // Inicia o servidor TCP na porta definida
    server = new WiFiServer(TCP_PORT); 

    // Inicia o Access Point
    Serial.print("|WifiServer| Abrindo Access Point: ");
    Serial.println(ap_ssid);
    
    // Configura e inicia o AP
    WiFi.softAP(ap_ssid, ap_password);
    
    IPAddress myIP = WiFi.softAPIP();
    Serial.print("|WifiServer| IP do Servidor (AP): ");
    Serial.println(myIP); // O IP padrão é 192.168.4.1
    
    server->begin();
    Serial.print("|WifiServer| Servidor TCP iniciado na porta ");
    Serial.println(TCP_PORT);
    Serial.println("|WifiServer| Conecte-se a esta rede e acesse 192.168.4.1");
}

WifiServer::~WifiServer() {
    delete server;
}

// Método Singleton Init
WifiServer* WifiServer::Init_WifiServer(const char* ssid, const char* password) {
    if (instance == nullptr) {
        instance = new WifiServer(ssid, password);
    }
    return instance;
}

/**
 * @brief Verifica se um novo cliente (PC) se conectou.
 */
void WifiServer::handleNewClient() {
    // Verifica se há um novo cliente
    if (server->hasClient()) {
        // Se já tínhamos um cliente, desconecta ele primeiro
        if (client && client.connected()) {
            client.stop();
            Serial.println("|WifiServer| Cliente antigo desconectado.");
        }
        
        // Aceita a nova conexão
        client = server->available();
        Serial.println("|WifiServer| Novo cliente conectado!");
    }
}

/**
 * @brief Envia os dados de todos os sensores para o cliente conectado.
 */
void WifiServer::sendDataToClient() {
    // Se o cliente estiver conectado
    if (client && client.connected()) {
        
        // E se o tempo de intervalo (100ms) já passou
        unsigned long now = millis();
        if (now - lastSendTime >= sendInterval) {
            lastSendTime = now;
            
            // 1. Coletar dados do Giroscópio
            int16_t ax_raw, ay_raw, az_raw, tmp_raw, gx_raw, gy_raw, gz_raw;
            gyro->getData(&ax_raw, &ay_raw, &az_raw, &tmp_raw, &gx_raw, &gy_raw, &gz_raw);
            
            // 2. Coletar dados do Magnetômetro
            int mx_raw, my_raw, mz_raw;
            float heading;
            String bearing;
            mag->getData(&mx_raw, &my_raw, &mz_raw, &heading, bearing);

            // 3. Coletar dados do ADC
            float v32, v33, v34, v35;
            adcReader->getData(&v32, &v33, &v34, &v35);

            // 4. Montar a string JSON
            String json = "{";
            
            // Dados do Giroscópio (convertendo de volta para float)
            json += "\"gyro\":{";
            json += "\"ax\":"; json += (ax_raw / 100.0);
            json += ",\"ay\":"; json += (ay_raw / 100.0);
            json += ",\"az\":"; json += (az_raw / 100.0);
            json += ",\"gx\":"; json += (gx_raw / 100.0);
            json += ",\"gy\":"; json += (gy_raw / 100.0);
            json += ",\"gz\":"; json += (gz_raw / 100.0);
            json += "},"; // <-- **AJUSTE: Adicionada vírgula**
            
            // Dados do Magnetômetro
            json += "\"mag\":{";
            json += "\"mx\":"; json += mx_raw;
            json += ",\"my\":"; json += my_raw;
            json += ",\"mz\":"; json += mz_raw;
            json += ",\"heading\":"; json += heading;
            json += ",\"bearing\":\""; json += bearing; json += "\"";
            json += "},"; // <-- **AJUSTE: Adicionada vírgula**
            
            // Dados do ADC
            json += "\"adc\":{";
            json += "\"v32\":"; json += v32;
            json += ",\"v33\":"; json += v33;
            json += ",\"v34\":"; json += v34;
            json += ",\"v35\":"; json += v35;
            json += "}";
            
            json += "}\n"; // O '\n' (newline) é importante

            // 5. Enviar para o cliente
            client.print(json);
        }
    }
}

/**
 * @brief Loop principal da classe.
 */
void WifiServer::loop() {
    handleNewClient();  // Verifica se um novo PC se conectou
    sendDataToClient(); // Envia dados para o PC conectado (se houver)
}