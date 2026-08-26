"""
=====================================================================================
Project Title : Farm Bot: Intelligent Farming with Fertility & Crop Recommendation
File          : src/dashboard.py
Description   : Streamlit Interactive Real-Time Web Dashboard for IoT Telemetry,
                Machine Learning Crop Recommendation, Fertilizer Deficit Calculation,
                Live Gauge Displays, and Manual Pump Override.
Run Command   : streamlit run src/dashboard.py
=====================================================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
import time
from src.ml_engine import CropRecommendationEngine
from src.fertilizer_engine import FertilizerAndTargetCropEngine
from src.db_manager import FarmBotDatabase
try:
    from src.voice_assistant import MultilingualVoiceAssistant
    VOICE_AVAILABLE = True
except Exception:
    VOICE_AVAILABLE = False

# Page Configuration
st.set_page_config(
    page_title="Farm Bot IoT & AI Telemetry Dashboard",
    page_icon="🌾",
    layout="wide"
)

# Initialize Engines
ml_engine = CropRecommendationEngine()
fert_engine = FertilizerAndTargetCropEngine()
db = FarmBotDatabase()

# Header Title
st.title("🌾 Farm Bot: Intelligent Agriculture Dashboard")
st.markdown("---")

# Sidebar Controls
st.sidebar.header("🎛 System Controls & Config")
selected_lang = st.sidebar.selectbox("Voice / Interface Language", ["English", "Hindi (हिंदी)", "Kannada (ಕನ್ನಡ)", "Tamil (தமிழ்)", "Telugu (తెలుగు)"])
pump_override = st.sidebar.toggle("Manual Water Pump Override", value=False)
moisture_threshold = st.sidebar.slider("Soil Moisture Alert Threshold (%)", 10, 80, 35)

# Simulated / Live Hardware Telemetry
st.sidebar.subheader("📡 Simulated Live Telemetry Feed")
temp_in = st.sidebar.number_input("Ambient Temp (°C)", 10.0, 50.0, 26.5)
hum_in  = st.sidebar.number_input("Humidity (%)", 20.0, 100.0, 65.0)
moist_in= st.sidebar.number_input("Soil Moisture (%)", 5.0, 100.0, 32.0)
n_in    = st.sidebar.number_input("Nitrogen N (mg/kg)", 0, 300, 55)
p_in    = st.sidebar.number_input("Phosphorus P (mg/kg)", 0, 300, 32)
k_in    = st.sidebar.number_input("Potassium K (mg/kg)", 0, 400, 165)
ph_in   = st.sidebar.number_input("Soil pH", 3.0, 10.0, 6.4)
ec_in   = st.sidebar.number_input("Soil EC (mS/cm)", 0.1, 5.0, 1.25)

telemetry = {
    'temp': temp_in, 'hum': hum_in, 'moisture': moist_in,
    'N': n_in, 'P': p_in, 'K': k_in, 'ph': ph_in, 'ec': ec_in,
    'pump': 1 if (moist_in < moisture_threshold or pump_override) else 0
}

# Log to database
db.log_telemetry(telemetry)

# Real-Time Telemetry Cards
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Atmospheric Temp", f"{telemetry['temp']} °C")
col2.metric("Relative Humidity", f"{telemetry['hum']} %")
col3.metric("Soil Moisture", f"{telemetry['moisture']} %", delta="-ALERT Low" if telemetry['moisture'] < moisture_threshold else "Normal")
col4.metric("Soil pH / EC", f"{telemetry['ph']} pH", f"{telemetry['ec']} mS/cm")
col5.metric("Water Pump Relay", "ON 🌊" if telemetry['pump'] else "OFF 🛑")

st.markdown("---")

# Main Section Layout (Tabs)
tab1, tab2, tab3, tab4 = st.tabs([
    "🌱 Mode 1: Smart Crop Recommendation",
    "🎯 Mode 2: Target Crop Goal Mode",
    "📊 Historical Telemetry Logs",
    "🎙 Voice Assistant Interface"
])

with tab1:
    st.header("Smart Machine Learning Crop Recommendation")
    top_crops = ml_engine.predict_top_crops(telemetry, top_n=3)

    c1, c2, c3 = st.columns(3)
    for i, crop_info in enumerate(top_crops):
        col = [c1, c2, c3][i]
        with col:
            st.subheader(f"Rank #{i+1}: {crop_info['crop']}")
            st.progress(int(crop_info['suitability_score_pct']))
            st.write(f"**Suitability Score:** {crop_info['suitability_score_pct']}%")
            st.write(f"**ML Model Confidence:** {crop_info['model_confidence_pct']}%")
            st.write(f"**Expected Yield:** {crop_info['estimated_yield_tons_per_acre']} Tons/Acre")
            st.info(f"**Agronomic Rationale:** {crop_info['rationale']}")

with tab2:
    st.header("Target Crop Goal Mode & Soil Deficit Analyzer")
    target_crop = st.selectbox("Select Target Crop to Cultivate", ["Paddy", "Wheat", "Maize", "Cotton", "Sugarcane", "Groundnut", "Tomato", "Onion", "Potato", "Chili", "Banana", "Millets"])

    if st.button("Analyze Soil Deficits for Selected Target Crop"):
        result = fert_engine.analyze_target_crop_goal(telemetry, target_crop)

        if result['status'] == 'SUCCESS':
            if result['is_currently_suitable']:
                st.success("✅ Soil is currently SUITABLE for cultivating " + target_crop)
            else:
                st.warning("⚠️ Soil is currently UNSUITABLE. Action required below:")
                for r in result['unsuitable_reasons']:
                    st.write(f"• {r}")

            st.subheader("Required Chemical Fertilizers (kg / acre)")
            f = result['chemical_fertilizers']
            fc1, fc2, fc3 = st.columns(3)
            fc1.metric("Urea (46% N)", f"{f['urea_kg_per_acre']} kg/acre")
            fc2.metric("SSP (16% P2O5)", f"{f['ssp_kg_per_acre']} kg/acre")
            fc3.metric("MOP (60% K2O)", f"{f['mop_kg_per_acre']} kg/acre")

            st.subheader("Organic Alternatives & Soil Amendments")
            for org in result['organic_alternatives']:
                st.write(f"🌱 {org}")

            st.subheader("pH Adjustment Analysis")
            st.write(result['ph_analysis']['recommendation'])

            st.info(f"⏳ Estimated Soil Preparation Time: **{result['est_prep_time_days']} Days**")

with tab3:
    st.header("Real-Time Telemetry & Historical Trends")
    rows = db.fetch_recent_telemetry(30)
    if rows:
        df_log = pd.DataFrame(rows, columns=['Timestamp', 'Temp', 'Humidity', 'Moisture', 'N', 'P', 'K', 'EC', 'pH', 'Pump'])
        st.line_chart(df_log[['Moisture', 'Temp', 'Humidity']])
        st.dataframe(df_log)

with tab4:
    st.header("Multilingual Voice Assistant Interface")
    st.write(f"Current Assistant Language: **{selected_lang}**")
    
    LANG_MAP = {
        "English": "en",
        "Hindi (हिंदी)": "hi",
        "Kannada (ಕನ್ನಡ)": "kn",
        "Tamil (தமிழ்)": "ta",
        "Telugu (తెలుగు)": "te"
    }
    lang_code = LANG_MAP.get(selected_lang, "en")

    voice_query = st.text_input("Ask Farm Bot a question (e.g. 'What crop should I grow?', 'What is soil moisture?', 'Is pump on?'):", "What crop should I grow?")
    
    if st.button("🎙 Ask Farm Bot & Generate Response"):
        st.write("🎙 Processing Query...")
        if VOICE_AVAILABLE:
            assistant = MultilingualVoiceAssistant(default_lang_code=lang_code)
            resp = assistant.process_query(voice_query, telemetry, ml_engine, fert_engine)
            st.info(f"🤖 **Farm Bot Answer:** {resp}")
            try:
                assistant.speak(resp)
                st.success("🔊 Audio response played through speakers.")
            except Exception as e:
                st.warning(f"Audio playback notice: {e}")
        else:
            st.info(f"🤖 **Response:** Simulated query received: '{voice_query}'")

