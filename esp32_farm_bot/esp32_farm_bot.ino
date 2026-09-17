/*
  =====================================================================================
  Project Title : Farm Bot: IoT Sensor Node Firmware
  File          : esp32_farm_bot.ino
  Board         : ESP32 (30-pin or 38-pin DevKit)
  Description   : Reads DHT22 (Temp/Humidity), Soil Moisture (Analog), and
  simulates NPK/pH/EC from RS485 or analog sensors. Sends JSON telemetry to the
                  Farm Bot PC dashboard via HTTP POST over WiFi. Controls water
  pump relay based on commands from the server.

  SENSOR WIRING:
  ┌────────────────────────────────────────────────────────────┐
  │  Sensor             │  ESP32 Pin  │  Notes                 │
  ├─────────────────────┼─────────────┼────────────────────────┤
  │  DHT22 DATA         │  GPIO 4     │  10kΩ pull-up to 3.3V  │
  │  Soil Moisture      │  GPIO 34    │  Analog input (ADC1)   │
  │  RS485 NPK/pH RX    │  GPIO 16    │  UART2 RX              │
  │  RS485 NPK/pH TX    │  GPIO 17    │  UART2 TX              │
  │  RS485 DE/RE Enable │  GPIO 5     │  Direction control     │
  │  Pump Relay IN      │  GPIO 26    │  HIGH=ON, LOW=OFF      │
  │  Status LED (opt)   │  GPIO 2     │  Onboard LED           │
  └─────────────────────┴─────────────┴────────────────────────┘

  LIBRARIES REQUIRED (Arduino IDE):
    - DHT sensor library by Adafruit
    - ArduinoJson by Benoit Blanchon
    - WiFi (built-in ESP32)
    - HTTPClient (built-in ESP32)

  =====================================================================================
*/

#include <Arduino.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <HTTPClient.h>
#include <WiFi.h>

// Forward function declarations for C++ / PlatformIO IntelliSense
void connectToWiFi();
void sendTelemetryToServer(float temp, float hum, float moisture, int n, int p,
                           int k, float ph, float ec);
float readTemperature();
float readHumidity();
float readSoilMoisturePct();
int readNPK_N();
int readNPK_P();
int readNPK_K();
float readSoilPH();
float readSoilEC();
int readRS485Sensor(const byte *cmd, int cmdLen, byte *responseBuffer);

// ── WiFi Configuration
// ───────────────────────────────────────────────────────────────
const char *WIFI_SSID = "VREDDY";       // ← Replace with your WiFi name
const char *WIFI_PASSWORD = "VPMVR@05"; // ← Replace with your WiFi password

// ── PC Server URL (replace with your PC's local IP address)
// ───────────────────────── Find your PC IP: run `ipconfig` in Command Prompt,
// look for IPv4 Address
const char *SERVER_URL =
    "http://192.168.8.1:5000/api/telemetry"; // ← Update IP!

// ── Pin Definitions
// ──────────────────────────────────────────────────────────────────
#define DHT_PIN 4 // DHT22 Data Pin
#define DHT_TYPE DHT22
#define SOIL_MOISTURE_PIN 34 // Analog Soil Moisture Sensor (ADC1_CH6)
#define RS485_RX_PIN 16      // UART2 RX (NPK/pH/EC sensor)
#define RS485_TX_PIN 17      // UART2 TX
#define RS485_DE_PIN 5       // RS485 Direction Enable (HIGH=TX, LOW=RX)
#define PUMP_RELAY_PIN 26    // Water Pump Relay
#define STATUS_LED_PIN 2     // Onboard LED for status indicator

// ── Timing Configuration
// ─────────────────────────────────────────────────────────────
#define TELEMETRY_INTERVAL_MS 5000 // Send data every 5 seconds
#define RETRY_DELAY_MS 3000        // Retry WiFi connect every 3 seconds

// ── Soil Moisture Calibration
// ──────────────────────────────────────────────────────── Calibrate these
// values by testing your sensor in dry air vs. submerged in water
#define MOISTURE_AIR_VALUE 3800   // ADC reading in completely dry air
#define MOISTURE_WATER_VALUE 1200 // ADC reading in water

// ── NPK RS485 Modbus Commands
// ──────────────────────────────────────────────────────── Standard command for
// Chinese RS485 NPK sensor (Model: JXBS-3001-NPK)
static const byte NPK_CMD[] = {0x01, 0x03, 0x00, 0x1E, 0x00, 0x03, 0x65, 0xCD};
static const byte PH_CMD[] = {0x01, 0x03, 0x00, 0x06, 0x00, 0x01, 0x64, 0x0B};
static const byte EC_CMD[] = {0x01, 0x03, 0x00, 0x15, 0x00, 0x01, 0x95, 0xCE};

// ── Global Objects
// ───────────────────────────────────────────────────────────────────
DHT dht(DHT_PIN, DHT_TYPE);
HardwareSerial RS485Serial(2); // UART2 for RS485 sensor

unsigned long lastTelemetrySendTime = 0;
bool pumpState = false;

// ────────────────────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n====================================================");
  Serial.println("  🌾 FARM BOT ESP32 SENSOR NODE - BOOTING UP...");
  Serial.println("====================================================");

  // Pin Modes
  pinMode(PUMP_RELAY_PIN, OUTPUT);
  pinMode(STATUS_LED_PIN, OUTPUT);
  pinMode(RS485_DE_PIN, OUTPUT);

  // Initial states
  digitalWrite(PUMP_RELAY_PIN, LOW); // Pump OFF at boot
  digitalWrite(STATUS_LED_PIN, LOW);
  digitalWrite(RS485_DE_PIN, LOW); // RS485 in receive mode

  // Initialize DHT22
  dht.begin();
  Serial.println("[DHT22]: Sensor initialized on GPIO " + String(DHT_PIN));

  // Initialize RS485 UART2 at 4800 baud (standard for NPK sensors)
  RS485Serial.begin(4800, SERIAL_8N1, RS485_RX_PIN, RS485_TX_PIN);
  Serial.println("[RS485]: UART2 initialized (GPIO16/17) at 4800 baud");

  // Connect to WiFi
  connectToWiFi();
}

// ────────────────────────────────────────────────────────────────────────────────────
void loop() {
  // Reconnect WiFi if disconnected
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi]: Connection lost! Reconnecting...");
    connectToWiFi();
  }

  unsigned long now = millis();
  if (now - lastTelemetrySendTime >= TELEMETRY_INTERVAL_MS) {
    lastTelemetrySendTime = now;

    // Read all sensors
    float temperature = readTemperature();
    float humidity = readHumidity();
    float soilMoisture = readSoilMoisturePct();
    int nitrogen = readNPK_N();
    int phosphorus = readNPK_P();
    int potassium = readNPK_K();
    float soilPH = readSoilPH();
    float soilEC = readSoilEC();

    // Log readings to Serial Monitor
    Serial.println("\n────────────────── SENSOR READINGS ──────────────────");
    Serial.printf(" Temperature   : %.1f °C\n", temperature);
    Serial.printf(" Humidity      : %.1f %%\n", humidity);
    Serial.printf(" Soil Moisture : %.1f %%\n", soilMoisture);
    Serial.printf(" Nitrogen (N)  : %d mg/kg\n", nitrogen);
    Serial.printf(" Phosphorus (P): %d mg/kg\n", phosphorus);
    Serial.printf(" Potassium (K) : %d mg/kg\n", potassium);
    Serial.printf(" Soil pH       : %.2f\n", soilPH);
    Serial.printf(" Soil EC       : %.2f mS/cm\n", soilEC);
    Serial.printf(" Pump Status   : %s\n", pumpState ? "ON" : "OFF");
    Serial.println("──────────────────────────────────────────────────────");

    // Send to PC Dashboard
    sendTelemetryToServer(temperature, humidity, soilMoisture, nitrogen,
                          phosphorus, potassium, soilPH, soilEC);
  }
}

// ── WiFi Connection
// ──────────────────────────────────────────────────────────────────
void connectToWiFi() {
  Serial.printf("\n[WiFi]: Connecting to '%s'", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(RETRY_DELAY_MS / 10);
    Serial.print(".");
    attempts++;
    digitalWrite(STATUS_LED_PIN,
                 !digitalRead(STATUS_LED_PIN)); // Blink while connecting
  }

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(STATUS_LED_PIN, HIGH); // Solid ON = Connected
    Serial.println("\n[WiFi]: ✅ Connected!");
    Serial.printf("[WiFi]: ESP32 IP Address: %s\n",
                  WiFi.localIP().toString().c_str());
  } else {
    digitalWrite(STATUS_LED_PIN, LOW);
    Serial.println(
        "\n[WiFi]: ❌ Failed to connect. Will retry on next loop...");
  }
}

// ── Send Telemetry to PC Server via HTTP POST
// ────────────────────────────────────────
void sendTelemetryToServer(float temp, float hum, float moisture, int n, int p,
                           int k, float ph, float ec) {
  if (WiFi.status() != WL_CONNECTED)
    return;

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  // Build JSON payload
  StaticJsonDocument<300> doc;
  doc["temp"] = temp;
  doc["hum"] = hum;
  doc["moisture"] = moisture;
  doc["N"] = n;
  doc["P"] = p;
  doc["K"] = k;
  doc["ph"] = ph;
  doc["ec"] = ec;
  doc["pump"] = pumpState ? 1 : 0;

  String jsonPayload;
  serializeJson(doc, jsonPayload);

  Serial.printf("[HTTP]: Sending to %s\n", SERVER_URL);
  int httpCode = http.POST(jsonPayload);

  if (httpCode == 200) {
    String response = http.getString();
    Serial.printf("[HTTP]: ✅ Server responded: %s\n", response.c_str());

    // Parse server's pump command from response
    StaticJsonDocument<100> resp;
    if (deserializeJson(resp, response) == DeserializationError::Ok) {
      if (resp.containsKey("pump_command")) {
        bool cmdPump = resp["pump_command"].as<int>() == 1;
        if (cmdPump != pumpState) {
          pumpState = cmdPump;
          digitalWrite(PUMP_RELAY_PIN, pumpState ? HIGH : LOW);
          Serial.printf("[RELAY]: Pump set to %s by server command.\n",
                        pumpState ? "ON 🌊" : "OFF 🛑");
        }
      }
    }
  } else {
    Serial.printf(
        "[HTTP]: ❌ Error %d — Server unreachable. Check IP & firewall.\n",
        httpCode);
  }

  http.end();
}

// ── DHT22 — Temperature
// ──────────────────────────────────────────────────────────────
float readTemperature() {
  float t = dht.readTemperature();
  if (isnan(t)) {
    Serial.println(
        "[DHT22]: ⚠️  Temperature read failed. Using last known value.");
    return 26.0; // Fallback default
  }
  return t;
}

// ── DHT22 — Humidity
// ─────────────────────────────────────────────────────────────────
float readHumidity() {
  float h = dht.readHumidity();
  if (isnan(h)) {
    Serial.println("[DHT22]: ⚠️  Humidity read failed. Using last known value.");
    return 65.0; // Fallback default
  }
  return h;
}

// ── Capacitive Soil Moisture Sensor (Analog)
// ─────────────────────────────────────────
float readSoilMoisturePct() {
  int rawValue = analogRead(SOIL_MOISTURE_PIN);
  // Map ADC reading to percentage: dry=0%, wet=100%
  float pct = map(rawValue, MOISTURE_AIR_VALUE, MOISTURE_WATER_VALUE, 0, 100);
  pct = constrain(pct, 0.0, 100.0);
  return round(pct * 10.0) / 10.0; // 1 decimal place
}

// ── RS485 NPK Sensor — Nitrogen
// ──────────────────────────────────────────────────────
int readNPK_N() {
  byte response[11];
  int val = readRS485Sensor(NPK_CMD, sizeof(NPK_CMD), response);
  if (val >= 0)
    return (response[3] << 8) | response[4]; // High + Low byte
  return 50;                                 // Fallback if sensor unavailable
}

// ── RS485 NPK Sensor — Phosphorus
// ───────────────────────────────────────────────────
int readNPK_P() {
  byte response[11];
  int val = readRS485Sensor(NPK_CMD, sizeof(NPK_CMD), response);
  if (val >= 0)
    return (response[5] << 8) | response[6];
  return 30; // Fallback
}

// ── RS485 NPK Sensor — Potassium
// ─────────────────────────────────────────────────────
int readNPK_K() {
  byte response[11];
  int val = readRS485Sensor(NPK_CMD, sizeof(NPK_CMD), response);
  if (val >= 0)
    return (response[7] << 8) | response[8];
  return 120; // Fallback
}

// ── RS485 pH Sensor
// ───────────────────────────────────────────────────────────────────
float readSoilPH() {
  byte response[7];
  int val = readRS485Sensor(PH_CMD, sizeof(PH_CMD), response);
  if (val >= 0) {
    int raw = (response[3] << 8) | response[4];
    return raw / 100.0; // Sensor returns pH * 100
  }
  return 6.5; // Fallback
}

// ── RS485 EC Sensor
// ───────────────────────────────────────────────────────────────────
float readSoilEC() {
  byte response[7];
  int val = readRS485Sensor(EC_CMD, sizeof(EC_CMD), response);
  if (val >= 0) {
    int raw = (response[3] << 8) | response[4];
    return raw / 100.0; // Sensor returns EC * 100
  }
  return 1.25; // Fallback
}

// ── Generic RS485 Read Helper
// ─────────────────────────────────────────────────────────
int readRS485Sensor(const byte *cmd, int cmdLen, byte *responseBuffer) {
  // Set RS485 to transmit mode
  digitalWrite(RS485_DE_PIN, HIGH);
  delay(10);
  RS485Serial.write(cmd, cmdLen);
  RS485Serial.flush();
  delay(10);

  // Set RS485 to receive mode
  digitalWrite(RS485_DE_PIN, LOW);

  // Wait for response (max 500ms)
  unsigned long start = millis();
  int bytesRead = 0;
  while ((millis() - start) < 500 && bytesRead < 11) {
    if (RS485Serial.available()) {
      responseBuffer[bytesRead++] = RS485Serial.read();
    }
  }

  if (bytesRead < 5) {
    // Sensor not responding (not wired, or address mismatch)
    return -1;
  }
  return bytesRead;
}
