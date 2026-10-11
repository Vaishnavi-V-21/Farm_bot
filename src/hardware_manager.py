"""
=====================================================================================
Project Title : Farm Bot: Hardware & Sensor Manager
File          : src/hardware_manager.py
Description   : Auto-detects connected hardware (USB Serial COM port or WiFi IoT),
                reads real-time sensor telemetry, sends threshold/pump/crop commands,
                and gracefully handles temporary sensor drops without forcing manual mode.
=====================================================================================
"""

import time
import json
import re
import threading
import sys
import os

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

try:
    from src.db_manager import FarmBotDatabase
except ModuleNotFoundError:
    from db_manager import FarmBotDatabase


def _safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int_or_none(val):
    if val is None or val == "" or str(val).strip() in ["--", "null", "None", "-1"]:
        return None
    try:
        ival = int(float(val))
        return ival if ival >= 0 else None
    except (ValueError, TypeError):
        return None


class HardwareManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(HardwareManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, baudrate=115200, db_instance=None):
        if self._initialized:
            return
        self._initialized = True
        
        self.baudrate = baudrate
        self.db = db_instance or FarmBotDatabase()
        
        self.latest_telemetry = None
        self.last_received_time = 0.0
        self.connection_type = "None"
        self.port_name = None
        self.is_connected = False
        
        # Buffer for multi-line regex parsing (if ESP32 outputs multi-line text)
        self._partial_reading = {}
        
        # Serial reader thread & synchronization lock
        self._serial_thread = None
        self._serial_running = True
        self._active_serial = None
        self._serial_io_lock = threading.Lock()
        
        # Start background scanner and listener thread
        if SERIAL_AVAILABLE:
            self._serial_thread = threading.Thread(target=self._serial_worker, daemon=True)
            self._serial_thread.start()

    def _serial_worker(self):
        """Continuously scans COM ports and reads sensor telemetry if connected."""
        while self._serial_running:
            try:
                # Check for available ports if not already connected
                if self._active_serial is None or not self._active_serial.is_open:
                    ports = list(serial.tools.list_ports.comports())
                    target_port = None
                    
                    # Look for likely microcontrollers (CP210x, CH340, USB Serial, etc.)
                    for p in ports:
                        desc = (p.description or "").lower()
                        hwid = (p.hwid or "").lower()
                        if any(k in desc or k in hwid for k in ["cp210", "ch340", "ch341", "usb-serial", "uart", "esp32", "arduino"]):
                            target_port = p.device
                            break
                    
                    # If none matched by keyword, try any available COM port (except COM1 on older PCs)
                    if not target_port and ports:
                        for p in ports:
                            if p.device.upper() != "COM1":
                                target_port = p.device
                                break
                        if not target_port and ports:
                            target_port = ports[0].device

                    if target_port:
                        try:
                            ser = serial.Serial(target_port, self.baudrate, timeout=1.0)
                            time.sleep(1.0)  # Allow ESP32 to settle
                            with self._serial_io_lock:
                                self._active_serial = ser
                                self.port_name = target_port
                                self.connection_type = f"USB Serial ({target_port})"
                                self.is_connected = True
                            print(f"[HARDWARE]: ✅ Connected to ESP32 on {target_port} @ {self.baudrate} baud")
                        except Exception as e:
                            with self._serial_io_lock:
                                self._active_serial = None
                            time.sleep(2.0)
                            continue
                    else:
                        # No serial hardware plugged in
                        self.is_connected = False
                        time.sleep(2.0)
                        continue

                # Read from active serial port
                if self._active_serial and self._active_serial.is_open:
                    try:
                        raw_line = self._active_serial.readline()
                        if raw_line:
                            line = raw_line.decode('utf-8', errors='ignore').strip()
                            if line:
                                parsed = self.parse_serial_line(line)
                                if parsed:
                                    self._on_telemetry_received(parsed, f"USB Serial ({self.port_name})")
                    except serial.SerialException:
                        print(f"[HARDWARE]: ❌ Lost connection to USB Serial on {self.port_name}")
                        self._handle_disconnection()
                        time.sleep(2.0)
                    except Exception as e:
                        time.sleep(0.2)

            except Exception as e:
                time.sleep(2.0)

    def _handle_disconnection(self):
        """Safely cleans up state on genuine physical disconnection."""
        with self._serial_io_lock:
            if self._active_serial:
                try:
                    self._active_serial.close()
                except Exception:
                    pass
            self._active_serial = None
            self.port_name = None
            self.connection_type = "None"
            self.is_connected = False

    def is_hardware_connected(self) -> bool:
        """
        Verifies actual ESP32 connection status without confusing
        delayed readings with a disconnect.
        """
        # Check active USB serial port
        if self._active_serial and self._active_serial.is_open:
            if SERIAL_AVAILABLE and self.port_name:
                available_ports = [p.device for p in serial.tools.list_ports.comports()]
                if self.port_name in available_ports:
                    self.is_connected = True
                    return True
                else:
                    # Device was physically unplugged from USB
                    self._handle_disconnection()
                    return False
            self.is_connected = True
            return True

        # Check recent WiFi telemetry (30s grace period)
        if self.connection_type.startswith("WiFi") and (time.time() - self.last_received_time <= 30.0):
            self.is_connected = True
            return True

        return False

    def parse_serial_line(self, line: str):
        """
        Parses incoming serial line from ESP32.
        Correctly handles JSON with null/missing NPK values and regex formatted lines.
        """
        line = line.strip()
        if not line:
            return None

        # 1. Try parsing JSON substring
        if "{" in line and "}" in line:
            try:
                start = line.index("{")
                end = line.rindex("}") + 1
                json_str = line[start:end]
                data = json.loads(json_str)
                if "telemetry" in data and isinstance(data["telemetry"], dict):
                    data = data["telemetry"]
                
                # Check for standard fields
                if any(k in data for k in ["temp", "humidity", "hum", "moisture", "N", "pump"]):
                    raw_n = data.get('N', data.get('nitrogen'))
                    raw_p = data.get('P', data.get('phosphorus'))
                    raw_k = data.get('K', data.get('potassium'))
                    
                    parsed_n = _safe_int_or_none(raw_n)
                    parsed_p = _safe_int_or_none(raw_p)
                    parsed_k = _safe_int_or_none(raw_k)
                    
                    npk_valid = bool(data.get('npk_valid', (parsed_n is not None and parsed_p is not None and parsed_k is not None)))
                    npk_status = str(data.get('npk_status', 'OK' if npk_valid else 'UNAVAILABLE'))
                    
                    telemetry = {
                        'temp': _safe_float(data.get('temp', data.get('temperature', 26.5)), 26.5),
                        'hum': _safe_float(data.get('hum', data.get('humidity', 65.0)), 65.0),
                        'moisture': _safe_float(data.get('moisture', data.get('soil_moisture', 35.0)), 35.0),
                        'N': parsed_n,
                        'P': parsed_p,
                        'K': parsed_k,
                        'ph': _safe_float(data.get('ph', data.get('soil_ph', 6.5)), 6.5),
                        'ec': _safe_float(data.get('ec', data.get('soil_ec', 1.2)), 1.2),
                        'pump': int(_safe_float(data.get('pump', data.get('pump_status', 0)))),
                        'pump_mode': str(data.get('pump_mode', 'AUTO')),
                        'lower_thresh': _safe_float(data.get('lower_thresh', 30.0), 30.0),
                        'upper_thresh': _safe_float(data.get('upper_thresh', 45.0), 45.0),
                        'npk_valid': npk_valid,
                        'npk_status': npk_status
                    }
                    return telemetry
            except Exception as e:
                pass

        # 2. Try parsing formatted human-readable lines from ESP32 Serial Monitor
        temp_match = re.search(r"Temperature\s*:\s*([0-9.]+)", line, re.IGNORECASE)
        if temp_match:
            self._partial_reading['temp'] = float(temp_match.group(1))

        hum_match = re.search(r"Humidity\s*:\s*([0-9.]+)", line, re.IGNORECASE)
        if hum_match:
            self._partial_reading['hum'] = float(hum_match.group(1))

        moist_match = re.search(r"Soil Moisture\s*:\s*([0-9.]+)", line, re.IGNORECASE)
        if moist_match:
            self._partial_reading['moisture'] = float(moist_match.group(1))

        n_match = re.search(r"Nitrogen\s*\(?N\)?\s*:\s*([0-9]+|--)", line, re.IGNORECASE)
        if n_match:
            val = n_match.group(1)
            self._partial_reading['N'] = None if val == "--" else int(val)

        p_match = re.search(r"Phosphorus\s*\(?P\)?\s*:\s*([0-9]+|--)", line, re.IGNORECASE)
        if p_match:
            val = p_match.group(1)
            self._partial_reading['P'] = None if val == "--" else int(val)

        k_match = re.search(r"Potassium\s*\(?K\)?\s*:\s*([0-9]+|--)", line, re.IGNORECASE)
        if k_match:
            val = k_match.group(1)
            self._partial_reading['K'] = None if val == "--" else int(val)

        ph_match = re.search(r"Soil pH\s*:\s*([0-9.]+)", line, re.IGNORECASE)
        if ph_match:
            self._partial_reading['ph'] = float(ph_match.group(1))

        ec_match = re.search(r"Soil EC\s*:\s*([0-9.]+)", line, re.IGNORECASE)
        if ec_match:
            self._partial_reading['ec'] = float(ec_match.group(1))

        pump_match = re.search(r"Pump Status\s*:\s*(ON|OFF|[01])", line, re.IGNORECASE)
        if pump_match:
            val = pump_match.group(1).upper()
            self._partial_reading['pump'] = 1 if val in ["ON", "1"] else 0

        # When we have collected at least temperature, humidity, and moisture
        if all(k in self._partial_reading for k in ['temp', 'hum', 'moisture']):
            n_val = self._partial_reading.get('N', None)
            p_val = self._partial_reading.get('P', None)
            k_val = self._partial_reading.get('K', None)
            npk_v = (n_val is not None and p_val is not None and k_val is not None)

            telemetry = {
                'temp': self._partial_reading.get('temp', 26.5),
                'hum': self._partial_reading.get('hum', 65.0),
                'moisture': self._partial_reading.get('moisture', 35.0),
                'N': n_val,
                'P': p_val,
                'K': k_val,
                'ph': self._partial_reading.get('ph', 6.5),
                'ec': self._partial_reading.get('ec', 1.2),
                'pump': self._partial_reading.get('pump', 0),
                'pump_mode': 'AUTO',
                'lower_thresh': 30.0,
                'upper_thresh': 45.0,
                'npk_valid': npk_v,
                'npk_status': 'OK' if npk_v else 'UNAVAILABLE'
            }
            self._partial_reading = {}
            return telemetry

        return None

    def _on_telemetry_received(self, telemetry: dict, conn_type: str):
        """Called whenever fresh telemetry arrives from USB Serial or WiFi."""
        self.latest_telemetry = telemetry
        self.last_received_time = time.time()
        self.connection_type = conn_type
        self.is_connected = True
        
        # Log to database (fallback defaults for SQL if N/P/K is None)
        try:
            db_log_record = dict(telemetry)
            if db_log_record.get('N') is None: db_log_record['N'] = -1
            if db_log_record.get('P') is None: db_log_record['P'] = -1
            if db_log_record.get('K') is None: db_log_record['K'] = -1
            self.db.log_telemetry(db_log_record)
        except Exception:
            pass

    def send_command(self, cmd_dict: dict) -> bool:
        """Sends JSON command to ESP32 over active USB Serial connection."""
        with self._serial_io_lock:
            if self._active_serial and self._active_serial.is_open:
                try:
                    payload = json.dumps(cmd_dict) + "\n"
                    self._active_serial.write(payload.encode('utf-8'))
                    self._active_serial.flush()
                    return True
                except Exception as e:
                    print(f"[HARDWARE]: Error writing command to serial: {e}")
                    return False
        return False

    def set_moisture_thresholds(self, lower: float, upper: float) -> bool:
        """Sends lower and upper moisture threshold updates to ESP32 firmware."""
        return self.send_command({
            "cmd": "set_thresholds",
            "lower": round(float(lower), 1),
            "upper": round(float(upper), 1)
        })

    def set_pump_manual_override(self, state: int) -> bool:
        """Commands ESP32 to manually turn pump ON (1) or OFF (0)."""
        return self.send_command({
            "cmd": "set_pump",
            "state": int(state)
        })

    def set_pump_auto_mode(self) -> bool:
        """Commands ESP32 to restore automatic soil moisture hysteresis control."""
        return self.send_command({
            "cmd": "set_pump_mode",
            "mode": "AUTO"
        })

    def send_crop_recommendations(self, crop_names: list) -> bool:
        """Sends top recommended crop names to ESP32 for 16x2 LCD display."""
        return self.send_command({
            "cmd": "set_crops",
            "crops": [str(c) for c in crop_names[:4]]
        })

    def check_wifi_iot_telemetry(self, max_age_seconds=20):
        """Checks if recent telemetry was received via WiFi (logged into SQLite database)."""
        try:
            rows = self.db.fetch_recent_telemetry(1)
            if rows:
                row = rows[0]
                telemetry = {
                    'temp': float(row[1]),
                    'hum': float(row[2]),
                    'moisture': float(row[3]),
                    'N': int(row[4]) if int(row[4]) >= 0 else None,
                    'P': int(row[5]) if int(row[5]) >= 0 else None,
                    'K': int(row[6]) if int(row[6]) >= 0 else None,
                    'ec': float(row[7]),
                    'ph': float(row[8]),
                    'pump': int(row[9]),
                    'npk_valid': int(row[4]) >= 0,
                    'npk_status': 'OK' if int(row[4]) >= 0 else 'UNAVAILABLE',
                    'pump_mode': 'AUTO',
                    'lower_thresh': 30.0,
                    'upper_thresh': 45.0
                }
                return telemetry
        except Exception:
            pass
        return None

    def get_effective_telemetry(self, manual_inputs: dict, mode: str = "Auto-Detect Hardware"):
        """
        Determines whether to use Live Hardware readings or Manual Inputs.
        Adheres strictly to rules:
        - Retains Hardware Mode as long as ESP32 connection is physically active.
        - Never automatically switches to manual mode due to a temporary delay or timeout.
        - Genuinely disconnected hardware displays 'Hardware Disconnected'.
        - Automatic restoration when hardware reconnects.
        """
        hardware_connected = self.is_hardware_connected()

        # If user explicitly chooses Manual Input
        if mode == "Manual Input":
            return manual_inputs, False, "Manual Input Mode (Simulation)"

        # Check for WiFi telemetry fallback if USB is not connected
        if not hardware_connected:
            wifi_data = self.check_wifi_iot_telemetry(max_age_seconds=20)
            if self.connection_type.startswith("WiFi") and wifi_data:
                self.latest_telemetry = wifi_data
                hardware_connected = True

        # Mode: Force Hardware Only
        if mode == "Force Hardware Only":
            if hardware_connected:
                telemetry_to_use = self.latest_telemetry if self.latest_telemetry else manual_inputs
                return telemetry_to_use, True, f"Live Hardware ({self.connection_type})"
            else:
                return manual_inputs, False, "Hardware Offline / Waiting for Signal"

        # Mode: Auto-Detect Hardware (Default)
        if hardware_connected:
            if self.latest_telemetry:
                # Add warnings to status string if specific sensors have issues
                status_msg = f"Live Hardware Connected ({self.connection_type})"
                if not self.latest_telemetry.get('npk_valid', False):
                    status_msg += " — ⚠️ NPK Sensor Not Responding"
                return self.latest_telemetry, True, status_msg
            else:
                # Connected to port, waiting for initial frame
                return manual_inputs, True, f"Hardware Port Connected ({self.connection_type}) — Acquiring sensor frames..."

        # Hardware genuinely disconnected
        return manual_inputs, False, "Hardware Disconnected (Using Manual Input)"


# Global shared instance
_global_hw_manager = None

def get_hardware_manager() -> HardwareManager:
    global _global_hw_manager
    if _global_hw_manager is None:
        _global_hw_manager = HardwareManager()
    return _global_hw_manager
