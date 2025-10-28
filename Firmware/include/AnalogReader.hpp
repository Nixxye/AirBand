#ifndef ANALOGREADER_HPP
#define ANALOGREADER_HPP

#include "Arduino.h"

class AnalogReader {
public:
    /**
     * @brief Obtém a instância Singleton da classe.
     */
    static AnalogReader* Init_AnalogReader();

    /**
     * @brief Loop principal, deve ser chamado no main loop.
     * Lê os pinos ADC em uma frequência fixa e os imprime.
     */
    void loop();

    /**
     * @brief Obtém as últimas tensões lidas.
     * @param v32 Ponteiro para armazenar a tensão do pino 32.
     * @param v33 Ponteiro para armazenar a tensão do pino 33.
     * @param v34 Ponteiro para armazenar a tensão do pino 34.
     * @param v35 Ponteiro para armazenar a tensão do pino 35.
     */
    void getData(float* v32, float* v33, float* v34, float* v35);

private:
    // Construtor privado (Singleton)
    AnalogReader();
    
    // Destrutor privado
    ~AnalogReader();

    // Instância estática (Singleton)
    static AnalogReader* instance;

    // Função de leitura interna
    void readData();

    // Membros para armazenar as tensões (em Volts)
    float voltage32;
    float voltage33;
    float voltage34;
    float voltage35;

    // Para controlar a taxa de leitura (polling)
    unsigned long lastReadTime;

    // Constantes de hardware do ADC
    const float MAX_ADC_VALUE = 4095.0; // ESP32 tem 12-bit ADC
    const float MAX_ADC_VOLTAGE = 3.3;  // Tensão de referência
};

#endif // ANALOGREADER_HPP