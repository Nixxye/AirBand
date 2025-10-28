#include "../include/AnalogReader.hpp"

// Inicializa a instância estática
AnalogReader* AnalogReader::instance = nullptr;

// Construtor: Configura os pinos
AnalogReader::AnalogReader() : voltage32(0), voltage33(0), voltage34(0), voltage35(0), lastReadTime(0)
{
    Serial.println("|AnalogReader| ------- Iniciando Leitor Analógico ---------");
    
    // Configura os pinos 34 e 35 como INPUT (são "input only")
    pinMode(34, INPUT);
    pinMode(35, INPUT);
    // Pinos 32 e 33 podem ser input/output, mas analogRead os configura
    
    Serial.println("|AnalogReader| -------- Pinos ADC (32, 33, 34, 35) prontos! ---------");
}

AnalogReader::~AnalogReader() {
}

// Método Singleton Init
AnalogReader* AnalogReader::Init_AnalogReader() {
    if (instance == nullptr) {
        instance = new AnalogReader();
    }
    return instance;
}

// Função de Leitura
void AnalogReader::readData() {
    // Lê o valor bruto (0-4095) de cada pino
    int raw32 = analogRead(32);
    int raw33 = analogRead(33);
    int raw34 = analogRead(34);
    int raw35 = analogRead(35);

    // Converte o valor bruto para tensão (Volts)
    voltage32 = (raw32 / MAX_ADC_VALUE) * MAX_ADC_VOLTAGE;
    voltage33 = (raw33 / MAX_ADC_VALUE) * MAX_ADC_VOLTAGE;
    voltage34 = (raw34 / MAX_ADC_VALUE) * MAX_ADC_VOLTAGE;
    voltage35 = (raw35 / MAX_ADC_VALUE) * MAX_ADC_VOLTAGE;
}

// Função Getter
void AnalogReader::getData(float* v32, float* v33, float* v34, float* v35) {
    *v32 = voltage32;
    *v33 = voltage33;
    *v34 = voltage34;
    *v35 = voltage35;
}

// Loop Principal (Polling)
void AnalogReader::loop() {
    // Lê os sensores 4 vezes por segundo (a cada 250ms)
    unsigned long now = millis();
    if (now - lastReadTime >= 250) { 
        lastReadTime = now;
        readData();

        // Imprime os valores no console (com 2 casas decimais)
        Serial.print("ADC D32: "); Serial.print(voltage32, 2);
        Serial.print("V | D33: "); Serial.print(voltage33, 2);
        Serial.print("V | D34: "); Serial.print(voltage34, 2);
        Serial.print("V | D35: "); Serial.print(voltage35, 2);
        Serial.println("V");
    }
}