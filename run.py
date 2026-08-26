"""
=====================================================================================
Project Title : Farm Bot: Intelligent Farming with Fertility & Crop Recommendation
File          : run.py
Description   : Master launcher script to setup environment, train ML model,
                initialize database, and launch the interactive dashboard.
Usage         : python run.py
=====================================================================================
"""

import os
import sys
import subprocess

def check_and_install_dependencies():
    """Checks for required packages and installs any missing ones."""
    required_packages = {
        'streamlit': 'streamlit',
        'sklearn': 'scikit-learn',
        'pandas': 'pandas',
        'numpy': 'numpy',
        'pygame': 'pygame',
        'gtts': 'gTTS',
        'speech_recognition': 'SpeechRecognition'
    }

    missing = []
    for module_name, package_name in required_packages.items():
        try:
            __import__(module_name)
        except ImportError:
            missing.append(package_name)

    if missing:
        print(f"📦 Installing missing dependencies: {', '.join(missing)}...")
        req_file = os.path.join(os.path.dirname(__file__), 'requirements.txt')
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', req_file])
        print("✅ All dependencies installed successfully.\n")

def main():
    print("=" * 65)
    print(" 🌾 FARM BOT: INTELLIGENT AGRICULTURE & CROP RECOMMENDATION 🌾")
    print("=" * 65)

    # 1. Check dependencies
    print("\n[Step 1/3] Checking dependencies...")
    check_and_install_dependencies()

    # 2. Train model if missing
    print("[Step 2/3] Checking ML model and database...")
    model_path = os.path.join(os.path.dirname(__file__), 'models', 'crop_recommendation_rf.pkl')
    if not os.path.exists(model_path):
        print("⚡ Pre-trained model not found. Training model now...")
        from src.dataset_generator import train_and_save_model
        train_and_save_model()
    else:
        print(f"✅ Trained model found at {model_path}")

    # Initialize DB
    from src.db_manager import FarmBotDatabase
    db = FarmBotDatabase()
    print("✅ Database initialized successfully.")

    # 3. Launch Dashboard
    print("\n[Step 3/3] Launching Farm Bot Dashboard on Streamlit...")
    dashboard_path = os.path.join(os.path.dirname(__file__), 'src', 'dashboard.py')
    
    cmd = [sys.executable, "-m", "streamlit", "run", dashboard_path]
    print(f"🚀 Running: {' '.join(cmd)}\n")
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n🛑 Farm Bot Dashboard stopped.")

if __name__ == '__main__':
    main()
