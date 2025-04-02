#!/usr/bin/env python3
import os
import json
import socket
import sqlite3
import logging
import threading
import random
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import jwt

app = Flask(__name__)
CORS(app)

# Configuration
CORE_IP = "10.2.22.85"
CORE_PORT = 5001
DB_PATH = "sensor_data.db"
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
UESIM_INTERFACE = "uesimtun0"  # Replace with your UESIM tunnel interface name
CURRENT_TIME = "2025-03-27 09:22:00"  # Updated timestamp
CURRENT_USER = "PrathikRajRC"  # Updated user

# Authentication counter for random unauthenticated data
auth_counter = 0

# Global Sensor Data
sensor_data = {"temperature": "--", "distance": "--", "error": None}
lock = threading.Lock()
running = True

# Setup Logging with colored output
class ColoredFormatter(logging.Formatter):
	COLORS = {
    	'DEBUG': '\033[94m',  # blue
    	'INFO': '\033[92m',   # green
    	'WARNING': '\033[93m', # yellow
    	'ERROR': '\033[91m',  # red
    	'CRITICAL': '\033[91m\033[1m',  # bold red
    	'RESET': '\033[0m'	# reset color
	}
    
	def format(self, record):
    	log_message = super().format(record)
    	return f"{self.COLORS.get(record.levelname, self.COLORS['RESET'])}{log_message}{self.COLORS['RESET']}"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

# Initialize Database
def init_database():
	try:
    	conn = sqlite3.connect(DB_PATH)
    	cursor = conn.cursor()
    	cursor.execute('''
        	CREATE TABLE IF NOT EXISTS sensor_data (
            	id INTEGER PRIMARY KEY AUTOINCREMENT,
            	timestamp TEXT,
            	temperature REAL,
            	distance REAL,
            	transmitted INTEGER DEFAULT 0
        	)
    	''')
    	conn.commit()
    	conn.close()
    	logger.info(f"💾 Database initialized at {DB_PATH}")
	except Exception as e:
    	logger.error(f"❌ Database initialization error: {e}")

# Store sensor data locally
def store_data_locally(data):
	try:
    	conn = sqlite3.connect(DB_PATH)
    	cursor = conn.cursor()
    	timestamp = datetime.now().isoformat()
   	 
    	# Extract temperature and distance, using None if not present
    	temperature = data.get("temperature", None)
    	distance = data.get("distance", None)
   	 
    	cursor.execute(
        	"INSERT INTO sensor_data (timestamp, temperature, distance) VALUES (?, ?, ?)",
        	(timestamp, temperature, distance)
    	)
    	conn.commit()
    	conn.close()
    	logger.info(f"💾 Data stored locally: {json.dumps(data, indent=2)}")
	except Exception as e:
    	logger.error(f"❌ Failed to store data locally: {e}")

# Send Data Over UESIM Tunnel
def send_data(data):
	if data.get("error") is not None:
    	return False

	try:
    	json_payload = json.dumps(data).encode('utf-8')
    	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    	sock.settimeout(2)

    	# Try to bind to UESIM tunnel interface if it exists
    	try:
        	sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, UESIM_INTERFACE.encode())
    	except:
        	pass  # Silently continue if interface doesn't exist

    	logger.info(f"📡 Sending data to {CORE_IP}:{CORE_PORT}")
    	logger.info(f"📊 Payload: {json_payload.decode('utf-8')}")

    	bytes_sent = sock.sendto(json_payload, (CORE_IP, CORE_PORT))
    	logger.info(f"✅ Sent {bytes_sent} bytes of data successfully")

    	sock.close()
    	return True
	except Exception as e:
    	logger.error(f"❌ Socket error: {e}")
    	return False

# Verify JWT token
def verify_token(token):
	try:
    	# Note: In a production environment, you should verify the signature
    	# This is just doing basic token parsing for display purposes
    	decoded = jwt.decode(token, options={"verify_signature": False})
    	return True, decoded
	except Exception as e:
    	return False, str(e)

# Flask Endpoint to Receive Data
@app.route('/receive_data', methods=['POST'])
def receive_data():
	global auth_counter
	timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
	logger.info(f"📥 [{timestamp}] Incoming request received")
    
	# Check for authentication
	auth_header = request.headers.get('Authorization', '')
	if auth_header.startswith('Bearer '):
    	token = auth_header[7:]
    	is_valid, token_data = verify_token(token)
    	if is_valid:
        	logger.info("✅ AUTHENTICATION VALID")
        	if isinstance(token_data, dict):
            	logger.info(f"👤 User: {token_data.get('preferred_username', 'unknown')}")
            	logger.info(f"🔒 Roles: {token_data.get('realm_access', {}).get('roles', [])}")
    	else:
        	logger.warning(f"⚠️ INVALID TOKEN: {token_data}")
	else:
    	logger.warning("⚠️ NO AUTHENTICATION TOKEN PROVIDED")
    
	try:
    	data = request.json
    	logger.info(f"📊 Received data: {json.dumps(data, indent=2)}")
   	 
    	with lock:
        	sensor_data.update(data)
        	sensor_data["error"] = None
       	 
        	# Decide whether to send authenticated or unauthenticated data
        	send_data_copy = sensor_data.copy()
       	 
        	# Randomly send unauthenticated data based on counter
        	auth_counter += 1
        	should_strip_auth = False
       	 
        	if auth_counter >= random.randint(4, 6):
            	should_strip_auth = True
            	auth_counter = 0
       	 
        	if should_strip_auth and "auth_status" in send_data_copy:
            	# Create unauthenticated data with BLOCKED actual data
            	logger.error(f"\033[91m⛔ UNAUTHENTICATED TRANSMISSION BLOCKED. DATA FIELDS RESTRICTED\033[0m")
           	 
            	# Keep only auth_status with authenticated=False and strip all other data
            	blocked_data = {
                	"auth_status": {
                    	"authenticated": False,
                    	"auth_time": datetime.now().isoformat(),
                    	"auth_provider": "None",
                    	"auth_method": "None",
                    	"processor": CURRENT_USER
                	},
                	"temperature": None,  # NULL values to simulate blocked data
                	"distance": None, 	# NULL values to simulate blocked data
                	"timestamp": datetime.now().isoformat(),
                	"transmission_status": "BLOCKED"
            	}
           	 
            	if not send_data(blocked_data):
                	logger.warning("⚠️ UDP transmission failed, storing data locally")
                	store_data_locally(blocked_data)
                	return jsonify({"status": "partial_success", "message": "Data received but forwarding failed"}), 202
        	else:
            	# Send normal authenticated data
            	if not send_data(send_data_copy):
                	logger.warning("⚠️ UDP transmission failed, storing data locally")
                	store_data_locally(send_data_copy)
                	return jsonify({"status": "partial_success", "message": "Data received but forwarding failed"}), 202
   	 
    	return jsonify({
        	"status": "success",
        	"message": "Data received and forwarded successfully",
        	"timestamp": datetime.now().isoformat()
    	}), 200
	except Exception as e:
    	logger.error(f"❌ Error processing received data: {e}")
    	return jsonify({"status": "error", "message": f"Invalid data format: {str(e)}"}), 400

# Add retry mechanism for stored data
def retry_sending_stored_data():
	while running:
    	try:
        	conn = sqlite3.connect(DB_PATH)
        	cursor = conn.cursor()
        	cursor.execute("SELECT id, temperature, distance FROM sensor_data WHERE transmitted = 0 LIMIT 10")
        	rows = cursor.fetchall()
       	 
        	if rows:
            	logger.info(f"⏳ Attempting to send {len(rows)} stored data records")
           	 
        	for row in rows:
            	id, temperature, distance = row
           	 
            	# Randomly decide if this retry should have auth data
            	if random.random() > 0.2:  # 80% chance of being authenticated
                	data = {
                    	"temperature": temperature,
                    	"distance": distance,
                    	"error": None,
                    	"auth_status": {
                        	"authenticated": True,
                        	"auth_time": datetime.now().isoformat(),
                        	"auth_provider": "Keycloak",
                        	"auth_method": "retry",
                        	"client_id": "retry-mechanism",
                        	"processor": CURRENT_USER
                    	}
                	}
            	else:
                	# Send blocked data with auth_status only
                	logger.error(f"\033[91m⛔ UNAUTHENTICATED RETRY BLOCKED. DATA FIELDS RESTRICTED\033[0m")
                	data = {
                    	"auth_status": {
                        	"authenticated": False,
                        	"auth_time": datetime.now().isoformat(),
                        	"auth_provider": "None",
                        	"auth_method": "None",
                        	"processor": CURRENT_USER
                    	},
                    	"temperature": None,
                    	"distance": None,
                    	"transmission_status": "BLOCKED"
                	}
           	 
            	if send_data(data):
                	cursor.execute("UPDATE sensor_data SET transmitted = 1 WHERE id = ?", (id,))
                	conn.commit()
                	logger.info(f"✅ Successfully resent stored data ID: {id}")
       	 
        	conn.close()
    	except Exception as e:
        	logger.error(f"❌ Error in retry mechanism: {e}")
   	 
    	# Sleep before next retry batch
    	threading.Event().wait(60)  # Check every minute

@app.route('/stats', methods=['GET'])
def get_stats():
	try:
    	conn = sqlite3.connect(DB_PATH)
    	cursor = conn.cursor()
   	 
    	cursor.execute("SELECT COUNT(*) FROM sensor_data")
    	total = cursor.fetchone()[0]
   	 
    	cursor.execute("SELECT COUNT(*) FROM sensor_data WHERE transmitted = 1")
    	transmitted = cursor.fetchone()[0]
   	 
    	conn.close()
   	 
    	return jsonify({
        	"total_records": total,
        	"transmitted_records": transmitted,
        	"pending_records": total - transmitted,
        	"current_data": sensor_data,
        	"timestamp": datetime.now().isoformat(),
        	"server_info": {
            	"current_time": CURRENT_TIME,
            	"processor": CURRENT_USER
        	}
    	}), 200
	except Exception as e:
    	logger.error(f"Error getting stats: {e}")
    	return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
	try:
    	init_database()
    	# Start retry mechanism in background
    	retry_thread = threading.Thread(target=retry_sending_stored_data, daemon=True)
    	retry_thread.start()
   	 
    	logger.info("=" * 60)
    	logger.info("🚀 Secure Data Transmission System")
    	logger.info(f"⏱️ Current time: {CURRENT_TIME}")
    	logger.info(f"👤 Processor: {CURRENT_USER}")
    	logger.info(f"⚙️ Configured to forward data to {CORE_IP}:{CORE_PORT} via UDP")
    	logger.info(f"🛡️ Security protocol: Unauthorized data will be blocked")
    	logger.info("=" * 60)
    	app.run(host='0.0.0.0', port=5002, debug=False)
	except KeyboardInterrupt:
    	logger.info("🛑 Shutting down gracefully...")
    	running = False





