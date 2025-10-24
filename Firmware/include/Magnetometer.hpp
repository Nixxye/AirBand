#ifndef MAGNETOMETER_HPP
#define MAGNETOMETER_HPP

#include "Arduino.h"
#include <Wire.h>
#include <QMC5883LCompass.h> // Biblioteca 'mprograms'
#include "GPIOS.hpp"

class Magnetometer {
public:
    /**
     * @brief Obtém a instância Singleton.
     */
    static Magnetometer* Init_Magnetometer();

    /**
     * @brief Loop principal, lê e imprime dados baseado em um timer.
     */
    void loop();

    /**
     * @brief Obtém os últimos dados lidos.
     */
    void getData(int* mx, int* my, int* mz, float* heading, String &bearing);

private:
    Magnetometer(); // Construtor privado
    ~Magnetometer(); // Destrutor privado
    
    static Magnetometer* instance; // Instância Singleton

    void configQMC5883L_Simple(); // Função de configuração simples
    void readData();

    QMC5883LCompass compass; // O objeto da biblioteca

    // Variáveis para armazenar os dados
    int magX; 
    int magY;
    int magZ;
    float headingDegrees;
    String bearingName;

    // Timer para leitura (não bloqueante)
    unsigned long lastReadTime; 
};

#endif // MAGNETOMETER_HPP