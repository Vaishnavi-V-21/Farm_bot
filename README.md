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

| Sensor | ESP32 Pin | Notes |
|---|---|---|
| DHT22 DATA | GPIO 4 | 10kΩ pull-up to 3.3V |
| Soil Moisture | GPIO 34 | Analog (ADC1) |
| NPK/pH/EC RS485 RX | GPIO 16 | UART2 |
| NPK/pH/EC RS485 TX | GPIO 17 | UART2 |
| RS485 DE/RE | GPIO 5 | Direction control |
| Pump Relay IN | GPIO 26 | HIGH = ON |

### Flash Steps
1. Open `esp32_farm_bot/esp32_farm_bot.ino` in **Arduino IDE 2.x**
2. Set your WiFi SSID/password and your **PC's local IP** in the config block
3. Board: `Tools → Board → ESP32 Dev Module`
4. Click **Upload**

### Run the Receiver API (on PC)
```bash
python sensor_receiver.py
```
> Listens on port `5000` for ESP32 JSON payloads and logs them to `data/farm_bot.db`

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
