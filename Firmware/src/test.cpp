// #include <Arduino.h>
// #include <Wire.h>

// void setup() {
//     // Inicia o I2C nos pinos padrão (SDA=21, SCL=22)
//     Wire.begin(); 
    
//     Serial.begin(9600);
//     Serial.println("\n--- I2C Scanner ---");
//     Serial.println("Varrendo pinos SDA=21 e SCL=22...");
// }

// void loop() {
//     byte error, address;
//     int nDevices = 0;

//     Serial.println("Varrendo...");

//     for (address = 1; address < 127; address++) {
//         Wire.beginTransmission(address);
//         error = Wire.endTransmission();

//         if (error == 0) {
//             Serial.print("Dispositivo I2C encontrado no endereço 0x");
//             if (address < 16) Serial.print("0");
//             Serial.print(address, HEX);
//             Serial.println(" !");
//             nDevices++;
//         }
//     }
    
//     if (nDevices == 0)
//         Serial.println("Nenhum dispositivo I2C encontrado.\n");
//     else
//         Serial.println("Varredura concluída.\n");

//     delay(5000); // Espera 5 segundos
// }