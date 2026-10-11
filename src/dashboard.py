import sys
import os
import warnings

# Suppress terminal warnings and extraneous library logs
warnings.filterwarnings('ignore')
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

# Ensure project root directory is on sys.path regardless of execution context
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import streamlit as st
import pandas as pd
import numpy as np
import time

try:
    from src.ml_engine import CropRecommendationEngine
    from src.fertilizer_engine import FertilizerAndTargetCropEngine
    from src.db_manager import FarmBotDatabase
    from src.hardware_manager import get_hardware_manager
except ModuleNotFoundError:
    from ml_engine import CropRecommendationEngine
    from fertilizer_engine import FertilizerAndTargetCropEngine
    from db_manager import FarmBotDatabase
    from hardware_manager import get_hardware_manager

try:
    try:
        from src.voice_assistant import MultilingualVoiceAssistant
    except ModuleNotFoundError:
        from voice_assistant import MultilingualVoiceAssistant
    VOICE_AVAILABLE = True
except Exception:
    VOICE_AVAILABLE = False

# Page Configuration
st.set_page_config(
    page_title="Farm Bot IoT & AI Telemetry Dashboard",
    page_icon="🌾",
    layout="wide"
)

# Initialize Engines & Managers
ml_engine = CropRecommendationEngine()
fert_engine = FertilizerAndTargetCropEngine()
db = FarmBotDatabase()
hw_manager = get_hardware_manager()

# Sidebar Controls
st.sidebar.header("🎛 System Controls & Config")
selected_lang = st.sidebar.selectbox("Voice / Interface Language", [
    "English", "Hindi (हिंदी)", "Kannada (ಕನ್ನಡ)", "Tamil (தமிழ்)", "Telugu (తెలుగు)"
])

# ── Moisture Thresholds with Hysteresis (Configurable) ──────────────────────────────
st.sidebar.subheader("💧 Soil Moisture Pump Thresholds")
c_th1, c_th2 = st.sidebar.columns(2)
with c_th1:
    lower_moist_th = st.number_input("Lower ON Threshold (%)", min_value=10.0, max_value=60.0, value=30.0, step=1.0,
                                     help="If moisture drops BELOW this value, pump turns ON.")
with c_th2:
    upper_moist_th = st.number_input("Upper OFF Threshold (%)", min_value=15.0, max_value=90.0, value=45.0, step=1.0,
                                     help="If moisture reaches or EXCEEDS this value, pump turns OFF.")

if upper_moist_th <= lower_moist_th:
    upper_moist_th = lower_moist_th + 5.0
    st.sidebar.warning(f"Upper threshold auto-adjusted to {upper_moist_th}% for proper hysteresis gap.")

# Sync thresholds with ESP32 firmware
if "last_synced_thresholds" not in st.session_state or st.session_state.last_synced_thresholds != (lower_moist_th, upper_moist_th):
    st.session_state.last_synced_thresholds = (lower_moist_th, upper_moist_th)
    hw_manager.set_moisture_thresholds(lower_moist_th, upper_moist_th)

# ── Water Pump Controls ─────────────────────────────────────────────────────────────
st.sidebar.subheader("🌊 Water Pump Controls")
pump_override = st.sidebar.toggle("Manual Water Pump Override", value=False,
                                  help="Enables manual direct control. When off, pump is controlled automatically by soil moisture hysteresis.")

if "last_pump_override" not in st.session_state or st.session_state.last_pump_override != pump_override:
    st.session_state.last_pump_override = pump_override
    if pump_override:
        hw_manager.set_pump_manual_override(1)
    else:
        hw_manager.set_pump_auto_mode()

# ── Telemetry Source Mode ───────────────────────────────────────────────────────────
st.sidebar.subheader("📡 Telemetry Data Source")
mode_choice = st.sidebar.radio(
    "Data Source Mode",
    ["Auto-Detect Hardware", "Manual Input", "Force Hardware Only"],
    index=0,
    help="Auto-Detect keeps live hardware mode as long as ESP32 is connected via USB/WiFi, and falls back to manual only if genuinely disconnected."
)

# Manual Telemetry Input Controls (available when manual mode is selected or fallback)
with st.sidebar.expander("📝 Manual Sensor Input / Simulation", expanded=(mode_choice == "Manual Input")):
    temp_in = st.number_input("Ambient Temp (°C)", 10.0, 50.0, 26.5)
    hum_in  = st.number_input("Humidity (%)", 20.0, 100.0, 65.0)
    moist_in= st.number_input("Soil Moisture (%)", 5.0, 100.0, 32.0)
    n_in    = st.number_input("Nitrogen N (mg/kg)", 0, 300, 55)
    p_in    = st.number_input("Phosphorus P (mg/kg)", 0, 300, 32)
    k_in    = st.number_input("Potassium K (mg/kg)", 0, 400, 165)
    ph_in   = st.number_input("Soil pH", 3.0, 10.0, 6.4)
    ec_in   = st.number_input("Soil EC (mS/cm)", 0.1, 5.0, 1.25)

manual_telemetry = {
    'temp': temp_in, 'hum': hum_in, 'moisture': moist_in,
    'N': n_in, 'P': p_in, 'K': k_in, 'ph': ph_in, 'ec': ec_in,
    'pump': 1 if (moist_in < lower_moist_th or pump_override) else 0,
    'pump_mode': 'MANUAL' if pump_override else 'AUTO',
    'lower_thresh': lower_moist_th,
    'upper_thresh': upper_moist_th,
    'npk_valid': True,
    'npk_status': 'OK'
}

# Resolve active telemetry based on hardware connectivity and selected mode
telemetry, is_hardware_active, status_message = hw_manager.get_effective_telemetry(
    manual_telemetry, mode=mode_choice
)

# Apply manual pump override in software representation if active
if pump_override:
    telemetry['pump'] = 1
    telemetry['pump_mode'] = 'MANUAL'

# Hardware Status Badge in Sidebar
if is_hardware_active:
    if "NPK Sensor Not Responding" in status_message:
        st.sidebar.warning(f"🟡 **{status_message}**")
    else:
        st.sidebar.success(f"🟢 **{status_message}**")
else:
    st.sidebar.info(f"⚪ **{status_message}**")

# Auto-refresh checkbox
auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh live data (every 3s)", value=True)

# Header Title & Live Status Banner
st.title("🌾 Farm Bot: Intelligent Agriculture Dashboard")
if is_hardware_active:
    if "NPK Sensor Not Responding" in status_message:
        st.warning(f"⚡ **Live Hardware Active:** {status_message}. Soil moisture and water pump relay are fully active. Please verify RS485 module wiring and 12V supply.")
    else:
        st.success(f"⚡ **Live Hardware Active:** {status_message} — Sensor readings and physical pump relay are synchronized!")
else:
    st.info(f"ℹ️ **Current Mode:** {status_message} — Connect your ESP32 via USB Serial or WiFi to stream live sensor readings.")

st.markdown("---")

def safe_metric(val, unit="", default="--"):
    if val is None:
        return default
    try:
        fval = float(val)
        return f"{fval:.1f} {unit}".strip()
    except (ValueError, TypeError):
        return default

# Real-Time Telemetry Cards
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Atmospheric Temp", safe_metric(telemetry.get('temp'), "°C"), "Live Sensor" if is_hardware_active else "Manual")
col2.metric("Relative Humidity", safe_metric(telemetry.get('hum'), "%"), "Live Sensor" if is_hardware_active else "Manual")

# Moisture with delta showing relation to hysteresis thresholds
raw_m = telemetry.get('moisture')
if raw_m is not None:
    try:
        moist_val = float(raw_m)
        if moist_val < lower_moist_th:
            moist_delta = f"Low (<{lower_moist_th:.0f}%) -> Pump ON"
        elif moist_val >= upper_moist_th:
            moist_delta = f"Satisfied (>{upper_moist_th:.0f}%) -> Pump OFF"
        else:
            moist_delta = f"Hysteresis Zone ({lower_moist_th:.0f}%-{upper_moist_th:.0f}%)"
    except Exception:
        moist_val = 0.0
        moist_delta = "Normal"
else:
    moist_val = 0.0
    moist_delta = "Sensor Unavailable"

col3.metric("Soil Moisture", safe_metric(raw_m, "%"), delta=moist_delta)

# NPK Display (Real sensor readings or -- if unavailable)
n_str = f"{telemetry['N']}" if telemetry.get('N') is not None else "--"
p_str = f"{telemetry['P']}" if telemetry.get('P') is not None else "--"
k_str = f"{telemetry['K']}" if telemetry.get('K') is not None else "--"
npk_tag = "Live RS485 NPK" if (is_hardware_active and telemetry.get('npk_valid', False)) else ("No Sensor" if is_hardware_active else "Manual")
col4.metric("Soil N - P - K (mg/kg)", f"{n_str} - {p_str} - {k_str}", npk_tag)

# Pump status with mode
pump_is_on = (telemetry.get('pump', 0) == 1)
pump_mode_str = telemetry.get('pump_mode', 'AUTO')
pump_label = "ON 🌊" if pump_is_on else "OFF 🛑"
col5.metric("Water Pump Relay", pump_label, f"Mode: {pump_mode_str}")

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

    # Automatically send the top predicted crops to the ESP32 so the 16x2 LCD displays them
    if is_hardware_active:
        crop_names = [c['crop'] for c in top_crops]
        hw_manager.send_crop_recommendations(crop_names)

    c1, c2, c3 = st.columns(3)
    for i, crop_info in enumerate(top_crops):
        col = [c1, c2, c3][i]
        with col:
            st.subheader(f"Rank #{i+1}: {crop_info['crop']}")
            score_clamped = max(0, min(100, int(crop_info.get('suitability_score_pct', 0))))
            st.progress(score_clamped)
            st.write(f"**Suitability Score:** {crop_info['suitability_score_pct']}%")
            st.write(f"**ML Model Confidence:** {crop_info['model_confidence_pct']}%")
            st.write(f"**Expected Yield:** {crop_info['estimated_yield_tons_per_acre']} Tons/Acre")
            st.info(f"**Agronomic Rationale:** {crop_info['rationale']}")

with tab2:
    st.header("Target Crop Goal Mode & Soil Deficit Analyzer")
    target_crop = st.selectbox("Select Target Crop to Cultivate", [
        "Paddy", "Wheat", "Maize", "Cotton", "Sugarcane", "Groundnut",
        "Tomato", "Onion", "Potato", "Chili", "Banana", "Millets"
    ])

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

    # Localized sample quick question chips
    SAMPLE_QUESTIONS = {
        'en': [
            "What crop should I grow?",
            "What is the soil moisture?",
            "What fertilizer should I use?",
            "Is the water pump on?",
            "What is the soil pH and fertility?",
            "Can I grow Paddy?",
            "How is my farm overall?"
        ],
        'hi': [
            "फसल कौन सी लगानी चाहिए?",
            "मिट्टी में नमी कितनी है?",
            "खाद कौन सी डालनी चाहिए?",
            "क्या पानी का पंप चालू है?",
            "मिट्टी का पीएच और पोषक तत्व कैसे हैं?",
            "क्या मैं धान उगा सकता हूँ?",
            "खेत का संक्षिप्त हाल बताइए"
        ],
        'kn': [
            "ಯಾವ ಬೆಳೆ ಬೆಳೆಯಬೇಕು?",
            "ಮಣ್ಣಿನ ತೇವಾಂಶ ಎಷ್ಟಿದೆ?",
            "ಯಾವ ಗೊಬ್ಬರ ಹಾಕಬೇಕು?",
            "ನೀರಿನ ಪಂಪ್ ಚಾಲನೆಯಲ್ಲಿದೆಯೇ?",
            "ಮಣ್ಣಿನ ಪಿಹೆಚ್ ಮತ್ತು ಪೋಷಕಾಂಶಗಳ ಮಟ್ಟವೇನು?",
            "ಭತ್ತ ಬೆಳೆಯಬಹುದೇ?",
            "ತೋಟದ ಸಮಗ್ರ ವಿವರ ತಿಳಿಸಿ"
        ],
        'ta': [
            "என்ன பயிர் செய்யலாம்?",
            "மண்ணின் ஈரப்பதம் என்ன?",
            "உரங்கள் என்ன போட வேண்டும்?",
            "தண்ணீர் பம்ப் ஓடுகிறதா?",
            "மண்ணின் பி.எச் மற்றும் சத்துக்கள் எப்படி உள்ளது?",
            "நெல் பயிரிடலாமா?",
            "பண்ணை நிலை அறிக்கை தாருங்கள்"
        ],
        'te': [
            "ఏ పంట వేయాలి?",
            "నేలలో తేమ ఎంత శాతం ఉంది?",
            "ఎరువులు ఏమి వేయాలి?",
            "నీటి పంపు ఆన్ లో ఉందా?",
            "నేల పి.హెచ్ మరియు పోషకాల స్థాయి ఏమిటి?",
            "వరి సాగు చేయవచ్చా?",
            "పొలం సమగ్ర వివరాలు చెప్పండి"
        ]
    }

    st.subheader("💡 Quick Sample Questions (Click to Ask)")
    curr_samples = SAMPLE_QUESTIONS.get(lang_code, SAMPLE_QUESTIONS['en'])
    
    # Store active query in session state
    if "active_voice_query" not in st.session_state:
        st.session_state.active_voice_query = curr_samples[0]

    # Grid of quick question buttons
    q_cols = st.columns(len(curr_samples))
    for idx, sample_q in enumerate(curr_samples):
        with q_cols[idx]:
            if st.button(sample_q, key=f"sample_q_{idx}"):
                st.session_state.active_voice_query = sample_q

    voice_query = st.text_input("Ask Farm Bot a question in your chosen language or English:", value=st.session_state.active_voice_query)

    ask_clicked = st.button("🎙 Ask Farm Bot & Announce Answer", use_container_width=True)

    if ask_clicked:
        st.write("🎙 Processing Query...")
        if VOICE_AVAILABLE:
            assistant = MultilingualVoiceAssistant(default_lang_code=lang_code)
            resp = assistant.process_query(voice_query, telemetry, ml_engine, fert_engine)
            st.success(f"🤖 **Farm Bot ({selected_lang}):** {resp}")
            try:
                assistant.speak(resp)
                st.info(f"🔊 Audio announced in **{selected_lang}** through your speakers.")
            except Exception as e:
                st.warning(f"Audio playback note: {e}")
        else:
            st.info(f"🤖 **Response:** Query received: '{voice_query}'")


# Auto-refresh trigger for live hardware streaming
if auto_refresh:
    time.sleep(3)
    st.rerun()
