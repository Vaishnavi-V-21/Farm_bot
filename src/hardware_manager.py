"""
=====================================================================================
Project Title : Farm Bot: Hardware & Sensor Manager
File          : src/hardware_manager.py
Description   : Auto-detects connected hardware (USB Serial COM port or WiFi IoT),
                reads real-time sensor telemetry, and seamlessly falls back to 
                manual input if hardware is disconnected.
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
        
        # Serial reader thread
        self._serial_thread = None
        self._serial_running = True
        self._active_serial = None
        
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
                            self._active_serial = ser
                            self.port_name = target_port
                            print(f"[HARDWARE]: Connected to USB Serial on {target_port} @ {self.baudrate} baud")
                        except Exception as e:
                            self._active_serial = None
                            time.sleep(2.0)
                            continue
                    else:
                        # No serial hardware plugged in
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
                        print(f"[HARDWARE]: Lost connection to USB Serial on {self.port_name}")
                        if self._active_serial:
                            try:
                                self._active_serial.close()
                            except Exception:
                                pass
                        self._active_serial = None
                        self.port_name = None
                        time.sleep(2.0)
                    except Exception as e:
                        time.sleep(0.5)

            except Exception as e:
                time.sleep(2.0)

    def parse_serial_line(self, line: str):
        """
        Parses incoming serial line. Handles both JSON strings and 
        formatted key-value text lines from the ESP32.
        """
        line = line.strip()
        if not line:
            return None

        # 1. Try parsing direct JSON
        if "{" in line and "}" in line:
            try:
                # Extract JSON substring if wrapped in extra text
                start = line.index("{")
                end = line.rindex("}") + 1
                json_str = line[start:end]
                data = json.loads(json_str)
                if "telemetry" in data and isinstance(data["telemetry"], dict):
                    data = data["telemetry"]
                
                # Check for standard fields
                if any(k in data for k in ["temp", "humidity", "hum", "moisture"]):
                    telemetry = {
                        'temp': float(data.get('temp', data.get('temperature', 26.5))),
                        'hum': float(data.get('hum', data.get('humidity', 65.0))),
                        'moisture': float(data.get('moisture', data.get('soil_moisture', 35.0))),
                        'N': int(data.get('N', data.get('nitrogen', 50))),
                        'P': int(data.get('P', data.get('phosphorus', 30))),
                        'K': int(data.get('K', data.get('potassium', 120))),
                        'ph': float(data.get('ph', data.get('soil_ph', 6.5))),
                        'ec': float(data.get('ec', data.get('soil_ec', 1.2))),
                        'pump': int(data.get('pump', data.get('pump_status', 0)))
                    }
                    return telemetry
            except Exception:
                pass

        # 2. Try parsing formatted lines (matching esp32_farm_bot.ino output)
        temp_match = re.search(r"Temperature\s*:\s*([0-9.]+)", line, re.IGNORECASE)
        if temp_match:
            self._partial_reading['temp'] = float(temp_match.group(1))

        hum_match = re.search(r"Humidity\s*:\s*([0-9.]+)", line, re.IGNORECASE)
        if hum_match:
            self._partial_reading['hum'] = float(hum_match.group(1))

        moist_match = re.search(r"Soil Moisture\s*:\s*([0-9.]+)", line, re.IGNORECASE)
        if moist_match:
            self._partial_reading['moisture'] = float(moist_match.group(1))

        n_match = re.search(r"Nitrogen\s*\(?N\)?\s*:\s*([0-9]+)", line, re.IGNORECASE)
        if n_match:
            self._partial_reading['N'] = int(n_match.group(1))

        p_match = re.search(r"Phosphorus\s*\(?P\)?\s*:\s*([0-9]+)", line, re.IGNORECASE)
        if p_match:
            self._partial_reading['P'] = int(p_match.group(1))

        k_match = re.search(r"Potassium\s*\(?K\)?\s*:\s*([0-9]+)", line, re.IGNORECASE)
        if k_match:
            self._partial_reading['K'] = int(k_match.group(1))

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

        # If we have collected at least temperature, humidity, and moisture, produce complete record
        if all(k in self._partial_reading for k in ['temp', 'hum', 'moisture']):
            telemetry = {
                'temp': self._partial_reading.get('temp', 26.5),
                'hum': self._partial_reading.get('hum', 65.0),
                'moisture': self._partial_reading.get('moisture', 35.0),
                'N': self._partial_reading.get('N', 50),
                'P': self._partial_reading.get('P', 30),
                'K': self._partial_reading.get('K', 120),
                'ph': self._partial_reading.get('ph', 6.5),
                'ec': self._partial_reading.get('ec', 1.2),
                'pump': self._partial_reading.get('pump', 0)
            }
            # Reset partial reading for next iteration
            self._partial_reading = {}
            return telemetry

        return None

    def _on_telemetry_received(self, telemetry: dict, conn_type: str):
        """Called whenever fresh telemetry arrives from USB Serial or WiFi."""
        self.latest_telemetry = telemetry
        self.last_received_time = time.time()
        self.connection_type = conn_type
        self.is_connected = True
        
        # Log to database
        try:
            self.db.log_telemetry(telemetry)
        except Exception:
            pass

    def check_wifi_iot_telemetry(self, max_age_seconds=15):
        """Checks if recent telemetry was received via WiFi (logged into SQLite database)."""
        try:
            rows = self.db.fetch_recent_telemetry(1)
            if rows:
                row = rows[0]
                # row: (timestamp, temperature, humidity, soil_moisture, nitrogen, phosphorus, potassium, soil_ec, soil_ph, pump_status)
                # If USB is not connected, use the latest DB telemetry if recently logged
                telemetry = {
                    'temp': float(row[1]),
                    'hum': float(row[2]),
                    'moisture': float(row[3]),
                    'N': int(row[4]),
                    'P': int(row[5]),
                    'K': int(row[6]),
                    'ec': float(row[7]),
                    'ph': float(row[8]),
                    'pump': int(row[9])
                }
                return telemetry
        except Exception:
            pass
        return None

    def get_effective_telemetry(self, manual_inputs: dict, mode: str = "Auto"):
        """
        Determines whether to use Live Hardware readings or Manual Inputs.

        Args:
            manual_inputs: dict of fallback values entered manually by user
            mode: "Auto", "Hardware Only", or "Manual Simulation"

        Returns:
            telemetry: dict of final values to display/use
            is_hardware_active: bool
            status_text: descriptive connection status string
        """
        now = time.time()
        hardware_fresh = (now - self.last_received_time) <= 15.0 if self.last_received_time > 0 else False

        # If USB is not currently feeding, check if WiFi IoT recently fed the database
        if not hardware_fresh:
            # Check receiver / database
            wifi_data = self.check_wifi_iot_telemetry(max_age_seconds=15)
            # Only use if this is a fresh external transmission and not just manual log
            if self.connection_type.startswith("WiFi") and wifi_data:
                self.latest_telemetry = wifi_data
                hardware_fresh = True

        if mode == "Manual Simulation":
            return manual_inputs, False, "Manual Input Mode (Simulation)"

        if mode == "Hardware Only":
            if hardware_fresh and self.latest_telemetry:
                return self.latest_telemetry, True, f"Live Hardware ({self.connection_type})"
            else:
                return manual_inputs, False, "Hardware Offline / Waiting for Signal (Falling back to manual)"

        # Auto Mode (Default)
        if hardware_fresh and self.latest_telemetry:
            return self.latest_telemetry, True, f"Live Hardware Connected ({self.connection_type})"
        else:
            return manual_inputs, False, "Hardware Disconnected (Using Manual Input)"


# Global shared instance
_global_hw_manager = None

def get_hardware_manager() -> HardwareManager:
    global _global_hw_manager
    if _global_hw_manager is None:
        _global_hw_manager = HardwareManager()
    return _global_hw_manager
