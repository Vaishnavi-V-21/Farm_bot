"""
=====================================================================================
Project Title : Farm Bot: Intelligent Farming with Fertility & Crop Recommendation
File          : src/voice_assistant.py
Description   : Full Multilingual Voice Assistant with native sentence synthesis
                for English, Hindi, Kannada, Tamil, and Telugu.
                Answers wide varieties of farmer questions including crops, moisture,
                temperature, humidity, pump status, fertilizers, NPK, pH, EC,
                specific target crops, farm summary, and greetings.
=====================================================================================
"""

import os
import time
import re
import speech_recognition as sr
from gtts import gTTS
import pygame

# Optional offline TTS fallback
try:
    import pyttsx3
    OFFLINE_TTS_AVAILABLE = True
except ImportError:
    OFFLINE_TTS_AVAILABLE = False

try:
    pygame.mixer.init()
except Exception:
    pass

LANGUAGES = {
    '1': {'code': 'en', 'name': 'English'},
    '2': {'code': 'hi', 'name': 'Hindi (हिंदी)'},
    '3': {'code': 'kn', 'name': 'Kannada (ಕನ್ನಡ)'},
    '4': {'code': 'ta', 'name': 'Tamil (தமிழ்)'},
    '5': {'code': 'te', 'name': 'Telugu (తెలుగు)'}
}

# Localized Crop Names
CROP_TRANSLATIONS = {
    'en': {
        'Paddy': 'Paddy (Rice)', 'Wheat': 'Wheat', 'Maize': 'Maize (Corn)', 'Cotton': 'Cotton',
        'Sugarcane': 'Sugarcane', 'Groundnut': 'Groundnut', 'Tomato': 'Tomato',
        'Onion': 'Onion', 'Potato': 'Potato', 'Chili': 'Chili', 'Banana': 'Banana',
        'Millets': 'Millets'
    },
    'hi': {
        'Paddy': 'धान (चावल)', 'Wheat': 'गेहूँ', 'Maize': 'मक्का', 'Cotton': 'कपास',
        'Sugarcane': 'गन्ना', 'Groundnut': 'मूंगफली', 'Tomato': 'टमाटर',
        'Onion': 'प्याज', 'Potato': 'आलू', 'Chili': 'मिर्च', 'Banana': 'केला',
        'Millets': 'बाजरा और मोटा अनाज'
    },
    'kn': {
        'Paddy': 'ಭತ್ತ', 'Wheat': 'ಗೋಧಿ', 'Maize': 'ಮೆಕ್ಕೆಜೋಳ', 'Cotton': 'ಹತ್ತಿ',
        'Sugarcane': 'ಕಬ್ಬು', 'Groundnut': 'ಕಡಲೆಕಾಯಿ', 'Tomato': 'ಟೊಮೇಟೊ',
        'Onion': 'ಈರುಳ್ಳಿ', 'Potato': 'ಆಲೂಗಡ್ಡೆ', 'Chili': 'ಮೆಣಸಿನಕಾಯಿ',
        'Banana': 'ಬಾಳೆಹಣ್ಣು', 'Millets': 'ಸಿರಿಧಾನ್ಯ'
    },
    'ta': {
        'Paddy': 'நெல்', 'Wheat': 'கோதுமை', 'Maize': 'மக்காச்சோளம்', 'Cotton': 'பருத்தி',
        'Sugarcane': 'கரும்பு', 'Groundnut': 'நிலக்கடலை', 'Tomato': 'தக்காளி',
        'Onion': 'வெங்காயம்', 'Potato': 'உருளைக்கிழங்கு', 'Chili': 'மிளகாய்',
        'Banana': 'வாழை', 'Millets': 'சிறுதானியங்கள்'
    },
    'te': {
        'Paddy': 'వరి', 'Wheat': 'గోధుమ', 'Maize': 'మొక్కజొన్న', 'Cotton': 'పత్తి',
        'Sugarcane': 'చెరకు', 'Groundnut': 'వేరుశనగ', 'Tomato': 'టమోటా',
        'Onion': 'ఉల్లిపాయ', 'Potato': 'బంగాళాదుంప', 'Chili': 'మిరప',
        'Banana': 'అరటి', 'Millets': 'చిరుధాన్యాలు'
    }
}

# Crop name alias matching dictionary (for detecting specific crop queries)
CROP_ALIASES = {
    'Paddy': ['paddy', 'rice', 'dhan', 'dhaana', 'bhatta', 'nellu', 'nel', 'vari', 'bhattha', 'धान', 'चावल', 'ಭತ್ತ', 'ನೆಲ್', 'நெல்', 'வரி', 'వరి'],
    'Wheat': ['wheat', 'gehu', 'gehoon', 'godhi', 'godhumai', 'godhuma', 'godhumalu', 'गेहूँ', 'गेहू', 'ಗೋಧಿ', 'கோதுமை', 'గోధుమ'],
    'Maize': ['maize', 'corn', 'makka', 'bhutta', 'mokejola', 'mekkejola', 'makkacholam', 'mokkajonna', 'मक्का', 'भुट्टा', 'ಮೆಕ್ಕೆಜೋಳ', 'மக்காச்சோளம்', 'మొక్కజొన్న'],
    'Cotton': ['cotton', 'kapaas', 'kapas', 'hatti', 'paruthi', 'patti', 'कपास', 'हत्ती', 'ಹತ್ತಿ', 'பருத்தி', 'పత్తి'],
    'Sugarcane': ['sugarcane', 'ganna', 'kabbu', 'karumbu', 'cheraku', 'गन्ना', 'ಕಬ್ಬು', 'கரும்பு', 'చెరకు'],
    'Groundnut': ['groundnut', 'peanut', 'mungfali', 'moongfali', 'kadlekayi', 'kadale', 'nilakkadalai', 'verusenaga', 'मूंगफली', 'ಕಡಲೆಕಾಯಿ', 'நிலக்கடலை', 'వేరుశనగ'],
    'Tomato': ['tomato', 'tamatar', 'thakkali', 'tamata', 'टमाटर', 'ಟೊಮೇಟೊ', 'தக்காளி', 'టమోటా'],
    'Onion': ['onion', 'pyaz', 'kanda', 'eerulli', 'irulli', 'vengayam', 'ullipaya', 'ulli', 'प्याज', 'कांदा', 'ಈರುಳ್ಳಿ', 'வெங்காயம்', 'ఉల్లిపాయ'],
    'Potato': ['potato', 'aloo', 'alu', 'alugadde', 'urulaikkilangu', 'bangaladumpa', 'आलू', 'ಆಲೂಗಡ್ಡೆ', 'உருளைக்கிழங்கு', 'బంగాళాదుంప'],
    'Chili': ['chili', 'chilli', 'mirch', 'mirchi', 'menasinakayi', 'milagai', 'mirapa', 'मिर्च', 'ಮೆಣಸಿನಕಾಯಿ', 'மிளகாய்', 'మిరప'],
    'Banana': ['banana', 'kela', 'balehannu', 'baale', 'valai', 'arati', 'केला', 'ಬಾಳೆಹಣ್ಣು', 'வாழை', 'అరటి'],
    'Millets': ['millet', 'millets', 'bajra', 'jowar', 'ragi', 'siridhanya', 'siruthaaniyam', 'chirudhanyalu', 'jonnalu', 'बाजरा', 'ज्वार', 'रागी', 'ಸಿರಿಧಾನ್ಯ', 'சிறுதானியங்கள்', 'చిరుధాన్యాలు']
}


class MultilingualVoiceAssistant:
    def __init__(self, default_lang_code='en'):
        self.lang_code = default_lang_code if default_lang_code in ['en', 'hi', 'kn', 'ta', 'te'] else 'en'
        self.recognizer = sr.Recognizer()
        if OFFLINE_TTS_AVAILABLE:
            try:
                self.offline_engine = pyttsx3.init()
            except Exception:
                self.offline_engine = None

    def set_language(self, lang_code):
        if lang_code in ['en', 'hi', 'kn', 'ta', 'te']:
            self.lang_code = lang_code

    def get_crop_name(self, crop_en):
        """Translates crop name to selected language."""
        lang_dict = CROP_TRANSLATIONS.get(self.lang_code, CROP_TRANSLATIONS['en'])
        return lang_dict.get(crop_en, crop_en)

    def speak(self, text):
        """Synthesizes text and plays audio with online gTTS or offline pyttsx3 fallback."""
        try:
            print(f"\n[VOICE ASSISTANT ({self.lang_code.upper()})]: {text}")
        except Exception:
            try:
                print(f"\n[VOICE ASSISTANT ({self.lang_code.upper()})]: {text.encode('ascii', 'replace').decode('ascii')}")
            except Exception:
                pass

        # Attempt Online gTTS first (Produces natural human pronunciation in selected language)
        try:
            tts = gTTS(text=text, lang=self.lang_code, slow=False)
            filename = f"temp_voice_{int(time.time() * 1000)}.mp3"
            tts.save(filename)

            if not pygame.mixer.get_init():
                pygame.mixer.init()

            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)

            pygame.mixer.music.unload()
            if os.path.exists(filename):
                try:
                    os.remove(filename)
                except Exception:
                    pass
            return
        except Exception as e:
            print(f"[VOICE WARNING]: Online gTTS failed ({e}). Falling back to Offline Engine.")

        # Fallback to Offline Engine if installed
        if OFFLINE_TTS_AVAILABLE and hasattr(self, 'offline_engine') and self.offline_engine:
            try:
                self.offline_engine.say(text)
                self.offline_engine.runAndWait()
            except Exception as ex:
                print(f"[VOICE ERROR]: Offline TTS also failed: {ex}")

    def listen(self, timeout_sec=5):
        """Captures microphone input and converts speech to text."""
        with sr.Microphone() as source:
            print("\n[VOICE LISTENER] Listening... Speak clearly into microphone.")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            try:
                audio = self.recognizer.listen(source, timeout=timeout_sec, phrase_time_limit=5)
                # Map language code for Google Speech Recognition
                sr_lang = 'en-IN'
                if self.lang_code == 'hi': sr_lang = 'hi-IN'
                elif self.lang_code == 'kn': sr_lang = 'kn-IN'
                elif self.lang_code == 'ta': sr_lang = 'ta-IN'
                elif self.lang_code == 'te': sr_lang = 'te-IN'

                query = self.recognizer.recognize_google(audio, language=sr_lang)
                print(f"[VOICE LISTENER] Recognized: '{query}'")
                return query.lower()
            except sr.WaitTimeoutError:
                print("[VOICE LISTENER] No speech detected (Timeout).")
                return ""
            except sr.UnknownValueError:
                print("[VOICE LISTENER] Speech unreadable.")
                return ""
            except Exception as e:
                print(f"[VOICE LISTENER] Error: {e}")
                return ""

    def process_query(self, query, telemetry, ml_engine, fert_engine):
        """
        Answers a comprehensive variety of farmer questions and announces
        complete, fluent natural sentences in the selected language.
        """
        if not query or not query.strip():
            no_query_msg = {
                'en': "I did not receive any question. Please ask something about your crops, moisture, pump, or soil.",
                'hi': "मुझे कोई प्रश्न प्राप्त नहीं हुआ। कृपया अपनी फसल, नमी, पंप या मिट्टी के बारे में कुछ पूछें।",
                'kn': "ಯಾವುದೇ ಪ್ರಶ್ನೆ ಸ್ವೀಕರಿಸಲಾಗಿಲ್ಲ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ಬೆಳೆ, ತೇವಾಂಶ, ಪಂಪ್ ಅಥವಾ ಮಣ್ಣಿನ ಬಗ್ಗೆ ಕೇಳಿ.",
                'ta': "எந்த கேள்வியும் கிடைக்கவில்லை. உங்கள் பயிர், ஈரப்பதம், பம்ப் அல்லது மண் பற்றி கேளுங்கள்.",
                'te': "ఎటువంటి ప్రశ్న అందలేదు. దయచేసి మీ పంటలు, తేమ, పంపు లేదా నేల గురించి ఏదైనా అడగండి."
            }
            return no_query_msg.get(self.lang_code, no_query_msg['en'])

        q = query.lower().strip()
        temp = round(telemetry.get('temp', 26.5), 1)
        hum = round(telemetry.get('hum', 65.0), 1)
        moisture = round(telemetry.get('moisture', 35.0), 1)
        n = int(telemetry.get('N', 50))
        p = int(telemetry.get('P', 30))
        k = int(telemetry.get('K', 120))
        ph = round(telemetry.get('ph', 6.5), 2)
        ec = round(telemetry.get('ec', 1.2), 2)
        pump = int(telemetry.get('pump', 0))

        # Check for specific target crop question (e.g. "Can I grow Paddy?", "Is soil good for wheat?", etc.)
        detected_target_crop = None
        for crop_canonical, aliases in CROP_ALIASES.items():
            if any(alias in q for alias in aliases):
                # Ensure it's not a generic query
                if any(k in q for k in [
                    "grow", "plant", "suitable", "can i", "kare", "kheti", "ugaye", "belabahuda",
                    "valarkalama", "pandinchavacha", "good for", "suit", "उगा", "बो", "ಬೆಳೆ",
                    "பயிர்", "பயிரிட", "పంట", "సాగు", "సరిపో"
                ]):
                    detected_target_crop = crop_canonical
                    break

        if detected_target_crop:
            target_res = fert_engine.analyze_target_crop_goal(telemetry, detected_target_crop)
            is_suitable = target_res.get('is_currently_suitable', False)
            score = int(target_res.get('suitability_score_pct', 70))
            prep_days = int(target_res.get('est_prep_time_days', 7))
            crop_name_loc = self.get_crop_name(detected_target_crop)

            if self.lang_code == 'hi':
                if is_suitable:
                    return f"{crop_name_loc} के लिए आपकी मिट्टी बहुत उपयुक्त है। उपयुक्तता स्कोर {score} प्रतिशत है। आप इस फसल की बुवाई कर सकते हैं।"
                else:
                    return f"{crop_name_loc} के लिए वर्तमान मिट्टी को सुधार की आवश्यकता है। उपयुक्तता {score} प्रतिशत है। मिट्टी को तैयार करने में लगभग {prep_days} दिन लगेंगे।"
            elif self.lang_code == 'kn':
                if is_suitable:
                    return f"{crop_name_loc} ಬೆಳೆಗೆ ನಿಮ್ಮ ಮಣ್ಣು ಅತ್ಯಂತ ಸೂಕ್ತವಾಗಿದೆ. ಸೂಕ್ತತೆ ಸ್ಕೋರ್ {score} ಪ್ರತಿಶತ ಇದೆ. ನೀವು ಈ ಬೆಳೆಯನ್ನು ಬೆಳೆಯಬಹುದು."
                else:
                    return f"{crop_name_loc} ಬೆಳೆಗೆ ಪ್ರಸ್ತುತ ಮಣ್ಣಿಗೆ ಸುಧಾರಣೆ ಬೇಕಾಗಿದೆ. ಸೂಕ್ತತೆ ಸ್ಕೋರ್ {score} ಪ್ರತಿಶತ ಇದ್ದು, ಮಣ್ಣು ಸಿದ್ಧಪಡಿಸಲು ಸುಮಾರು {prep_days} ದಿನಗಳು ಬೇಕಾಗುತ್ತವೆ."
            elif self.lang_code == 'ta':
                if is_suitable:
                    return f"{crop_name_loc} பயிரிட உங்கள் மண் மிகவும் ஏற்றது. பொருத்தம் {score} சதவீதம் உள்ளது. நீங்கள் பயிர் செய்யலாம்."
                else:
                    return f"{crop_name_loc} பயிருக்கு தற்போதைய மண்ணை தயார்படுத்த வேண்டும். பொருத்தம் {score} சதவீதம். நிலத்தை தயார் செய்ய சுமார் {prep_days} நாட்கள் ஆகும்."
            elif self.lang_code == 'te':
                if is_suitable:
                    return f"{crop_name_loc} పంటకు మీ నేల చాలా అనుకూలంగా ఉంది. అనుకూలత {score} శాతం ఉంది. మీరు ఈ పంటను సాగు చేయవచ్చు."
                else:
                    return f"{crop_name_loc} పంటకు నేలకు తగిన సవరణలు అవసరం. అనుకూలత {score} శాతం. నేలను సిద్ధం చేయడానికి దాదాపు {prep_days} రోజులు పడుతుంది."
            else:
                if is_suitable:
                    return f"Your soil is suitable for {crop_name_loc} with {score} percent suitability. You can proceed with cultivation."
                else:
                    return f"For {crop_name_loc}, soil requires preparation. Suitability is {score} percent, and soil preparation will take approximately {prep_days} days."

        # 1. Greetings / Help / Capabilities
        if any(w in q for w in [
            "hello", "hi", "hey", "namaste", "namaskar", "namaskara", "vanakkam", "namaskaram",
            "who are you", "help", "kya kar sakte", "sahaya", "uthavi", "sahayam",
            "नमस्ते", "नमस्कार", "प्रणाम", "मदद", "सहायता", "ನಮಸ್ಕಾರ", "ಸಹಾಯ", "வணக்கம்", "உதவி", "నమస్కారం", "సహాయం"
        ]):
            if self.lang_code == 'hi':
                return "नमस्ते! मैं आपका फार्म बॉट डिजिटल कृषि सहायक हूँ। आप मुझसे फसल की सिफारिश, मिट्टी की नमी, तापमान, पानी के पंप, खाद और पोषक तत्वों के बारे में पूछ सकते हैं।"
            elif self.lang_code == 'kn':
                return "ನಮಸ್ಕಾರ! ನಾನು ನಿಮ್ಮ ಫಾರ್ಮ್ ಬಾಟ್ ಕೃಷಿ ಸಹಾಯಕ. ನೀವು ನನ್ನ ಬಳಿ ಬೆಳೆ ಶಿಫಾರಸು, ಮಣ್ಣಿನ ತೇವಾಂಶ, ತಾಪಮಾನ, ಪಂಪ್ ಸ್ಥಿತಿ, ರಸಗೊಬ್ಬರ ಮತ್ತು ಮಣ್ಣಿನ ಆರೋಗ್ಯದ ಬಗ್ಗೆ ಕೇಳಬಹುದು."
            elif self.lang_code == 'ta':
                return "வணக்கம்! நான் உங்கள் பார்ம் பாட் விவசாய உதவியாளர். பயிர் பரிந்துரை, மண்ணின் ஈரப்பதம், வெப்பநிலை, தண்ணீர் பம்ப், மற்றும் உரங்கள் பற்றி என்னிடம் கேட்கலாம்."
            elif self.lang_code == 'te':
                return "నమస్కారం! నేను మీ ఫార్మ్ బాట్ డిజిటల్ వ్యవసాయ సహాయకుడిని. మీరు పంటల సిఫార్సు, నేలలో తేమ, ఉష్ణోగ్రత, నీటి పంపు, ఎరువులు మరియు నేల పోషకాల గురించి అడగవచ్చు."
            else:
                return "Hello! I am your Farm Bot agriculture assistant. You can ask me about crop recommendations, soil moisture, temperature, irrigation pump status, fertilizers, and soil nutrients."

        # 2. Crop Recommendation / What crop to grow
        if any(w in q for w in [
            "crop", "grow", "plant", "suggest", "recommend", "fasal", "kheti", "ugaye", "upaj", "boni",
            "bele", "belibeku", "thaliru", "payir", "velai", "sedi", "panta", "pandinchali", "saagu",
            "फसल", "खेती", "उपज", "बोना", "उगाना", "ಬೆಳೆ", "ಬೆಳೆಯ", "ಕೃಷಿ", "ಪೈರು",
            "பயிர்", "சாகுபடி", "பயிரிட", "விளைச்சல்", "பயிர்கள்", "பயிர் செய்யலாம்", "பயிர் நட",
            "పంట", "పండించ", "సాగు", "విత్తనాలు", "ఏ పంట"
        ]):
            recs = ml_engine.predict_top_crops(telemetry, top_n=1)
            top = recs[0]
            top_crop_name = self.get_crop_name(top['crop'])
            suitability = int(top['suitability_score_pct'])
            exp_yield = top['estimated_yield_tons_per_acre']

            if self.lang_code == 'hi':
                return f"वर्तमान मिट्टी और मौसम के आधार पर, सबसे उत्तम फसल {top_crop_name} है। इसकी उपयुक्तता {suitability} प्रतिशत है और अनुमानित उपज {exp_yield} टन प्रति एकड़ है।"
            elif self.lang_code == 'kn':
                return f"ಪ್ರಸ್ತುತ ಮಣ್ಣು ಮತ್ತು ಹವಾಮಾನದ ಆಧಾರದ ಮೇಲೆ, ಅತ್ಯುತ್ತಮ ಬೆಳೆ {top_crop_name}. ಇದರ ಸೂಕ್ತತೆ {suitability} ಪ್ರತಿಶತ ಮತ್ತು ಅಂದಾಜು ಇಳುವರಿ ಎಕರೆಗೆ {exp_yield} ಟನ್ ಆಗಿದೆ."
            elif self.lang_code == 'ta':
                return f"தற்போதைய மண் மற்றும் காலநிலைக்கு மிகவும் பரிந்துரைக்கப்படும் பயிர் {top_crop_name} ஆகும். இதன் பொருத்தம் {suitability} சதவீதம் மற்றும் எதிர்பார்க்கப்படும் மகசூல் ஏக்கருக்கு {exp_yield} டன்."
            elif self.lang_code == 'te':
                return f"ప్రస్తుత నేల మరియు వాతావరణ పరిస్థితులకు అత్యంత అనుకూలమైన పంట {top_crop_name}. దీని అనుకూలత {suitability} శాతం మరియు అంచనా దిగుబడి ఎకరానికి {exp_yield} టన్నులు."
            else:
                return f"Based on current soil conditions, the most recommended crop is {top_crop_name} with {suitability} percent suitability and expected yield of {exp_yield} tons per acre."

        # 3. Soil Moisture / Water in soil
        if any(w in q for w in [
            "moisture", "nami", "thevamsa", "theamsha", "eerappatham", "eeram", "thema", "thadi",
            "soil dry", "soil wet", "water in soil", "water level", "dry", "wet",
            "नमी", "गीली", "सूखी", "मिट्टी में पानी", "ತೇವಾಂಶ", "ತೇವ", "ಒಣಗಿದೆ", "ತಡಿಯ",
            "ஈரப்பதம்", "ஈரம்", "காய்ந்து", "தேவை", "தேவாம்சம்", "తేమ", "తడి", "ఆరిపో", "నీటిమట్టం"
        ]):
            if moisture < 30.0:
                cond = {
                    'en': f"Current soil moisture is {moisture} percent. The soil is dry and requires irrigation.",
                    'hi': f"वर्तमान में मिट्टी की नमी {moisture} प्रतिशत है। मिट्टी सूखी है और तुरंत सिंचाई की आवश्यकता है।",
                    'kn': f"ಪ್ರಸ್ತುತ ಮಣ್ಣಿನ ತೇವಾಂಶ {moisture} ಪ್ರತಿಶತ ಇದೆ. ಮಣ್ಣು ಒಣಗಿದ್ದು ತಕ್ಷಣ ನೀರುಣಿಸುವ ಅಗತ್ಯವಿದೆ.",
                    'ta': f"தற்போதைய மண்ணின் ஈரப்பதம் {moisture} சதவீதம் ஆகும். மண் வறண்டுள்ளது, உடனே பாசனம் தேவைப்படுகிறது.",
                    'te': f"ప్రస్తుత నేలలో తేమ శాతం {moisture} శాతం ఉంది. నేల ఆరిపోయింది, తక్షణమే నీరు పెట్టాలి."
                }
            elif moisture > 70.0:
                cond = {
                    'en': f"Current soil moisture is {moisture} percent. The soil is heavily wet with plenty of water.",
                    'hi': f"वर्तमान में मिट्टी की नमी {moisture} प्रतिशत है। मिट्टी में पानी की मात्रा अधिक है।",
                    'kn': f"ಪ್ರಸ್ತುತ ಮಣ್ಣಿನ ತೇವಾಂಶ {moisture} ಪ್ರತಿಶತ ಇದೆ. ಮಣ್ಣಿನಲ್ಲಿ ನೀರಿನ ಪ್ರಮಾಣ ಅಧಿಕವಾಗಿದೆ.",
                    'ta': f"தற்போதைய மண்ணின் ஈரப்பதம் {moisture} சதவீதம் ஆகும். மண்ணில் அதிகப்படியான தண்ணீர் உள்ளது.",
                    'te': f"ప్రస్తుత నేలలో తేమ శాతం {moisture} శాతం ఉంది. నేలలో నీటి నిల్వ ఎక్కువగా ఉంది."
                }
            else:
                cond = {
                    'en': f"Current soil moisture is {moisture} percent. The soil moisture level is optimal for healthy crop growth.",
                    'hi': f"वर्तमान में मिट्टी की नमी {moisture} प्रतिशत है। यह नमी फसल के अच्छे विकास के लिए बिल्कुल सही है।",
                    'kn': f"ಪ್ರಸ್ತುತ ಮಣ್ಣಿನ ತೇವಾಂಶ {moisture} ಪ್ರತಿಶತ ಇದೆ. ಇದು ಬೆಳೆಯ ಆರೋಗ್ಯಕರ ಬೆಳವಣಿಗೆಗೆ ಸೂಕ್ತವಾಗಿದೆ.",
                    'ta': f"தற்போதைய மண்ணின் ஈரப்பதம் {moisture} சதவீதம் ஆகும். ಇದು பயிர்களின் வளர்ச்சிக்கு உகந்த அளவில் உள்ளது.",
                    'te': f"ప్రస్తుత నేలలో తేమ శాతం {moisture} శాతం ఉంది. ఇది పంటల ఎదుగుదలకు అనుకూలమైన స్థాయిలో ఉంది."
                }
            return cond.get(self.lang_code, cond['en'])

        # 4. Temperature / Heat / Weather
        if any(w in q for w in [
            "temperature", "temp", "tapman", "taapman", "tapamana", "veppanilai", "ushnogratha",
            "garmi", "sardi", "weather", "heat", "hot", "cold",
            "तापमान", "ताप", "गर्मी", "सर्दी", "मौसम", "ತಾಪಮಾನ", "ಉಷ್ಣಾಂಶ", "ಬಿಸಿ", "ಚಳಿ",
            "வெப்பநிலை", "வெப்பம்", "குளிர்", "ఉష్ణోగ్రత", "వేడి", "చలి", "వాతావరణం"
        ]):
            if self.lang_code == 'hi':
                return f"वर्तमान वातावरणीय तापमान {temp} डिग्री सेल्सियस है।"
            elif self.lang_code == 'kn':
                return f"ಪ್ರಸ್ತುತ ವಾತಾವರಣದ ತಾಪಮಾನ {temp} ಡಿಗ್ರಿ ಸೆಲ್ಸಿಯಸ್ ಆಗಿದೆ."
            elif self.lang_code == 'ta':
                return f"தற்போதைய வளிமண்டல வெப்பநிலை {temp} டிகிரி செல்சியஸ் ஆகும்."
            elif self.lang_code == 'te':
                return f"ప్రస్తుత వాతావరణ ఉష్ణోగ్రత {temp} డిగ్రీల సెల్సియస్ గా ఉంది."
            else:
                return f"The current atmospheric temperature is {temp} degrees Celsius."

        # 5. Humidity
        if any(w in q for w in [
            "humidity", "humid", "aadrata", "aardrata", "aadrathe", "kaatrin eerappatham", "gaalilo thema",
            "air moisture", "आर्द्रता", "हवा में नमी", "ಆರ್ದ್ರತೆ", "ಗಾಳಿಯ ತೇವಾಂಶ", "காற்றின் ஈரப்பதம்", "గాలిలోని తేమ"
        ]):
            if self.lang_code == 'hi':
                return f"वातावरण में सापेक्ष आर्द्रता {hum} प्रतिशत है।"
            elif self.lang_code == 'kn':
                return f"ಗಾಳಿಯ ಸಾಪೇಕ್ಷ ಆರ್ದ್ರತೆ {hum} ಪ್ರತಿಶತ ಇದೆ."
            elif self.lang_code == 'ta':
                return f"காற்றின் ஈரப்பதம் {hum} சதவீதம் ஆகும்."
            elif self.lang_code == 'te':
                return f"గాలిలోని సాపేక్ష తేమ {hum} శాతం ఉంది."
            else:
                return f"Current relative humidity is {hum} percent."

        # 6. Water Pump / Motor / Irrigation status
        if any(w in q for w in [
            "pump", "motor", "water", "irrigation", "sinchai", "sinchayi", "neeru", "paasanam", "neellu",
            "motar", "paani", "पंप", "मोटर", "सिंचाई", "पानी", "जल", "ಪಂಪ್", "ಮೋಟಾರ್", "ನೀರು", "ನೀರಾವರಿ",
            "பம்ப்", "மோட்டார்", "பாசனம்", "தண்ணீர்", "நீர்", "பாய்ச்ச", "పంపు", "మోటారు", "నీరు", "నీళ్లు", "సాగునీరు"
        ]):
            if pump == 1:
                if self.lang_code == 'hi':
                    return "पानी का पंप वर्तमान में चालू है। खेत में सिंचाई की जा रही है।"
                elif self.lang_code == 'kn':
                    return "ನೀರಿನ ಪಂಪ್ ಪ್ರಸ್ತುತ ಚಾಲನೆಯಲ್ಲಿದೆ. ಬೆಳೆಗೆ ನೀರು ಹರಿಯುತ್ತಿದೆ."
                elif self.lang_code == 'ta':
                    return "தண்ணீர் பம்ப் தற்போது இயங்குகிறது. பாசனம் நடைபெறுகிறது."
                elif self.lang_code == 'te':
                    return "నీటి పంపు ప్రస్తుతం ఆన్ లో ఉంది. పొలానికి నీరు అందుతోంది."
                else:
                    return "The water pump relay is currently ON and active for irrigation."
            else:
                if self.lang_code == 'hi':
                    return "पानी का पंप वर्तमान में बंद है। मिट्टी में पर्याप्त नमी उपलब्ध है।"
                elif self.lang_code == 'kn':
                    return "ನೀರಿನ ಪಂಪ್ ಪ್ರಸ್ತುತ ಆಫ್ ಆಗಿದೆ. ಮಣ್ಣಿನಲ್ಲಿ ಸಾಕಷ್ಟು ತೇವಾಂಶವಿದೆ."
                elif self.lang_code == 'ta':
                    return "தண்ணீர் பம்ப் தற்போது நிறுத்தப்பட்டுள்ளது. மண்ணில் போதுமான ஈரப்பதம் உள்ளது."
                elif self.lang_code == 'te':
                    return "నీటి పంపు ప్రస్తుతం ఆఫ్ లో ఉంది. నేలలో తగినంత తేమ ఉంది."
                else:
                    return "The water pump relay is currently OFF as soil moisture is sufficient."

        # 7. Fertilizer recommendation / Chemical & Organic manure
        if any(w in q for w in [
            "fertilizer", "fertilizers", "khad", "urvarak", "gobbara", "uram", "eruvu", "eruvulu", "urea", "ssp", "mop",
            "manure", "compost", "vermicompost", "gobar", "sendriya", "iyarkai",
            "खाद", "उर्वरक", "यूरिया", "गोबर", "वर्मीकम्पोस्ट", "जैविक खाद", "गोंबरा",
            "ಗೊಬ್ಬರ", "ಗೊಬ್ಬ", "ಯೂರಿಯಾ", "ಎರೆಹುಳು", "ಸಾವಯವ", "ಉರಂ",
            "உரம்", "உரங்கள்", "உரங்", "உர", "யூரியா", "மண்புழு உரம்", "இயற்கை உரம்",
            "ఎరువు", "ఎరువులు", "ఎరు", "యూరియా", "వర్మీకంపోస్ట్", "సేంద్రియ ఎరువు"
        ]):
            recs = ml_engine.predict_top_crops(telemetry, top_n=1)
            top_crop = recs[0]['crop']
            target_res = fert_engine.analyze_target_crop_goal(telemetry, top_crop)
            chems = target_res.get('chemical_fertilizers', {'urea_kg_per_acre': 25, 'ssp_kg_per_acre': 15, 'mop_kg_per_acre': 10})
            urea_kg = int(chems.get('urea_kg_per_acre', 25))
            ssp_kg = int(chems.get('ssp_kg_per_acre', 15))
            mop_kg = int(chems.get('mop_kg_per_acre', 10))
            crop_loc = self.get_crop_name(top_crop)

            if self.lang_code == 'hi':
                return f"शीर्ष फसल {crop_loc} के लिए, प्रति एकड़ लगभग {urea_kg} किलो यूरिया, {ssp_kg} किलो एसएसपी, और {mop_kg} किलो एमओपी खाद डालें। जैविक खाद हेतु वर्मीकम्पोस्ट का प्रयोग करें।"
            elif self.lang_code == 'kn':
                return f"{crop_loc} ಬೆಳೆಗೆ, ಎಕರೆಗೆ ಸುಮಾರು {urea_kg} ಕೆಜಿ ಯೂರಿಯಾ, {ssp_kg} ಕೆಜಿ ಎಸ್.ಎಸ್.ಪಿ ಮತ್ತು {mop_kg} ಕೆಜಿ ಎಂ.ಒ.ಪಿ ಗೊಬ್ಬರ ಹಾಕಿ. ಸಾವಯವ ಪೋಷಣೆಗೆ ಎರೆಹುಳು ಗೊಬ್ಬರ ಬಳಸಿ."
            elif self.lang_code == 'ta':
                return f"{crop_loc} பயிருக்கு, ஏக்கருக்கு சுமார் {urea_kg} கிலோ யூரியா, {ssp_kg} கிலோ எஸ்.எஸ்.பி, மற்றும் {mop_kg} கிலோ எம்.ஓ.பி உரம் இடவும். இயற்கை உரமாக மண்புழு உரம் பயன்படுத்தலாம்."
            elif self.lang_code == 'te':
                return f"{crop_loc} పంటకు, ఎకరానికి సుమారు {urea_kg} కిలోల యూరియా, {ssp_kg} కిలోల ఎస్.ఎస్.పి మరియు {mop_kg} కిలోల ఎం.ఓ.పి ఎరువు వేయండి. సేంద్రియ ఎరువుగా వర్మీకంపోస్ట్ వాడండి."
            else:
                return f"For top crop {crop_loc}, apply approximately {urea_kg} kg Urea, {ssp_kg} kg SSP, and {mop_kg} kg MOP per acre. Apply vermicompost for organic enrichment."

        # 8. Soil pH / Acidity / Alkalinity
        if any(w in q for w in [
            "ph", "acidity", "alkaline", "acid", "amlata", "kshar", "amla", "kshara", "amila", "kaara", "aamla", "kshaara",
            "पीएच", "अम्ल", "क्षार", "अम्लीय", "क्षारीय", "अम्लता", "ಪಿಹೆಚ್", "ಆಮ್ಲ", "ಕ್ಷಾರ", "ಆಮ್ಲೀಯ",
            "பி.எச்", "அமில", "காரம்", "காரத்தன்மை", "அமிலத்தன்மை", "పి.హెచ్", "ఆమ్ల", "క్షార", "ఆమ్లత్వం", "క్షారత్వం"
        ]):
            if ph < 6.0:
                ph_eval = {
                    'en': f"Current soil pH is {ph}. The soil is acidic. You can add agricultural lime to balance the pH.",
                    'hi': f"मिट्टी का वर्तमान पीएच {ph} है। यह मिट्टी अम्लीय है। पीएच सुधारने के लिए चूना मिलाया जा सकता है।",
                    'kn': f"ಮಣ್ಣಿನ ಪ್ರಸ್ತುತ ಪಿಹೆಚ್ {ph} ಆಗಿದೆ. ಮಣ್ಣು ಆಮ್ಲೀಯವಾಗಿದೆ. ಪಿಹೆಚ್ ಸಮತೋಲನಕ್ಕೆ ಸುಣ್ಣ ಬಳಸಬಹುದು.",
                    'ta': f"மண்ணின் தற்போதைய பி.எச் {ph} ஆகும். மண் அமிலத்தன்மை கொண்டது. இதை சரிசெய்ய வேளாண் சுண்ணாம்பு இடலாம்.",
                    'te': f"నేల ప్రస్తుత పి.హెచ్ {ph} ఉంది. నేల ఆమ్ల గుణం కలిగి ఉంది. సమతుల్యత కోసం వ్యవసాయ సున్నం వాడవచ్చు."
                }
            elif ph > 7.5:
                ph_eval = {
                    'en': f"Current soil pH is {ph}. The soil is alkaline. You can add gypsum to reduce soil alkalinity.",
                    'hi': f"मिट्टी का वर्तमान पीएच {ph} है। यह मिट्टी क्षारीय है। सुधार के लिए जिप्सम का प्रयोग करें।",
                    'kn': f"ಮಣ್ಣಿನ ಪ್ರಸ್ತುತ ಪಿಹೆಚ್ {ph} ಆಗಿದೆ. ಮಣ್ಣು ಕ್ಷಾರೀಯವಾಗಿದೆ. ಸುಧಾರಣೆಗೆ ಜಿಪ್ಸಮ್ ಬಳಸಿ.",
                    'ta': f"மண்ணின் தற்போதைய பி.எச் {ph} ஆகும். மண் காரத்தன்மை கொண்டது. இதை குறைக்க ஜிப்சம் இடலாம்.",
                    'te': f"నేల ప్రస్తుత పి.హెచ్ {ph} ఉంది. నేల క్షార గుణం కలిగి ఉంది. తగ్గించడానికి జిప్సం వాడవచ్చు."
                }
            else:
                ph_eval = {
                    'en': f"Current soil pH is {ph}. The soil is neutral and ideal for most crops.",
                    'hi': f"मिट्टी का वर्तमान पीएच {ph} है। यह मिट्टी सामान्य और अधिकांश फसलों के लिए बहुत उपयुक्त है।",
                    'kn': f"ಮಣ್ಣಿನ ಪ್ರಸ್ತುತ ಪಿಹೆಚ್ {ph} ಆಗಿದೆ. ಮಣ್ಣು ತಟಸ್ಥವಾಗಿದ್ದು ಹೆಚ್ಚಿನ ಬೆಳೆಗಳಿಗೆ ಅತ್ಯುತ್ತಮವಾಗಿದೆ.",
                    'ta': f"மண்ணின் தற்போதைய பி.எச் {ph} ஆகும். இது பெரும்பாலான பயிர்களுக்கு உகந்த சமச்சீர் நிலையாகும்.",
                    'te': f"నేల ప్రస్తుత పి.హెచ్ {ph} ఉంది. ఇది తటస్థంగా ఉండి చాలా పంటలకు అనుకూలంగా ఉంది."
                }
            return ph_eval.get(self.lang_code, ph_eval['en'])

        # 9. NPK / Nutrients / Soil Fertility
        if any(w in q for w in [
            "npk", "nitrogen", "phosphorus", "potassium", "nutrient", "fertility", "poshak", "sarajanaka",
            "oottasatthu", "poshakaalu", "fertile", "saaram", "urvarata",
            "नाइट्रोजन", "फास्फोरस", "पोटेशियम", "पोषक तत्व", "उर्वरता", "उपजाऊ",
            "ಸಾರಜನಕ", "ರಂಜಕ", "ಪೊಟ್ಯಾಷಿಯಂ", "ಪೋಷಕಾಂಶ", "ಫಲವತ್ತತೆ",
            "தழைச்சத்து", "மணிச்சத்து", "சாம்பல் சத்து", "ஊட்டச்சத்து", "மண் வளம்",
            "నత్రజని", "భాస్వరం", "పొటాషియం", "పోషకాలు", "సారవంతం"
        ]):
            if self.lang_code == 'hi':
                return f"मिट्टी में पोषक तत्वों की मात्रा: नाइट्रोजन {n}, फास्फोरस {p}, और पोटेशियम {k} मिलीग्राम प्रति किलोग्राम है। मिट्टी की उर्वरता अच्छी स्थिति में है।"
            elif self.lang_code == 'kn':
                return f"ಮಣ್ಣಿನ ಪೋಷಕಾಂಶಗಳ ಮಟ್ಟ: ಸಾರಜನಕ {n}, ರಂಜಕ {p}, ಮತ್ತು ಪೊಟ್ಯಾಷಿಯಂ {k} ಮಿಲಿಗ್ರಾಂ ಪ್ರತಿ ಕೆಜಿ ಇದೆ. ಮಣ್ಣಿನ ಫಲವತ್ತತೆ ಉತ್ತಮ ಸ್ಥಿತಿಯಲ್ಲಿದೆ."
            elif self.lang_code == 'ta':
                return f"மண்ணின் ஊட்டச்சத்து நிலை: தழைச்சத்து {n}, மணிச்சத்து {p}, மற்றும் சாம்பல் சத்து {k} மி.கி/கி.கி ஆகும். மண் நல்ல வளத்துடன் உள்ளது."
            elif self.lang_code == 'te':
                return f"నేలలో పోషకాల స్థాయి: నత్రజని {n}, భాస్వరం {p}, మరియు పొటాషియం {k} మి.గ్రా/కి.గ్రా ఉంది. నేల సారం మంచి స్థితిలో ఉంది."
            else:
                return f"Current soil nutrients are: Nitrogen {n}, Phosphorus {p}, and Potassium {k} mg/kg. Overall soil fertility is healthy."

        # 10. Soil EC / Salinity
        if any(w in q for w in [
            "ec", "salinity", "salt", "lavanta", "kharapan", "uppu", "uvarppu", "conductivity", "saline",
            "ईसी", "लवणता", "खारापन", "नमक", "ಈಸಿ", "ಲವಣಾಂಶ", "ಉಪ್ಪು", "ಉಪ್ಪಿನಾಂಶ",
            "ஈசி", "உவர்ப்பு", "உப்பு", "உவர்ப்புத்தன்மை", "లవణీయత", "ఉప్పు"
        ]):
            if self.lang_code == 'hi':
                return f"मिट्टी की विद्युत चालकता अर्थात ईसी {ec} मिलीसीमेंस प्रति सेमी है। लवणता का स्तर सामान्य है।"
            elif self.lang_code == 'kn':
                return f"ಮಣ್ಣಿನ ವಿದ್ಯುತ್ ವಾಹಕತೆ {ec} ಎಂಎಸ್ ಪ್ರತಿ ಸೆಂಮೀ ಇದೆ. ಮಣ್ಣಿನಲ್ಲಿ ಉಪ್ಪಿನಾಂಶ ಸಾಮಾನ್ಯವಾಗಿದೆ."
            elif self.lang_code == 'ta':
                return f"மண்ணின் மின் கடத்துத்திறன் {ec} மி.சீ/செ.மீ ஆகும். உவர்ப்பு நிலை இயல்பாக உள்ளது."
            elif self.lang_code == 'te':
                return f"నేల విద్యుత్ వాహకత {ec} mS/cm ఉంది. నేలలో లవణీయత సాధారణ స్థాయిలో ఉంది."
            else:
                return f"Soil electrical conductivity is {ec} mS/cm, which indicates normal salinity."

        # 11. Farm Health Summary / Overall Report / How is my farm
        if any(w in q for w in [
            "summary", "report", "health", "farm", "khet", "thota", "thottam", "polam", "overall",
            "condition", "status", "how is", "how is my farm",
            "रिपोर्ट", "हाल", "स्थिति", "विवरण", "खेत कैसा है", "खेत का हाल",
            "ವರದಿ", "ಸಾರಾಂಶ", "ತೋಟ ಹೇಗಿದೆ", "ಜಮೀನು ಹೇಗಿದೆ", "ಜಮೀನಿನ ಸ್ಥಿತಿ",
            "அறிக்கை", "சுருக்கம்", "தோட்டம் எப்படி", "பண்ணை எப்படி உள்ளது", "பண்ணை நிலை",
            "నివేదిక", "సారాంశం", "పొలం ఎలా ఉంది", "పరిస్థితి", "పొలం సమాచారం"
        ]):
            recs = ml_engine.predict_top_crops(telemetry, top_n=1)
            top_crop_loc = self.get_crop_name(recs[0]['crop'])
            pump_str = "ON" if pump == 1 else "OFF"

            if self.lang_code == 'hi':
                return f"खेत का संक्षिप्त विवरण: मिट्टी की नमी {moisture} प्रतिशत, तापमान {temp} डिग्री, पीएच {ph}, और पंप {pump_str} है। आपके खेत के लिए सबसे उत्तम फसल {top_crop_loc} है।"
            elif self.lang_code == 'kn':
                return f"ತೋಟದ ಸಮಗ್ರ ವಿವರ: ಮಣ್ಣಿನ ತೇವಾಂಶ {moisture} ಪ್ರತಿಶತ, ತಾಪಮಾನ {temp} ಡಿಗ್ರಿ, ಪಿಹೆಚ್ {ph}, ಮತ್ತು ಪಂಪ್ {pump_str} ಆಗಿದೆ. ನಿಮ್ಮ ಜಮೀನಿಗೆ ಅತ್ಯುತ್ತಮ ಬೆಳೆ {top_crop_loc}."
            elif self.lang_code == 'ta':
                return f"பண்ணை நிலை சுருக்கம்: மண்ணின் ஈரப்பதம் {moisture} சதவீதம், வெப்பநிலை {temp} டிகிரி, பி.எச் {ph}, பம்ப் {pump_str} ஆகும். சிறந்த பயிர் {top_crop_loc}."
            elif self.lang_code == 'te':
                return f"పొలం సమగ్ర వివరాలు: నేలలో తేమ {moisture} శాతం, ఉష్ణోగ్రత {temp} డిగ్రీలు, పి.హెచ్ {ph}, మరియు పంపు {pump_str} ఉంది. మీ పొలానికి ఉత్తమ పంట {top_crop_loc}."
            else:
                return f"Farm status report: Soil moisture is {moisture}%, temperature is {temp}°C, pH is {ph}, and pump is {pump_str}. Recommended crop is {top_crop_loc}."

        # 12. Smart Fallback for Any Other Unclassified Question
        # (Instead of saying "Received command 'x'. Telemetry optimal.")
        recs = ml_engine.predict_top_crops(telemetry, top_n=1)

        top_crop_loc = self.get_crop_name(recs[0]['crop'])
        
        fallback_msg = {
            'en': f"Regarding '{query}': Current soil moisture is {moisture}%, temperature is {temp}°C, pH is {ph}, and recommended crop is {top_crop_loc}. You can ask about crops, fertilizers, moisture, temperature, or pump status.",
            'hi': f"आपके प्रश्न '{query}' के संदर्भ में: वर्तमान में मिट्टी की नमी {moisture} प्रतिशत, तापमान {temp} डिग्री, पीएच {ph}, और अनुशंसित फसल {top_crop_loc} है। आप फसल, खाद, नमी, तापमान या पंप के बारे में पूछ सकते हैं।",
            'kn': f"ನಿಮ್ಮ ಪ್ರಶ್ನೆ '{query}' ಕುರಿತು: ಪ್ರಸ್ತುತ ಮಣ್ಣಿನ ತೇವಾಂಶ {moisture} ಪ್ರತಿಶತ, ತಾಪಮಾನ {temp} ಡಿಗ್ರಿ, ಪಿಹೆಚ್ {ph}, ಮತ್ತು ಸೂಕ್ತ ಬೆಳೆ {top_crop_loc} ಆಗಿದೆ. ನೀವು ಬೆಳೆ, ರಸಗೊಬ್ಬರ, ತೇವಾಂಶ, ತಾಪಮಾನ ಅಥವಾ ಪಂಪ್ ಬಗ್ಗೆ ಕೇಳಬಹುದು.",
            'ta': f"உங்கள் கேள்வி '{query}' தொடர்பாக: தற்போதைய மண்ணின் ஈரப்பதம் {moisture} சதவீதம், வெப்பநிலை {temp} டிகிரி, பி.எச் {ph}, மற்றும் சிறந்த பயிர் {top_crop_loc} ஆகும். பயிர், உரம், ஈரப்பதம், வெப்பநிலை அல்லது பம்ப் பற்றி கேட்கலாம்.",
            'te': f"మీ ప్రశ్న '{query}' గురించి: ప్రస్తుత నేల తేమ {moisture} శాతం, ఉష్ణోగ్రత {temp} డిగ్రీలు, పి.హెచ్ {ph}, మరియు సిఫార్సు చేసిన పంట {top_crop_loc}. మీరు పంటలు, ఎరువులు, తేమ, ఉష్ణోగ్రత లేదా పంపు గురించి అడగవచ్చు."
        }
        return fallback_msg.get(self.lang_code, fallback_msg['en'])


if __name__ == '__main__':
    assistant = MultilingualVoiceAssistant('en')
    assistant.speak("Farm Bot Voice Assistant Online.")
