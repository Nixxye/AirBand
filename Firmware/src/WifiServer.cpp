#include "WifiServer.hpp"

WifiServer* WifiServer::instance = nullptr;

WifiServer::WifiServer(const char* ssid, const char* password) 
    : ap_ssid(ssid), ap_password(password), lastSendTime(0) 
{
    // Define o IP padrão do PC conectado ao SoftAP do ESP32
    // O ESP é 192.168.4.1, o primeiro cliente recebe 192.168.4.2
    pcIP = IPAddress(192.168, 4, 2); 

    Serial.println("|WifiServer| ------- Iniciando UDP Turbo ---------");

    // Inicializa Sensores
    gyro = Gyroscope::Init_Gyroscope();
    mag = Magnetometer::Init_Magnetometer();
    adcReader = AnalogReader::Init_AnalogReader();

    // 1. Configura Wi-Fi AP
    WiFi.mode(WIFI_AP);
    
    // 2. CRUCIAL: Desativa Power Save (Salva ~100ms de latência)
    WiFi.setSleep(false); 
    
    WiFi.softAP(ap_ssid, ap_password);
    
    Serial.print("|WifiServer| AP Iniciado. IP: ");
    Serial.println(WiFi.softAPIP());

    // 3. Inicia escuta UDP (caso precise receber comandos do PC depois)
    udp.begin(UDP_PORT);
}

WifiServer::~WifiServer() {
    // Destrutor
}

WifiServer* WifiServer::Init_WifiServer(const char* ssid, const char* password) {
    if (instance == nullptr) {
        instance = new WifiServer(ssid, password);
    }
    return instance;
}

void WifiServer::sendDataToClient() {
    unsigned long now = millis();

    // Envio constante (Time-Driven, não Event-Driven)
    if (now - lastSendTime >= SEND_INTERVAL_MS) {
        lastSendTime = now;

        // Verifica se tem alguém conectado no Wi-Fi para não falar sozinho
        if (WiFi.softAPgetStationNum() > 0) {
            
            SensorPacket packet;

            // --- Preenchimento Rápido da Struct ---
            // Variável temporária para temperatura (se não for usar)
            int16_t temp_trash; 
            
            // Giroscópio/Acelerômetro
            gyro->getData(&packet.ax, &packet.ay, &packet.az, &temp_trash, &packet.gx, &packet.gy, &packet.gz);
            
            // Magnetômetro (Convertendo pointers para o tipo correto se necessário)
            String bearing_trash; // Ignoramos strings para performance
            // Assumindo aqui que mx, my, mz são ints
            mag->getData((int*)&packet.mx, (int*)&packet.my, (int*)&packet.mz, &packet.heading, bearing_trash);

            // ADC
            adcReader->getData(&packet.v32, &packet.v33, &packet.v34, &packet.v35);

            // Timestamp (para calcular latência no PC)
            packet.timestamp = now;

            // --- Envio UDP ---
            // beginPacket prepara o cabeçalho
            udp.beginPacket(pcIP, UDP_PORT);
            // write envia os bytes brutos da memória
            udp.write((const uint8_t*)&packet, sizeof(SensorPacket));
            udp.endPacket(); 
        }
    }
}

void WifiServer::loop() {
    sendDataToClient();
}