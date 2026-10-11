#ifndef PINS_H
#define PINS_H

#include <Arduino.h>

/*
  =====================================================================================
  Project Title : Farm Bot: IoT Sensor Node Hardware Pin Configuration
  File          : pins.h
  Board         : ESP32 DevKit V1 (30-pin or 38-pin Dev Module)
  Description   : Master pin mapping definitions, hardware interfacing guide,
                  wire color codes, and electrical specifications for Farm Bot.
  =====================================================================================

  ESP32 PINOUT DIAGRAM & HARDWARE MAPPING:
  ┌───────────────────────────────────────────────────────────────────────────────────┐
  │ Sensor / Module          │ ESP32 Pin │ Type        │ Voltage │ Notes              │
  ├──────────────────────────┼───────────┼─────────────┼─────────┼────────────────────┤
  │ DHT22 (Temp & Humidity)  │ GPIO 4    │ Digital I/O │ 3.3V    │ 10kΩ pull-up to 3V3│
  │ Soil Moisture (Analog)   │ GPIO 34   │ Analog In   │ 3.3V    │ ADC1_CH6 (input-only│
  │ RS485 Transceiver (RO)   │ GPIO 16   │ UART2 RX    │ 3.3V/5V │ Connect to MAX485 RO│
  │ RS485 Transceiver (DI)   │ GPIO 17   │ UART2 TX    │ 3.3V/5V │ Connect to MAX485 DI│
  │ RS485 Direction (DE/RE)  │ GPIO 5    │ Digital Out │ 3.3V    │ HIGH=TX, LOW=RX    │
  │ Water Pump Relay IN      │ GPIO 26   │ Digital Out │ 5V/3.3V │ Configurable HIGH/LOW│
  │ LCD 16x2 I2C SDA         │ GPIO 21   │ I2C Data    │ 3.3V/5V │ Hardware I2C SDA   │
  │ LCD 16x2 I2C SCL         │ GPIO 22   │ I2C Clock   │ 3.3V/5V │ Hardware I2C SCL   │
  │ Onboard Status LED       │ GPIO 2    │ Digital Out │ 3.3V    │ Blinks on activity │
  └───────────────────────────────────────────────────────────────────────────────────┘

  POWER DISTRIBUTION RAILS:
  ┌───────────────────────────────────────────────────────────────────────────────────┐
  │ Rail / Source            │ Voltage   │ Connected Devices                          │
  ├──────────────────────────┼───────────┼────────────────────────────────────────────┤
  │ ESP32 3V3 Pin            │ 3.3V DC   │ DHT22 VCC, Soil Moisture VCC, Pull-ups     │
  │ ESP32 VIN / 5V Pin       │ 5.0V DC   │ 5V Relay VCC, MAX485 VCC, LCD I2C VCC      │
  │ External 12V DC Supply   │ 12.0V DC  │ NPK Sensor VCC (Brown wire), Pump Load (+) │
  │ Common GND Rail          │ 0V (GND)  │ ALL GNDs tied together (ESP32 + 12V + 5V)  │
  └───────────────────────────────────────────────────────────────────────────────────┘
*/

// =====================================================================================
// 1. DHT22 SENSOR PIN DEFINITION (Temperature & Relative Humidity)
// =====================================================================================
#define DHT_PIN                 4
#define DHT_TYPE                DHT22


// =====================================================================================
// 2. CAPACITIVE SOIL MOISTURE SENSOR (Analog Soil Water Content)
// =====================================================================================
#define SOIL_MOISTURE_PIN       34

// Soil Moisture Calibration Constants (Raw 12-bit ADC reading 0 - 4095)
#define MOISTURE_AIR_VALUE      3800   // Reading in completely dry air (0% moisture)
#define MOISTURE_WATER_VALUE    1200   // Reading submerged in clean water (100% moisture)


// =====================================================================================
// 3. MAX485 TTL-TO-RS485 MODULE & NPK SENSOR
// =====================================================================================
#define RS485_RX_PIN            16     // UART2 RX
#define RS485_TX_PIN            17     // UART2 TX
#define RS485_DE_PIN            5      // Direction Control: HIGH = Transmit, LOW = Receive
#define RS485_BAUD_RATE         4800   // Standard factory baud rate for RS485 NPK sensors


// =====================================================================================
// 4. WATER PUMP RELAY MODULE & ACTUATOR
// =====================================================================================
#define PUMP_RELAY_PIN          26

// Set to true if using standard Active-LOW optocoupled relay module; false for Active-HIGH
#define RELAY_ACTIVE_LOW        false

#define RELAY_ACTIVE_STATE      (RELAY_ACTIVE_LOW ? LOW : HIGH)
#define RELAY_INACTIVE_STATE    (RELAY_ACTIVE_LOW ? HIGH : LOW)


// =====================================================================================
// 5. 16x2 LCD DISPLAY VIA I2C BACKPACK (PCF8574)
// =====================================================================================
#define LCD_I2C_SDA_PIN         21     // Default ESP32 I2C SDA
#define LCD_I2C_SCL_PIN         22     // Default ESP32 I2C SCL
#define LCD_DEFAULT_ADDR        0x27   // Common addresses: 0x27 or 0x3F
#define LCD_COLS                16
#define LCD_ROWS                2


// =====================================================================================
// 6. STATUS INDICATOR & MISCELLANEOUS
// =====================================================================================
#define STATUS_LED_PIN          2


// =====================================================================================
// 7. HARDWARE INITIALIZATION HELPER FUNCTION
// =====================================================================================
inline void initHardwarePins() {
    pinMode(PUMP_RELAY_PIN, OUTPUT);
    digitalWrite(PUMP_RELAY_PIN, RELAY_INACTIVE_STATE); // Pump guaranteed OFF at boot

    pinMode(STATUS_LED_PIN, OUTPUT);
    digitalWrite(STATUS_LED_PIN, LOW);

    pinMode(RS485_DE_PIN, OUTPUT);
    digitalWrite(RS485_DE_PIN, LOW); // Default to RS485 Receive mode
}

#endif // PINS_H
