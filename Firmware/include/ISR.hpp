#ifndef ISR_HPP
#define ISR_HPP

#include <Arduino.h>
#include "GPIOS.hpp"

extern volatile bool mpuInterrupt;
extern volatile bool magInterrupt;

void Init_ISR();

void IRAM_ATTR onMpuInterrupt();
void IRAM_ATTR onMagInterrupt();

#endif // ISR_HPP