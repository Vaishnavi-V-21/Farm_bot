"""
=====================================================================================
Project Title : Farm Bot: Intelligent Farming with Fertility & Crop Recommendation
File          : src/voice_assistant.py
Description   : Multilingual Voice Assistant engine with speech recognition and
                dual online (gTTS) / offline (pyttsx3) text-to-speech synthesis for
                English, Hindi, Kannada, Tamil, and Telugu.
=====================================================================================
"""

import os
import time
import speech_recognition as sr
from gtts import gTTS
import pygame

# Optional offline TTS fallback
try:
    import pyttsx3
    OFFLINE_TTS_AVAILABLE = True
except ImportError:
    OFFLINE_TTS_AVAILABLE = False

pygame.mixer.init()

LANGUAGES = {
    '1': {'code': 'en', 'name': 'English'},
    '2': {'code': 'hi', 'name': 'Hindi (हिंदी)'},
    '3': {'code': 'kn', 'name': 'Kannada (ಕನ್ನಡ)'},
    '4': {'code': 'ta', 'name': 'Tamil (தமிழ்)'},
    '5': {'code': 'te', 'name': 'Telugu (తెలుగు)'}
}

class MultilingualVoiceAssistant:
    def __init__(self, default_lang_code='en'):
        self.lang_code = default_lang_code
        self.recognizer = sr.Recognizer()
        if OFFLINE_TTS_AVAILABLE:
            self.offline_engine = pyttsx3.init()

    def set_language(self, lang_code):
        if lang_code in ['en', 'hi', 'kn', 'ta', 'te']:
            self.lang_code = lang_code

    def speak(self, text):
        """Synthesizes text and plays audio with online gTTS or offline pyttsx3 fallback."""
        print(f"\n[VOICE ASSISTANT ({self.lang_code.upper()})]: {text}")

        # Attempt Online gTTS first
        try:
            tts = gTTS(text=text, lang=self.lang_code, slow=False)
            filename = "temp_voice.mp3"
            tts.save(filename)

            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)

            pygame.mixer.music.unload()
            if os.path.exists(filename):
                os.remove(filename)
            return
        except Exception as e:
            print(f"[VOICE WARNING]: Online gTTS failed ({e}). Falling back to Offline Engine.")

        # Fallback to Offline Engine if installed
        if OFFLINE_TTS_AVAILABLE:
            try:
                self.offline_engine.say(text)
                self.offline_engine.runAndWait()
            except Exception as ex:
                print(f"[VOICE ERROR]: Offline TTS also failed: {ex}")

    def listen(self, timeout_sec=5):
        """Captures microphone input and converts speech to text."""
        with sr.Microphone() as source:
            print(f"\n[VOICE LISTENER] Listening... Speak clearly into microphone.")
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
        """Answers standard farmer queries directly."""
        if not query:
            return "No command heard. Please try again."

        query = query.lower()

        if "crop" in query or "fasal" in query or "bele" in query:
            recs = ml_engine.predict_top_crops(telemetry, top_n=1)
            top = recs[0]
            if self.lang_code == 'hi':
                return f"सुझाई गई फसल {top['crop']} है। अनुमानित उपज {top['estimated_yield_tons_per_acre']} टन प्रति एकड़ है।"
            elif self.lang_code == 'kn':
                return f"ಸೂಕ್ತವಾದ ಬೆಳೆ {top['crop']}. ಅಂದಾಜು ಇಳುವರಿ ಎಕರೆಗೆ {top['estimated_yield_tons_per_acre']} ಟನ್."
            else:
                return f"Recommended crop is {top['crop']} with suitability {top['suitability_score_pct']} percent."

        elif "moisture" in query or "nami" in query or "theamsha" in query:
            return f"Current soil moisture is {telemetry['moisture']} percent."

        elif "temperature" in query or "taapman" in query:
            return f"Current temperature is {telemetry['temp']} degrees Celsius."

        elif "pump" in query or "irrigation" in query or "paani" in query:
            status = "ON" if telemetry['pump'] else "OFF"
            return f"Water pump is currently {status}."

        else:
            return f"Received command '{query}'. Telemetry optimal."

if __name__ == '__main__':
    assistant = MultilingualVoiceAssistant('en')
    assistant.speak("Farm Bot Voice Assistant Online.")
