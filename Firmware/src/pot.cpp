// #include <Arduino.h>

// // Defina o pino ADC que você conectou ao pino do meio do potenciômetro
// // Pinos ADC1 (GPIOs 32-39) são recomendados. Ex: 34
// #define POT_PIN 15

// void setup() {
//     Serial.begin(115200);
// }

// void loop() {
//     // Lê o valor analógico do pino
//     // A ESP32 tem um ADC de 12 bits, então os valores variam de 0 a 4095.
//     int valor = analogRead(POT_PIN);

//     // Imprime o valor no console
//     Serial.print("Valor do Potenciômetro: ");
//     Serial.println(valor);

//     delay(250); // Aguarda um pouco antes de ler novamente
// }