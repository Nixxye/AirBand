#include "../include/Magnetometer.hpp"

Magnetometer* Magnetometer::instance = nullptr;

Magnetometer::Magnetometer() : magX(0), magY(0), magZ(0), headingDegrees(0), lastReadTime(0)
{
    Serial.println("|Magnetometer| ------- Iniciando QMC5883L (Modo Simples) ---------");
    configQMC5883L_Simple();
}

Magnetometer::~Magnetometer() {}

Magnetometer* Magnetometer::Init_Magnetometer() {
    if (instance == nullptr) {
        // Assume que Gyroscope::Init_Gyroscope() já chamou Wire.begin()
        instance = new Magnetometer();
    }
    return instance;
}

/**
 * @brief Configuração simplificada, usando apenas funções confirmadas.
 */
void Magnetometer::configQMC5883L_Simple() {
    // 1. Define o endereço I2C (0x0D) que o seu scanner encontrou.
    // (Função 'setADDR' é em maiúsculas)
    // compass.setADDR(0x0D); 

    // 2. Inicializa o sensor.
    compass.init();
    
    Serial.println("|Magnetometer| -------- QMC5883L iniciado! ---------");
    // (Não há mais configurações de 'setMode', 'setRate', etc.)
}

/**
 * @brief Lê os dados do sensor e armazena nas variáveis da classe.
 */
void Magnetometer::readData() {
    compass.read();

    magX = compass.getX();
    magY = compass.getY();
    magZ = compass.getZ();
    headingDegrees = compass.getAzimuth(); 

    // Pega o nome da direção (N, NNE, etc.)
    char bearingChars[4]; // 3 caracteres + 1 Nulo de terminação
    compass.getDirection(bearingChars, headingDegrees);
    
    bearingName = String(bearingChars);
}

/**
 * @brief Disponibiliza os dados lidos para outras partes do código.
 */
void Magnetometer::getData(int* mx, int* my, int* mz, float* heading, String &bearing) {
    *mx = magX;
    *my = magY;
    *mz = magZ;
    *heading = headingDegrees; 
    bearing = bearingName;
}

/**
 * @brief Loop principal da classe.
 * Lê os dados e imprime no console a cada 250ms (como no exemplo).
 */
void Magnetometer::loop() {
    unsigned long now = millis();
    
    // Verifica se já passaram 250ms desde a última leitura
    if (now - lastReadTime >= 250) { 
        lastReadTime = now;
        readData(); // Lê os dados

        // Imprime os valores no console
        Serial.print("MagX: "); Serial.print(magX);
        Serial.print(" | MagY: "); Serial.print(magY);
        Serial.print(" | MagZ: "); Serial.print(magZ);
        Serial.print(" | Heading: "); Serial.print(headingDegrees);
        Serial.print(" | Dir: "); Serial.println(bearingName); 
    }
}