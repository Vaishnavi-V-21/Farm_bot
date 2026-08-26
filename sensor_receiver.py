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

from flask import Flask, request, jsonify
from src.db_manager import FarmBotDatabase

app = Flask(__name__)
db  = FarmBotDatabase()

# Global moisture threshold (can be tuned here or synced from dashboard)
MOISTURE_THRESHOLD = 35.0

# Stores the latest telemetry received from ESP32 (shared state)
latest_telemetry = {}

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    """
    Receives JSON payload from ESP32 and logs to database.
    Returns pump ON/OFF command back to ESP32.
    """
    global latest_telemetry

    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    # Extract sensor values with safe defaults
    telemetry = {
        'temp'    : float(data.get('temp',     26.0)),
        'hum'     : float(data.get('hum',      65.0)),
        'moisture': float(data.get('moisture', 35.0)),
        'N'       : int(data.get('N',   50)),
        'P'       : int(data.get('P',   30)),
        'K'       : int(data.get('K',  120)),
        'ph'      : float(data.get('ph',  6.5)),
        'ec'      : float(data.get('ec',  1.2)),
        'pump'    : int(data.get('pump',    0)),
    }

    # Auto pump decision: turn ON if moisture below threshold
    auto_pump = 1 if telemetry['moisture'] < MOISTURE_THRESHOLD else 0
    telemetry['pump'] = auto_pump

    # Save latest telemetry so dashboard can read it
    latest_telemetry = telemetry

    # Log to SQLite database
    db.log_telemetry(telemetry)

    print(f"[ESP32 → SERVER] Temp:{telemetry['temp']}°C | "
          f"Hum:{telemetry['hum']}% | Moisture:{telemetry['moisture']}% | "
          f"N:{telemetry['N']} P:{telemetry['P']} K:{telemetry['K']} | "
          f"pH:{telemetry['ph']} | EC:{telemetry['ec']} | Pump:{auto_pump}")

    # Return pump command and status back to ESP32
    return jsonify({
        "status"       : "logged",
        "pump_command" : auto_pump,
        "threshold"    : MOISTURE_THRESHOLD
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
