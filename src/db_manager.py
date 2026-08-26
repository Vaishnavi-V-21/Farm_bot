"""
=====================================================================================
Project Title : Farm Bot: Intelligent Farming with Fertility & Crop Recommendation
File          : src/db_manager.py
Description   : SQLite database schema manager and Data Access Object (DAO) layer for
                logging telemetry readings, irrigation events, crop recommendations,
                and fertilizer prescriptions.
=====================================================================================
"""

import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '../data/farm_bot.db')

class FarmBotDatabase:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._shared_conn = None
        dir_name = os.path.dirname(self.db_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        if self.db_path == ":memory:":
            self._shared_conn = sqlite3.connect(":memory:")
        self.init_tables()

    def get_connection(self):
        if self._shared_conn:
            return self._shared_conn
        return sqlite3.connect(self.db_path)

    def init_tables(self):
        """Initializes database tables for sensor logs, alerts, and recommendations."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Telemetry Log Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS telemetry_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    temperature REAL,
                    humidity REAL,
                    soil_moisture REAL,
                    nitrogen INTEGER,
                    phosphorus INTEGER,
                    potassium INTEGER,
                    soil_ec REAL,
                    soil_ph REAL,
                    pump_status INTEGER
                )
            ''')

            # Irrigation Log Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS irrigation_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    trigger_reason TEXT,
                    start_moisture REAL,
                    end_moisture REAL,
                    duration_seconds INTEGER
                )
            ''')

            # Recommendation History Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crop_recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    recommended_crop TEXT,
                    suitability_pct REAL,
                    estimated_yield REAL,
                    rationale TEXT
                )
            ''')

            conn.commit()
            print(f"[DATABASE]: Schema initialized at {self.db_path}")

    def log_telemetry(self, t):
        """Logs real-time telemetry dictionary to SQLite database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO telemetry_logs 
                (temperature, humidity, soil_moisture, nitrogen, phosphorus, potassium, soil_ec, soil_ph, pump_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                t.get('temp', 0.0), t.get('hum', 0.0), t.get('moisture', 0.0),
                t.get('N', 0), t.get('P', 0), t.get('K', 0),
                t.get('ec', 0.0), t.get('ph', 0.0), int(t.get('pump', 0))
            ))
            conn.commit()

    def fetch_recent_telemetry(self, limit=50):
        """Fetches recent sensor logs for dashboard charting."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, temperature, humidity, soil_moisture, nitrogen, phosphorus, potassium, soil_ec, soil_ph, pump_status
                FROM telemetry_logs
                ORDER BY id DESC LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            return rows

if __name__ == '__main__':
    db = FarmBotDatabase()
    sample = {'temp': 28.5, 'hum': 65.0, 'moisture': 35.0, 'N': 50, 'P': 30, 'K': 120, 'ec': 1.2, 'ph': 6.5, 'pump': 1}
    db.log_telemetry(sample)
    logs = db.fetch_recent_telemetry(5)
    print(f"[DB TEST]: Fetched {len(logs)} recent telemetry records.")
