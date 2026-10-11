# 🌾 Farm Bot — Intelligent Agriculture & Crop Recommendation System

An AI-powered precision farming platform combining **IoT sensor telemetry**, **Machine Learning crop recommendation**, **fertilizer deficit analysis**, and a **multilingual voice assistant** — all in a real-time Streamlit web dashboard.

---

## 📦 Project Structure

```
FARM_BOT/
├── run.py                      # ← One-click master launcher
├── run.bat                     # ← Windows double-click launcher
├── sensor_receiver.py          # ← Flask API for ESP32 data ingestion
├── requirements.txt            # ← Python dependencies
├── esp32_farm_bot/
│   └── esp32_farm_bot.ino      # ← Arduino firmware for ESP32 sensor node
└── src/
    ├── dashboard.py            # ← Streamlit interactive dashboard
    ├── ml_engine.py            # ← Random Forest crop recommendation AI
    ├── fertilizer_engine.py    # ← Fertilizer deficit & pH analyzer
    ├── dataset_generator.py    # ← Agronomic dataset + ML model trainer
    ├── db_manager.py           # ← SQLite database manager
    └── voice_assistant.py      # ← Multilingual voice assistant (EN/HI/KN/TA/TE)
```

---

## 🚀 Quick Start (PC Dashboard)

### Prerequisites
- Python 3.10+
- pip

### Run
```bash
python run.py
```
> This automatically installs dependencies, trains the ML model, initializes the database, and launches the Streamlit dashboard at `http://localhost:8501`.

---

## 🔌 ESP32 Hardware Setup

### Sensor Wiring

| Sensor / Actuator | ESP32 Pin | Type | Notes |
|---|---|---|---|
| DHT22 (Temp & Humidity) | GPIO 4 | Digital I/O | 10kΩ pull-up to 3.3V |
| Soil Moisture (Capacitive) | GPIO 34 | Analog In (ADC1) | 0% dry ~ 100% wet |
| MAX485 RO (UART2 RX) | GPIO 16 | Hardware UART2 | Connect to MAX485 RO |
| MAX485 DI (UART2 TX) | GPIO 17 | Hardware UART2 | Connect to MAX485 DI |
| MAX485 DE / RE | GPIO 5 | Digital Out | Tie DE & RE together (HIGH=TX, LOW=RX) |
| Water Pump Relay IN | GPIO 26 | Digital Out | Configurable Active HIGH / Active LOW |
| LCD 16×2 I2C SDA | GPIO 21 | Hardware I2C | PCF8574 backpack (0x27 / 0x3F) |
| LCD 16×2 I2C SCL | GPIO 22 | Hardware I2C | PCF8574 backpack (0x27 / 0x3F) |
| Status Indicator LED | GPIO 2 | Digital Out | Onboard LED |

### Connection Methods

#### 🔌 Method 1: Direct USB Cable (Plug & Play — Recommended)
1. Plug your ESP32 into your laptop via USB.
2. Launch the dashboard (`python run.py`).
3. The dashboard **auto-detects** your USB COM port, reads live sensor streams, and switches to `🟢 Live Hardware Connected (USB Serial)`.
4. If you unplug the USB cable, it instantly falls back to `⚪ Hardware Disconnected (Using Manual Input)`.

#### 📶 Method 2: WiFi IoT Connection
1. Set your WiFi credentials in `esp32_farm_bot/esp32_farm_bot.ino`.
2. Set `SERVER_URL` to `http://<YOUR_PC_IP>:5000/api/telemetry`.
3. When you run `python run.py`, the WiFi receiver starts automatically in the background on port `5000`.
4. Telemetry sent over WiFi is logged and displayed live on the dashboard.

---

## 🌱 Features

- **Smart Crop Recommendation** — Top 3 crops with ML confidence, suitability score & yield
- **Target Crop Goal Mode** — Soil deficit analysis + exact fertilizer dosage (Urea / SSP / MOP)
- **Organic Alternatives** — Vermicompost, FYM, Bio-fertilizers with application rates
- **pH Amendment Advisor** — Lime for acidic / Gypsum for alkaline soils
- **Real-Time Telemetry** — Live sensor cards + historical trend charts
- **Water Pump Automation** — Auto-triggers irrigation below moisture threshold
- **Multilingual Voice Assistant** — Responds in English, Hindi, Kannada, Tamil, Telugu

---

## 🤖 ML Model

- **Algorithm:** Random Forest Classifier (winner of 4-algorithm benchmark)
- **Accuracy:** ~88.3% (5-Fold CV: 88.9%)
- **Features:** N, P, K, Temperature, Humidity, Soil pH, Soil Moisture
- **Crops Supported:** 12 major Indian crops (Paddy, Wheat, Maize, Cotton, Sugarcane, Groundnut, Tomato, Onion, Potato, Chili, Banana, Millets)

---

## 📋 Requirements

```
streamlit, scikit-learn, pandas, numpy, pygame, gTTS, SpeechRecognition, flask
```

---

## 👩‍💻 Authors

Built with ❤️ for intelligent precision farming.
