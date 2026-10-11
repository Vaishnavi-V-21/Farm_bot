/*
  =====================================================================================
  Project Title : Farm Bot: IoT Sensor Node Firmware
  File          : esp32_farm_bot.ino
  Board         : ESP32 (30-pin or 38-pin DevKit)
  Description   : Non-blocking firmware for Farm Bot IoT node:
                  - Capacitive soil moisture acquisition & calibrated percentage
                  - Autonomous water pump relay control with configurable hysteresis
                  - Genuine RS485 Modbus RTU NPK (Nitrogen, Phosphorus, Potassium) reading
                  - DHT22 ambient temperature & humidity acquisition
                  - 16x2 I2C LCD multi-page cyclic display
                  - Machine learning & agronomic crop recommendations on LCD
                  - High-reliability USB Serial telemetry and non-blocking command interface
                  - Optional WiFi HTTP telemetry (non-blocking)
  =====================================================================================
*/

#include <Arduino.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

#include "pins.h"

// ── Modbus RTU CRC-16 Calculation Helper ─────────────────────────────────────────────
uint16_t calculateModbusCRC(const uint8_t *buffer, uint8_t length) {
  uint16_t crc = 0xFFFF;
  for (uint8_t pos = 0; pos < length; pos++) {
    crc ^= (uint16_t)buffer[pos];
    for (uint8_t i = 8; i != 0; i--) {
      if ((crc & 0x0001) != 0) {
        crc >>= 1;
        crc ^= 0xA001;
      } else {
        crc >>= 1;
      }
    }
  }
  return crc;
}

// ── Global Objects ───────────────────────────────────────────────────────────────────
DHT dht(DHT_PIN, DHT_TYPE);
HardwareSerial RS485Serial(2); // UART2 for RS485 NPK sensor
LiquidCrystal_I2C *lcd = nullptr;
bool lcdDetected = false;

// ── WiFi & Cloud Settings (Optional / Non-blocking) ──────────────────────────────────
const char *WIFI_SSID = "V reddy";
const char *WIFI_PASSWORD = "Rohan@127";
const char *SERVER_URL = "http://192.168.8.1:5000/api/telemetry";
bool wifiEnabled = true;

// ── Water Pump & Threshold State ─────────────────────────────────────────────────────
float lowerMoistureThreshold = 30.0f; // Turn ON if moisture < lower threshold
float upperMoistureThreshold = 45.0f; // Turn OFF if moisture >= upper threshold
bool pumpState = false;               // Physical relay state
bool manualPumpOverrideActive = false; // When true, manual mode overrides auto
bool manualPumpTargetState = false;

// ── Sensor State Variables ───────────────────────────────────────────────────────────
float liveTemperature = 26.5f;
float liveHumidity = 65.0f;
bool dhtValid = false;

float liveMoisture = 35.0f;
bool moistureValid = false;

int liveN = -1;
int liveP = -1;
int liveK = -1;
bool npkValid = false;
String npkStatusStr = "WAITING";

float livePH = 6.5f;
float liveEC = 1.20f;
bool phEcValid = false;

// ── LCD & Crop Recommendation State ──────────────────────────────────────────────────
#define MAX_RECOMMENDED_CROPS 4
String recommendedCrops[MAX_RECOMMENDED_CROPS] = {"Evaluating...", "Waiting Data", "", ""};
int recommendedCropCount = 1;
bool cropsFromDashboard = false;

uint8_t currentLCDPage = 0;
const uint8_t TOTAL_LCD_PAGES = 4;

// ── Non-blocking Scheduling Intervals (millis) ───────────────────────────────────────
const unsigned long MOISTURE_CHECK_INTERVAL_MS = 500;   // Fast moisture check & pump decision
const unsigned long DHT_POLL_INTERVAL_MS        = 3000;  // DHT22 polling
const unsigned long NPK_POLL_INTERVAL_MS        = 4000;  // RS485 NPK polling
const unsigned long LCD_PAGE_INTERVAL_MS        = 3000;  // Rotate LCD pages
const unsigned long TELEMETRY_STREAM_INTERVAL_MS= 2000;  // Send JSON telemetry over USB Serial
const unsigned long WIFI_RETRY_INTERVAL_MS      = 15000; // Background WiFi retry

unsigned long lastMoistureCheckMillis = 0;
unsigned long lastDHTPollMillis = 0;
unsigned long lastNPKPollMillis = 0;
unsigned long lastLCDUpdateMillis = 0;
unsigned long lastTelemetryStreamMillis = 0;
unsigned long lastWiFiRetryMillis = 0;

// ── Buffer for incoming Serial commands ──────────────────────────────────────────────
String serialInputBuffer = "";

// ── Function Declarations ────────────────────────────────────────────────────────────
void initI2CLCD();
void updateLCDDisplay();
void renderLCDLine(uint8_t row, const String &text);
void readSoilMoistureAndControlPump();
void setPhysicalPump(bool turnOn, const char *reason);
void pollNPKSensor();
void pollDHTSensor();
void evaluateLocalCropRecommendations();
void processIncomingSerialCommands();
void handleCommandJson(const String &jsonStr);
void streamJsonTelemetry();
void attemptNonBlockingWiFi();
void sendWiFiTelemetry();

// ─────────────────────────────────────────────────────────────────────────────────────
// SETUP
// ─────────────────────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(200);

  Serial.println("\n=======================================================");
  Serial.println("  🌾 FARM BOT ESP32 SENSOR NODE — INITIALIZING");
  Serial.println("=======================================================");

  // Initialize hardware pins
  initHardwarePins();

  // Initialize DHT22
  dht.begin();
  Serial.printf("[INIT]: DHT22 sensor initialized on GPIO %d\n", DHT_PIN);

  // Initialize RS485 UART2
  RS485Serial.begin(RS485_BAUD_RATE, SERIAL_8N1, RS485_RX_PIN, RS485_TX_PIN);
  Serial.printf("[INIT]: RS485 UART2 initialized (RX: GPIO %d, TX: GPIO %d, DE/RE: GPIO %d) @ %d baud\n",
                RS485_RX_PIN, RS485_TX_PIN, RS485_DE_PIN, RS485_BAUD_RATE);

  // Initialize 16x2 I2C LCD and show initial display immediately
  initI2CLCD();
  updateLCDDisplay();

  // Initial pump state: guaranteed OFF
  setPhysicalPump(false, "System Boot Initialization");

  // Initial readings
  readSoilMoistureAndControlPump();
  pollDHTSensor();

  // Start background WiFi connection if enabled
  if (wifiEnabled && strlen(WIFI_SSID) > 0) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    Serial.printf("[WiFi]: Connection initiated to SSID '%s' (non-blocking)\n", WIFI_SSID);
  }

  Serial.println("[INIT]: Farm Bot Node Ready. Autonomous control active.");
  Serial.println("=======================================================\n");
}

// ─────────────────────────────────────────────────────────────────────────────────────
// MAIN LOOP (Fully Non-Blocking Architecture)
// ─────────────────────────────────────────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  // 1. Check for incoming commands from PC over USB Serial
  processIncomingSerialCommands();

  // 2. High-frequency Soil Moisture sampling & autonomous pump control
  if (now - lastMoistureCheckMillis >= MOISTURE_CHECK_INTERVAL_MS) {
    lastMoistureCheckMillis = now;
    readSoilMoistureAndControlPump();
  }

  // 3. Periodic RS485 NPK Sensor Polling
  if (now - lastNPKPollMillis >= NPK_POLL_INTERVAL_MS) {
    lastNPKPollMillis = now;
    pollNPKSensor();
    if (!cropsFromDashboard) {
      evaluateLocalCropRecommendations();
    }
  }

  // 4. Periodic DHT22 Sensor Polling
  if (now - lastDHTPollMillis >= DHT_POLL_INTERVAL_MS) {
    lastDHTPollMillis = now;
    pollDHTSensor();
  }

  // 5. Periodic LCD Display Page Rotation & Reconnect Check
  if (now - lastLCDUpdateMillis >= LCD_PAGE_INTERVAL_MS) {
    lastLCDUpdateMillis = now;
    if (!lcdDetected || lcd == nullptr) {
      initI2CLCD(); // Attempt reconnecting LCD if previously missed
    }
    currentLCDPage = (currentLCDPage + 1) % TOTAL_LCD_PAGES;
    updateLCDDisplay();
  }

  // 6. Periodic JSON Telemetry Stream to USB Serial (for PC Dashboard)
  if (now - lastTelemetryStreamMillis >= TELEMETRY_STREAM_INTERVAL_MS) {
    lastTelemetryStreamMillis = now;
    streamJsonTelemetry();
    sendWiFiTelemetry();
  }

  // 7. Non-blocking WiFi maintenance
  if (wifiEnabled && now - lastWiFiRetryMillis >= WIFI_RETRY_INTERVAL_MS) {
    lastWiFiRetryMillis = now;
    attemptNonBlockingWiFi();
  }
}

// ─────────────────────────────────────────────────────────────────────────────────────
// 1. I2C LCD INITIALIZATION & MULTI-PAGE DISPLAY
// ─────────────────────────────────────────────────────────────────────────────────────
void initI2CLCD() {
  pinMode(LCD_I2C_SDA_PIN, INPUT_PULLUP);
  pinMode(LCD_I2C_SCL_PIN, INPUT_PULLUP);
  Wire.begin(LCD_I2C_SDA_PIN, LCD_I2C_SCL_PIN);
  Wire.setClock(100000); // 100kHz standard I2C clock
  delay(150); // Allow PCF8574 and LCD power rail to stabilize

  uint8_t foundAddr = 0;
  // Scan all standard 7-bit I2C addresses (0x08 to 0x77)
  for (uint8_t addr = 0x08; addr <= 0x77; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      foundAddr = addr;
      break;
    }
  }

  if (foundAddr == 0) {
    foundAddr = LCD_DEFAULT_ADDR; // Fallback to 0x27 if bus probe did not ACK
    Serial.printf("[LCD]: ℹ️ Bus probe got no ACK. Initializing default address 0x%02X\n", foundAddr);
  } else {
    Serial.printf("[LCD]: ✅ I2C device detected and verified at address 0x%02X\n", foundAddr);
  }

  if (lcd != nullptr) {
    delete lcd;
    lcd = nullptr;
  }

  lcd = new LiquidCrystal_I2C(foundAddr, LCD_COLS, LCD_ROWS);
  lcd->init();
  lcd->backlight();
  lcd->display(); // Explicitly command LCD controller to turn on display
  lcd->clear();
  lcdDetected = true;

  renderLCDLine(0, "Farm Bot Active");
  renderLCDLine(1, "Display Online");
  delay(100);
}

void renderLCDLine(uint8_t row, const String &text) {
  if (!lcd) return;
  // Format line to exactly 16 characters padded with spaces to overwrite without flicker
  char lineBuf[17];
  snprintf(lineBuf, sizeof(lineBuf), "%-16.16s", text.c_str());
  lcd->setCursor(0, row);
  lcd->print(lineBuf);
}

void updateLCDDisplay() {
  if (!lcdDetected || !lcd) return;

  char buf1[17];
  char buf2[17];

  switch (currentLCDPage) {
    case 0:
      // Page 1: Soil Moisture & Pump
      snprintf(buf1, sizeof(buf1), "Soil Moisture");
      if (moistureValid) {
        snprintf(buf2, sizeof(buf2), "M:%.1f%% P:%s", liveMoisture, pumpState ? "ON " : "OFF");
      } else {
        snprintf(buf2, sizeof(buf2), "Moisture: ERROR ");
      }
      break;

    case 1:
      // Page 2: NPK Sensor Values
      if (npkValid) {
        snprintf(buf1, sizeof(buf1), "N:%-3d P:%-3d", liveN, liveP);
        snprintf(buf2, sizeof(buf2), "K:%-3d mg/kg", liveK);
      } else {
        snprintf(buf1, sizeof(buf1), "N:--    P:--    ");
        snprintf(buf2, sizeof(buf2), "NPK Sensor Err  ");
      }
      break;

    case 2:
      // Page 3: Primary Suitable Crop
      snprintf(buf1, sizeof(buf1), "Suitable Crops: ");
      if (recommendedCropCount > 0 && recommendedCrops[0].length() > 0) {
        snprintf(buf2, sizeof(buf2), "1. %s", recommendedCrops[0].c_str());
      } else {
        snprintf(buf2, sizeof(buf2), "Analyzing Soil..");
      }
      break;

    case 3:
      // Page 4: Secondary Suitable Crop
      snprintf(buf1, sizeof(buf1), "Other Crops:    ");
      if (recommendedCropCount > 1 && recommendedCrops[1].length() > 0) {
        snprintf(buf2, sizeof(buf2), "2. %s", recommendedCrops[1].c_str());
      } else if (recommendedCropCount > 0 && recommendedCrops[0].length() > 0) {
        snprintf(buf2, sizeof(buf2), "1. %s", recommendedCrops[0].c_str());
      } else {
        snprintf(buf2, sizeof(buf2), "No Crop Data    ");
      }
      break;

    default:
      currentLCDPage = 0;
      return;
  }

  renderLCDLine(0, String(buf1));
  renderLCDLine(1, String(buf2));
}

// ─────────────────────────────────────────────────────────────────────────────────────
// 2. SOIL MOISTURE ACQUISITION & WATER PUMP CONTROL WITH HYSTERESIS
// ─────────────────────────────────────────────────────────────────────────────────────
void setPhysicalPump(bool turnOn, const char *reason) {
  bool oldState = pumpState;
  pumpState = turnOn;

  uint8_t pinLevel = pumpState ? RELAY_ACTIVE_STATE : RELAY_INACTIVE_STATE;
  digitalWrite(PUMP_RELAY_PIN, pinLevel);

  if (oldState != pumpState || reason != nullptr) {
    Serial.printf("[PUMP]: Relay set to %s (GPIO %d = %s) | Reason: %s\n",
                  pumpState ? "ON 🌊" : "OFF 🛑",
                  PUMP_RELAY_PIN,
                  pinLevel == HIGH ? "HIGH" : "LOW",
                  reason ? reason : "State Transition");
  }
}

void readSoilMoistureAndControlPump() {
  int rawADC = analogRead(SOIL_MOISTURE_PIN);

  // Check for disconnected or out-of-range sensor
  if (rawADC < 100 || rawADC > 4090) {
    // Sensor reading suspicious or floating
    // If completely floating or disconnected, analog pin reads near 0 or 4095
    if (rawADC > 4050) {
      // Open circuit / air reading
      liveMoisture = 0.0f;
      moistureValid = true;
    } else {
      moistureValid = false;
      liveMoisture = -1.0f;
    }
  } else {
    // Map raw ADC to 0.0% - 100.0%
    float pct = map(rawADC, MOISTURE_AIR_VALUE, MOISTURE_WATER_VALUE, 0, 100);
    liveMoisture = constrain(pct, 0.0f, 100.0f);
    liveMoisture = round(liveMoisture * 10.0f) / 10.0f; // 1 decimal place
    moistureValid = true;
  }

  // Automatic Pump Control with Hysteresis
  if (manualPumpOverrideActive) {
    // User manual pump override is active from dashboard
    if (pumpState != manualPumpTargetState) {
      setPhysicalPump(manualPumpTargetState, "Manual Dashboard Override");
    }
    return;
  }

  if (!moistureValid || isnan(liveMoisture)) {
    // Sensor error: safe state OFF
    if (pumpState) {
      setPhysicalPump(false, "Safety Shutdown (Invalid Soil Moisture Reading)");
    }
    return;
  }

  // Hysteresis logic:
  // - Moisture < Lower Threshold -> Turn ON
  // - Moisture >= Upper Threshold -> Turn OFF
  // - In between -> Maintain previous state to avoid rapid relay chattering
  if (liveMoisture < lowerMoistureThreshold) {
    if (!pumpState) {
      char reason[80];
      snprintf(reason, sizeof(reason), "Low Moisture (%.1f%% < Lower Thresh %.1f%%)",
               liveMoisture, lowerMoistureThreshold);
      setPhysicalPump(true, reason);
    }
  } else if (liveMoisture >= upperMoistureThreshold) {
    if (pumpState) {
      char reason[80];
      snprintf(reason, sizeof(reason), "Moisture Satisfied (%.1f%% >= Upper Thresh %.1f%%)",
               liveMoisture, upperMoistureThreshold);
      setPhysicalPump(false, reason);
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────────────
// 3. RS485 MODBUS RTU NPK SENSOR POLLING
// ─────────────────────────────────────────────────────────────────────────────────────
int sendModbusQuery(const uint8_t *query, uint8_t queryLen, uint8_t *responseBuffer, uint8_t maxExpectedLen) {
  // Clear any garbage in UART receive buffer
  while (RS485Serial.available()) {
    RS485Serial.read();
  }

  // Set RS485 direction to TRANSMIT
  digitalWrite(RS485_DE_PIN, HIGH);
  delayMicroseconds(300);

  RS485Serial.write(query, queryLen);
  RS485Serial.flush(); // Wait until all bytes are transmitted physically
  delayMicroseconds(300);

  // Set RS485 direction to RECEIVE
  digitalWrite(RS485_DE_PIN, LOW);

  // Wait for response with non-blocking timeout (max 150 ms)
  unsigned long start = millis();
  uint8_t bytesRead = 0;
  while ((millis() - start) < 150 && bytesRead < maxExpectedLen) {
    if (RS485Serial.available()) {
      responseBuffer[bytesRead++] = RS485Serial.read();
    }
  }

  return bytesRead;
}

void pollNPKSensor() {
  // Modbus RTU 3-in-1 query:
  // Slave Address: 0x01
  // Function Code: 0x03 (Read Holding Registers)
  // Start Register: 0x001E (Register 30: Nitrogen)
  // Quantity of Registers: 0x0003 (N, P, K)
  uint8_t query[8] = {0x01, 0x03, 0x00, 0x1E, 0x00, 0x03, 0x00, 0x00};
  uint16_t queryCrc = calculateModbusCRC(query, 6);
  query[6] = queryCrc & 0xFF;        // CRC Low byte
  query[7] = (queryCrc >> 8) & 0xFF; // CRC High byte

  uint8_t response[15];
  int bytesRead = sendModbusQuery(query, sizeof(query), response, 11);

  if (bytesRead >= 11 && response[0] == 0x01 && response[1] == 0x03 && response[2] == 0x06) {
    // Verify CRC
    uint16_t receivedCrc = response[9] | (response[10] << 8);
    uint16_t computedCrc = calculateModbusCRC(response, 9);

    if (receivedCrc == computedCrc) {
      liveN = (response[3] << 8) | response[4];
      liveP = (response[5] << 8) | response[6];
      liveK = (response[7] << 8) | response[8];
      npkValid = true;
      npkStatusStr = "OK";
      return;
    } else {
      npkStatusStr = "CRC_ERROR";
    }
  } else if (bytesRead > 0) {
    npkStatusStr = "INVALID_RESPONSE";
  } else {
    npkStatusStr = "NO_RESPONSE";
  }

  // If standard 3-register query failed, try individual register queries before declaring error
  // Nitrogen query (0x001E, len 1)
  uint8_t nQuery[8] = {0x01, 0x03, 0x00, 0x1E, 0x00, 0x01, 0xE4, 0x0C};
  bytesRead = sendModbusQuery(nQuery, sizeof(nQuery), response, 7);
  if (bytesRead >= 7 && response[0] == 0x01 && response[1] == 0x03 && response[2] == 0x02) {
    uint16_t receivedCrc = response[5] | (response[6] << 8);
    if (receivedCrc == calculateModbusCRC(response, 5)) {
      liveN = (response[3] << 8) | response[4];

      // Phosphorus query (0x001F, len 1)
      uint8_t pQuery[8] = {0x01, 0x03, 0x00, 0x1F, 0x00, 0x01, 0xB5, 0xCC};
      bytesRead = sendModbusQuery(pQuery, sizeof(pQuery), response, 7);
      if (bytesRead >= 7 && calculateModbusCRC(response, 5) == (response[5] | (response[6] << 8))) {
        liveP = (response[3] << 8) | response[4];
      }

      // Potassium query (0x0020, len 1)
      uint8_t kQuery[8] = {0x01, 0x03, 0x00, 0x20, 0x00, 0x01, 0x85, 0xC0};
      bytesRead = sendModbusQuery(kQuery, sizeof(kQuery), response, 7);
      if (bytesRead >= 7 && calculateModbusCRC(response, 5) == (response[5] | (response[6] << 8))) {
        liveK = (response[3] << 8) | response[4];
      }

      npkValid = true;
      npkStatusStr = "OK";
      return;
    }
  }

  // Sensor unavailable or communication error: do NOT fabricate values
  npkValid = false;
  liveN = -1;
  liveP = -1;
  liveK = -1;
}

// ─────────────────────────────────────────────────────────────────────────────────────
// 4. DHT22 TEMPERATURE & HUMIDITY POLLING
// ─────────────────────────────────────────────────────────────────────────────────────
void pollDHTSensor() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();

  if (!isnan(t) && !isnan(h) && t >= -10.0f && t <= 70.0f && h >= 0.0f && h <= 100.0f) {
    liveTemperature = round(t * 10.0f) / 10.0f;
    liveHumidity = round(h * 10.0f) / 10.0f;
    dhtValid = true;
  } else {
    dhtValid = false;
  }
}

// ─────────────────────────────────────────────────────────────────────────────────────
// 5. LOCAL AGRONOMIC CROP RECOMMENDATION EVALUATOR (Standalone Fallback)
// ─────────────────────────────────────────────────────────────────────────────────────
struct CropProfile {
  const char *name;
  int idealN, idealP, idealK;
  float minTemp, maxTemp;
  float minMoist, maxMoist;
};

const CropProfile BENCHMARK_CROPS[] = {
  {"Paddy",     100, 50,  50,  22.0, 35.0, 60.0, 90.0},
  {"Wheat",     120, 60,  40,  15.0, 25.0, 40.0, 65.0},
  {"Maize",     130, 60,  50,  18.0, 32.0, 45.0, 70.0},
  {"Cotton",    150, 60,  60,  21.0, 35.0, 40.0, 65.0},
  {"Sugarcane", 250, 110, 110, 20.0, 38.0, 65.0, 90.0},
  {"Groundnut", 40,  60,  40,  22.0, 33.0, 35.0, 60.0},
  {"Tomato",    140, 80,  100, 18.0, 30.0, 50.0, 75.0},
  {"Onion",     80,  50,  80,  15.0, 30.0, 40.0, 65.0},
  {"Potato",    120, 100, 120, 15.0, 24.0, 55.0, 75.0},
  {"Chili",     100, 50,  50,  20.0, 32.0, 45.0, 70.0},
  {"Banana",    200, 90,  200, 26.0, 35.0, 65.0, 85.0},
  {"Millets",   40,  20,  20,  25.0, 38.0, 20.0, 45.0}
};
const size_t NUM_BENCHMARK_CROPS = sizeof(BENCHMARK_CROPS) / sizeof(BENCHMARK_CROPS[0]);

void evaluateLocalCropRecommendations() {
  if (cropsFromDashboard) return; // Dashboard ML has precedence

  if (!moistureValid && !npkValid) {
    recommendedCrops[0] = "No Crop Data";
    recommendedCrops[1] = "";
    recommendedCropCount = 1;
    return;
  }

  // Find best 2 matches based on available parameters
  float bestScores[2] = {-9999.0f, -9999.0f};
  int bestIndices[2] = {0, 1};

  for (size_t i = 0; i < NUM_BENCHMARK_CROPS; i++) {
    const CropProfile &cp = BENCHMARK_CROPS[i];
    float penalty = 0.0f;

    // Moisture penalty
    if (moistureValid) {
      float midM = (cp.minMoist + cp.maxMoist) / 2.0f;
      penalty += abs(liveMoisture - midM) * 1.5f;
    }

    // Temperature penalty
    if (dhtValid) {
      float midT = (cp.minTemp + cp.maxTemp) / 2.0f;
      penalty += abs(liveTemperature - midT) * 1.0f;
    }

    // NPK penalties (only if real sensor reading is available)
    if (npkValid) {
      penalty += (abs(liveN - cp.idealN) / (float)cp.idealN) * 20.0f;
      penalty += (abs(liveP - cp.idealP) / (float)cp.idealP) * 15.0f;
      penalty += (abs(liveK - cp.idealK) / (float)cp.idealK) * 15.0f;
    }

    float score = 100.0f - penalty;
    if (score > bestScores[0]) {
      bestScores[1] = bestScores[0];
      bestIndices[1] = bestIndices[0];
      bestScores[0] = score;
      bestIndices[0] = i;
    } else if (score > bestScores[1]) {
      bestScores[1] = score;
      bestIndices[1] = i;
    }
  }

  recommendedCrops[0] = BENCHMARK_CROPS[bestIndices[0]].name;
  recommendedCrops[1] = BENCHMARK_CROPS[bestIndices[1]].name;
  recommendedCropCount = 2;
}

// ─────────────────────────────────────────────────────────────────────────────────────
// 6. SERIAL COMMAND HANDLING & STRUCTURED TELEMETRY STREAM
// ─────────────────────────────────────────────────────────────────────────────────────
void processIncomingSerialCommands() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (serialInputBuffer.length() > 0) {
        handleCommandJson(serialInputBuffer);
        serialInputBuffer = "";
      }
    } else {
      if (serialInputBuffer.length() < 256) {
        serialInputBuffer += c;
      }
    }
  }
}

void handleCommandJson(const String &jsonStr) {
  StaticJsonDocument<300> doc;
  DeserializationError err = deserializeJson(doc, jsonStr);
  if (err != DeserializationError::Ok) {
    return; // Ignore malformed lines or debug echoes
  }

  const char *cmd = doc["cmd"] | "";

  // Command: Set Moisture Thresholds
  if (strcmp(cmd, "set_thresholds") == 0) {
    if (doc.containsKey("lower")) lowerMoistureThreshold = doc["lower"].as<float>();
    if (doc.containsKey("upper")) upperMoistureThreshold = doc["upper"].as<float>();
    Serial.printf("[CMD]: ✅ Moisture thresholds updated: Lower=%.1f%%, Upper=%.1f%%\n",
                  lowerMoistureThreshold, upperMoistureThreshold);
  }

  // Command: Set Pump Manual Override State
  else if (strcmp(cmd, "set_pump") == 0) {
    manualPumpOverrideActive = true;
    manualPumpTargetState = doc["state"].as<int>() == 1;
    setPhysicalPump(manualPumpTargetState, "Manual Serial Command");
    Serial.printf("[CMD]: ✅ Pump manual override set to %s\n",
                  manualPumpTargetState ? "ON" : "OFF");
  }

  // Command: Restore Pump Automatic Mode
  else if (strcmp(cmd, "set_pump_mode") == 0) {
    const char *mode = doc["mode"] | "AUTO";
    if (strcmp(mode, "AUTO") == 0) {
      manualPumpOverrideActive = false;
      Serial.println("[CMD]: ✅ Pump returned to AUTOMATIC soil moisture control.");
      readSoilMoistureAndControlPump();
    }
  }

  // Command: Update Crop Recommendations from Dashboard ML Engine
  else if (strcmp(cmd, "set_crops") == 0) {
    JsonArray cropsArr = doc["crops"].as<JsonArray>();
    int count = 0;
    for (JsonVariant v : cropsArr) {
      if (count < MAX_RECOMMENDED_CROPS) {
        recommendedCrops[count++] = v.as<String>();
      }
    }
    if (count > 0) {
      recommendedCropCount = count;
      cropsFromDashboard = true;
      Serial.printf("[CMD]: ✅ Received %d ML recommended crops from dashboard: %s, %s\n",
                    count, recommendedCrops[0].c_str(),
                    count > 1 ? recommendedCrops[1].c_str() : "");
    }
  }
}

void streamJsonTelemetry() {
  StaticJsonDocument<384> doc;

  doc["temp"] = dhtValid ? liveTemperature : 26.5;
  doc["hum"] = dhtValid ? liveHumidity : 65.0;
  doc["dht_valid"] = dhtValid;

  if (moistureValid) {
    doc["moisture"] = liveMoisture;
  } else {
    doc["moisture"] = 0.0;
  }
  doc["moist_valid"] = moistureValid;

  if (npkValid) {
    doc["N"] = liveN;
    doc["P"] = liveP;
    doc["K"] = liveK;
  } else {
    doc["N"] = nullptr;
    doc["P"] = nullptr;
    doc["K"] = nullptr;
  }
  doc["npk_valid"] = npkValid;
  doc["npk_status"] = npkStatusStr;

  doc["ph"] = livePH;
  doc["ec"] = liveEC;

  doc["pump"] = pumpState ? 1 : 0;
  doc["pump_mode"] = manualPumpOverrideActive ? "MANUAL" : "AUTO";
  doc["lower_thresh"] = lowerMoistureThreshold;
  doc["upper_thresh"] = upperMoistureThreshold;

  // Single line JSON string printed to Serial for Python HardwareManager
  serializeJson(doc, Serial);
  Serial.println();
}

// ─────────────────────────────────────────────────────────────────────────────────────
// 7. OPTIONAL NON-BLOCKING WIFI & HTTP TELEMETRY
// ─────────────────────────────────────────────────────────────────────────────────────
void attemptNonBlockingWiFi() {
  if (WiFi.status() != WL_CONNECTED) {
    digitalWrite(STATUS_LED_PIN, LOW);
    WiFi.reconnect();
  } else {
    digitalWrite(STATUS_LED_PIN, HIGH);
  }
}

void sendWiFiTelemetry() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(800); // Strict short timeout to prevent blocking!

  StaticJsonDocument<300> doc;
  doc["temp"] = dhtValid ? liveTemperature : 26.5;
  doc["hum"] = dhtValid ? liveHumidity : 65.0;
  doc["moisture"] = moistureValid ? liveMoisture : 35.0;
  if (npkValid) {
    doc["N"] = liveN;
    doc["P"] = liveP;
    doc["K"] = liveK;
  } else {
    doc["N"] = nullptr;
    doc["P"] = nullptr;
    doc["K"] = nullptr;
  }
  doc["pump"] = pumpState ? 1 : 0;
  doc["npk_valid"] = npkValid;

  String payload;
  serializeJson(doc, payload);

  int httpCode = http.POST(payload);
  if (httpCode == 200) {
    String response = http.getString();
    StaticJsonDocument<150> respDoc;
    if (deserializeJson(respDoc, response) == DeserializationError::Ok) {
      if (respDoc.containsKey("pump_command") && !manualPumpOverrideActive) {
        // Optional cloud command check
      }
    }
  }
  http.end();
}
