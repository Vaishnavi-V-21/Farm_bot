"""
=====================================================================================
Project Title : Farm Bot: IoT Sensor Receiver API
File          : sensor_receiver.py
Description   : Lightweight Flask HTTP server that receives real-time sensor data
                JSON payloads from the ESP32 node, logs them to the SQLite database,
                and returns pump control commands back to the ESP32.

Run Command   : python sensor_receiver.py
Port          : 5000 (must match ESP32 SERVER_URL)
=====================================================================================
"""

import os
import sys

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from flask import Flask, request, jsonify

try:
    from src.db_manager import FarmBotDatabase
except ModuleNotFoundError:
    from db_manager import FarmBotDatabase

app = Flask(__name__)
db  = FarmBotDatabase()

# Configurable hysteresis thresholds
LOWER_MOISTURE_THRESHOLD = 30.0
UPPER_MOISTURE_THRESHOLD = 45.0
current_pump_state = 0

# Stores the latest telemetry received from ESP32 (shared state)
latest_telemetry = {}

def _safe_val(v, default=None):
    if v is None or v == "" or str(v).lower() in ["null", "none", "--", "-1"]:
        return default
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return default

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    """
    Receives JSON payload from ESP32 and logs to database.
    Returns pump ON/OFF command back to ESP32 with hysteresis.
    """
    global latest_telemetry, current_pump_state

    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    raw_n = _safe_val(data.get('N'))
    raw_p = _safe_val(data.get('P'))
    raw_k = _safe_val(data.get('K'))
    moist = float(data.get('moisture', 35.0))

    telemetry = {
        'temp'    : float(data.get('temp',     26.0)),
        'hum'     : float(data.get('hum',      65.0)),
        'moisture': moist,
        'N'       : raw_n,
        'P'       : raw_p,
        'K'       : raw_k,
        'ph'      : float(data.get('ph',  6.5)),
        'ec'      : float(data.get('ec',  1.2)),
        'pump'    : int(data.get('pump', current_pump_state)),
        'npk_valid': bool(data.get('npk_valid', (raw_n is not None and raw_p is not None and raw_k is not None)))
    }

    # Auto pump hysteresis decision
    if moist < LOWER_MOISTURE_THRESHOLD:
        current_pump_state = 1
    elif moist >= UPPER_MOISTURE_THRESHOLD:
        current_pump_state = 0
    # Between thresholds: maintain current_pump_state

    telemetry['pump'] = current_pump_state

    # Save latest telemetry so dashboard can read it
    latest_telemetry = telemetry

    # Log to SQLite database
    db_record = dict(telemetry)
    if db_record['N'] is None: db_record['N'] = -1
    if db_record['P'] is None: db_record['P'] = -1
    if db_record['K'] is None: db_record['K'] = -1
    db.log_telemetry(db_record)

    n_display = f"{telemetry['N']} mg/kg" if telemetry['N'] is not None else "--"
    p_display = f"{telemetry['P']} mg/kg" if telemetry['P'] is not None else "--"
    k_display = f"{telemetry['K']} mg/kg" if telemetry['K'] is not None else "--"

    print(f"[ESP32 → SERVER] Temp:{telemetry['temp']}°C | Hum:{telemetry['hum']}% | "
          f"Moisture:{telemetry['moisture']}% | N:{n_display} P:{p_display} K:{k_display} | "
          f"Pump:{current_pump_state} (Hysteresis {LOWER_MOISTURE_THRESHOLD}-{UPPER_MOISTURE_THRESHOLD}%)")

    # Return pump command and status back to ESP32
    return jsonify({
        "status"       : "logged",
        "pump_command" : current_pump_state,
        "lower_thresh" : LOWER_MOISTURE_THRESHOLD,
        "upper_thresh" : UPPER_MOISTURE_THRESHOLD
    }), 200


@app.route('/api/latest', methods=['GET'])
def get_latest():
    """Returns the latest telemetry reading (used by live dashboard)."""
    return jsonify(latest_telemetry), 200


@app.route('/api/history', methods=['GET'])
def get_history():
    """Returns last 50 sensor records from SQLite."""
    rows = db.fetch_recent_telemetry(50)
    keys = ['timestamp', 'temp', 'hum', 'moisture', 'N', 'P', 'K', 'ec', 'ph', 'pump']
    result = [dict(zip(keys, row)) for row in rows]
    return jsonify(result), 200


@app.route('/api/pump/set', methods=['POST'])
def set_pump():
    """Manually override pump state from dashboard or external trigger."""
    global latest_telemetry
    data = request.get_json(force=True)
    state = int(data.get('state', 0))
    if latest_telemetry:
        latest_telemetry['pump'] = state
    print(f"[PUMP OVERRIDE]: Pump manually set to {'ON' if state else 'OFF'}")
    return jsonify({"pump_command": state}), 200


if __name__ == '__main__':
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print("=" * 60)
    print("  🌾 FARM BOT — ESP32 Sensor Receiver Server")
    print("=" * 60)
    print(f"  Server IP    : {local_ip}")
    print(f"  Listening on : http://0.0.0.0:5000")
    print(f"\n  ⚙️  Update ESP32 firmware with:")
    print(f"    SERVER_URL = \"http://{local_ip}:5000/api/telemetry\"")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False)
