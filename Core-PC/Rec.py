#!/usr/bin/env python3
import socket
import json
import logging
import threading
import sqlite3
import os
from datetime import datetime
from flask import Flask, jsonify, render_template

# Setup logging
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(levelname)s - %(message)s',
	handlers=[
    	logging.FileHandler("core_receiver.log"),
    	logging.StreamHandler()
	]
)

# Configuration
LISTEN_IP = "0.0.0.0"  # Listen on all interfaces
LISTEN_PORT = 5001 	# Match the port in edge device
DB_PATH = "sensor_data.db"
CURRENT_TIME = "2025-03-27 10:01:52"  # Updated timestamp
CURRENT_USER = "PrathikRajRC"  # Current user

# Initialize Flask for web dashboard
app = Flask(__name__)

# Global variables
running = True

def init_database():
	"""Create or open database for storing sensor data with authentication"""
	try:
    	conn = sqlite3.connect(DB_PATH)
    	cursor = conn.cursor()
   	 
    	# Check if table exists
    	cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_data'")
    	table_exists = cursor.fetchone() is not None
   	 
    	if not table_exists:
        	# Create new table with all columns
        	cursor.execute('''
            	CREATE TABLE IF NOT EXISTS sensor_data (
                	id INTEGER PRIMARY KEY AUTOINCREMENT,
                	timestamp TEXT,
                	device_ip TEXT,
                	temperature REAL,
                	distance REAL,
                	authenticated INTEGER DEFAULT 0,
                	auth_provider TEXT,
                	auth_method TEXT,
                	auth_time TEXT,
                	processor TEXT
            	)
        	''')
    	else:
        	# Check if auth columns already exist
        	cursor.execute("PRAGMA table_info(sensor_data)")
        	columns = [column[1] for column in cursor.fetchall()]
       	 
        	# Add missing columns if needed
        	if 'authenticated' not in columns:
            	cursor.execute("ALTER TABLE sensor_data ADD COLUMN authenticated INTEGER DEFAULT 0")
        	if 'auth_provider' not in columns:
            	cursor.execute("ALTER TABLE sensor_data ADD COLUMN auth_provider TEXT")
        	if 'auth_method' not in columns:
            	cursor.execute("ALTER TABLE sensor_data ADD COLUMN auth_method TEXT")  
        	if 'auth_time' not in columns:
            	cursor.execute("ALTER TABLE sensor_data ADD COLUMN auth_time TEXT")
        	if 'processor' not in columns:
            	cursor.execute("ALTER TABLE sensor_data ADD COLUMN processor TEXT")
   	 
    	conn.commit()
    	conn.close()
    	logging.info(f"Database initialized at {DB_PATH}")
	except Exception as e:
    	logging.error(f"Database initialization error: {e}")

def store_data(data, device_ip):
	"""Store received sensor data in database with authentication info"""
	try:
    	conn = sqlite3.connect(DB_PATH)
    	cursor = conn.cursor()
    	timestamp = datetime.now().isoformat()
   	 
    	# Extract authentication info if present
    	auth_status = data.get("auth_status", {})
    	authenticated = 1 if auth_status.get("authenticated", False) else 0
    	auth_provider = auth_status.get("auth_provider", "")
    	auth_method = auth_status.get("auth_method", "")
    	auth_time = auth_status.get("auth_time", "")
    	processor = auth_status.get("processor", "")
   	 
    	# Insert with authentication info
    	cursor.execute(
        	"""INSERT INTO sensor_data
           	(timestamp, device_ip, temperature, distance,
            	authenticated, auth_provider, auth_method, auth_time, processor)
           	VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        	(timestamp, device_ip, data.get("temperature"), data.get("distance"),
         	authenticated, auth_provider, auth_method, auth_time, processor)
    	)
   	 
    	conn.commit()
    	conn.close()
    	if authenticated:
        	logging.info(f"Stored authenticated data from {device_ip} (Provider: {auth_provider})")
    	else:
        	logging.warning(f"Stored unauthenticated data from {device_ip} - data will be nullified in display")
    	return True
	except Exception as e:
    	logging.error(f"Failed to store data: {e}")
    	return False

def start_udp_receiver():
	"""Start UDP receiver for sensor data"""
	try:
    	# Create UDP socket
    	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    	sock.bind((LISTEN_IP, LISTEN_PORT))
    	sock.settimeout(1)  # Allow checking running flag periodically
   	 
    	logging.info(f"UDP Receiver started on {LISTEN_IP}:{LISTEN_PORT}")
    	logging.info("Waiting for sensor data...")
   	 
    	while running:
        	try:
            	# Receive data
            	data, addr = sock.recvfrom(1024)
            	device_ip = addr[0]
            	timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
           	 
            	try:
                	# Parse JSON data
                	message = json.loads(data.decode('utf-8'))
               	 
                	# Check for authentication status
                	auth_info = ""
                	if "auth_status" in message and message["auth_status"].get("authenticated", False):
                    	auth_provider = message["auth_status"].get("auth_provider", "Unknown")
                    	auth_info = f" [Authenticated via {auth_provider}]"
                	else:
                    	auth_info = " [UNAUTHENTICATED - DATA WILL BE NULLIFIED]"
               	 
                	logging.info(f"Data received from {device_ip}: {message}")
               	 
                	# Store data
                	if "temperature" in message and "distance" in message:
                    	temp = message["temperature"]
                    	dist = message["distance"]
                    	logging.info(f"From {device_ip}: Temperature: {temp}°C, Distance: {dist}cm{auth_info}")
                   	 
                    	# Store in database
                    	store_data(message, device_ip)
                   	 
                    	# Optional: Send acknowledgment
                    	try:
                        	sock.sendto(b'{"status":"received"}', addr)
                    	except:
                        	pass
                   	 
            	except json.JSONDecodeError:
                	logging.error(f"Invalid JSON received from {device_ip}")
            	except Exception as e:
                	logging.error(f"Error processing message: {e}")
               	 
        	except socket.timeout:
            	continue  # Just loop again
        	except Exception as e:
            	logging.error(f"Receiver error: {e}")
           	 
    	sock.close()
    	logging.info("UDP receiver stopped")
   	 
	except Exception as e:
    	logging.error(f"Failed to start receiver: {e}")

# Flask Routes
@app.route('/')
def dashboard():
	return render_template('core_dashboard.html')

@app.route('/api/data')
def get_data():
	"""Get the latest sensor data including authentication status - nullify unauth data"""
	try:
    	conn = sqlite3.connect(DB_PATH)
    	conn.row_factory = sqlite3.Row
    	cursor = conn.cursor()
   	 
    	# Modified query to return NULL for temperature and distance when not authenticated
    	cursor.execute("""
        	SELECT
            	timestamp,
            	device_ip,
            	CASE WHEN authenticated = 1 THEN temperature ELSE NULL END as temperature,
            	CASE WHEN authenticated = 1 THEN distance ELSE NULL END as distance,
            	authenticated,
            	auth_provider,
            	auth_method,
            	auth_time,
            	processor
        	FROM sensor_data
        	ORDER BY timestamp DESC
        	LIMIT 100
    	""")
   	 
    	rows = cursor.fetchall()
    	data = [dict(row) for row in rows]
    	conn.close()
   	 
    	# Include server info
    	server_info = {
        	"current_time": CURRENT_TIME,
        	"processor": CURRENT_USER
    	}
   	 
    	return jsonify({"data": data, "server_info": server_info})
	except Exception as e:
    	logging.error(f"Error fetching data: {e}")
    	return jsonify({"error": str(e)}), 500

@app.route('/api/devices')
def get_devices():
	"""Get list of devices that have sent data with authentication stats"""
	try:
    	conn = sqlite3.connect(DB_PATH)
    	conn.row_factory = sqlite3.Row
    	cursor = conn.cursor()
   	 
    	cursor.execute("""
        	SELECT device_ip, COUNT(*) as count,
        	MAX(timestamp) as last_seen,
        	SUM(CASE WHEN authenticated = 1 THEN 1 ELSE 0 END) as authenticated_count
        	FROM sensor_data
        	GROUP BY device_ip
    	""")
   	 
    	rows = cursor.fetchall()
    	devices = [dict(row) for row in rows]
    	conn.close()
   	 
    	# Include server info
    	server_info = {
        	"current_time": CURRENT_TIME,
        	"processor": CURRENT_USER
    	}
   	 
    	return jsonify({"devices": devices, "server_info": server_info})
	except Exception as e:
    	logging.error(f"Error fetching devices: {e}")
    	return jsonify({"error": str(e)}), 500

@app.route('/api/stats')
def get_stats():
	"""Get overall statistics including authentication rates"""
	try:
    	conn = sqlite3.connect(DB_PATH)
    	cursor = conn.cursor()
   	 
    	# Get total count
    	cursor.execute("SELECT COUNT(*) FROM sensor_data")
    	total_count = cursor.fetchone()[0]
   	 
    	# Get authenticated count
    	cursor.execute("SELECT COUNT(*) FROM sensor_data WHERE authenticated = 1")
    	auth_count = cursor.fetchone()[0]
   	 
    	# Get device count
    	cursor.execute("SELECT COUNT(DISTINCT device_ip) FROM sensor_data")
    	device_count = cursor.fetchone()[0]
   	 
    	# Calculate auth percent
    	auth_percent = 0
    	if total_count > 0:
        	auth_percent = round((auth_count / total_count) * 100, 1)
   	 
    	conn.close()
   	 
    	# Include server info
    	server_info = {
        	"current_time": CURRENT_TIME,
        	"processor": CURRENT_USER
    	}
   	 
    	return jsonify({
        	"total_readings": total_count,
        	"authenticated_readings": auth_count,
        	"device_count": device_count,
        	"auth_percent": auth_percent,
        	"server_info": server_info
    	})
	except Exception as e:
    	logging.error(f"Error fetching stats: {e}")
    	return jsonify({"error": str(e)}), 500

@app.route('/api/clear-data', methods=['POST'])
def clear_data():
	"""Clear all sensor data from the database"""
	try:
    	conn = sqlite3.connect(DB_PATH)
    	cursor = conn.cursor()
   	 
    	# Get count before deletion
    	cursor.execute("SELECT COUNT(*) FROM sensor_data")
    	count_before = cursor.fetchone()[0]
   	 
    	# Delete all data
    	cursor.execute("DELETE FROM sensor_data")
   	 
    	# Reset the auto-increment counter
    	cursor.execute("DELETE FROM sqlite_sequence WHERE name='sensor_data'")
   	 
    	conn.commit()
    	conn.close()
   	 
    	# Log the operation
    	logging.warning(f"⚠️ ALL DATA CLEARED: {count_before} records deleted by {CURRENT_USER}")
   	 
    	return jsonify({
        	"status": "success",
        	"message": f"All sensor data cleared successfully. {count_before} records deleted.",
        	"timestamp": CURRENT_TIME
    	}), 200
	except Exception as e:
    	logging.error(f"Error clearing data: {e}")
    	return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
	try:
    	# Initialize the database with auth columns
    	init_database()
   	 
    	# Print startup banner
    	print("=" * 60)
    	print(f"CORE NETWORK SENSOR RECEIVER")
    	print(f"Current time: {CURRENT_TIME}")
    	print(f"Processor: {CURRENT_USER}")
    	print(f"UDP Server: {LISTEN_IP}:{LISTEN_PORT}")
    	print(f"Web Dashboard: http://0.0.0.0:8080")
    	print("=" * 60)
   	 
    	# Start UDP receiver in a separate thread
    	receiver_thread = threading.Thread(target=start_udp_receiver, daemon=True)
    	receiver_thread.start()
   	 
    	# Start Flask web interface
    	app.run(host='0.0.0.0', port=8080, debug=False)
   	 
	except KeyboardInterrupt:
    	logging.info("Shutting down gracefully...")
    	running = False

