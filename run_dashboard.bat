@echo off
echo =========================================================
echo   Starting Farm Bot Streamlit Dashboard...
echo =========================================================
cd /d "%~dp0"
python -m streamlit run src/dashboard.py
pause
