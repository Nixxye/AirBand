#include "ISR.hpp"

// Definição da flag global
// volatile bool mpuInterrupt = false;

void Init_ISR(){ 
    Serial.println("|ISR| ---------- Iniciando configuração de interrupções ----------");
    
    // Configuração do Giroscópio
    pinMode(INT_GYRO_PIN, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(INT_GYRO_PIN), onMpuInterrupt, RISING);
    
    // (Configuração do Magnetômetro removida)
    
    Serial.println("|ISR| ---------- Configuração de interrupções finalizada ----------");
}

void IRAM_ATTR onMpuInterrupt() {
    mpuInterrupt = true;
}

// (ISR do Magnetômetro removida)