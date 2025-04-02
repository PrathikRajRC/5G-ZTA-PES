#!/usr/bin/env python3
import serial
import requests
import json
import logging
import threading
import sys
from flask import Flask, jsonify
from datetime import datetime

# Configuration
SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 115200
KEYCLOAK_URL = "http://localhost:8080"
REALM = "IoT-Auth"
CLIENT_ID = "iot-device-client"
CLIENT_SECRET = "EaNiotSulJ1zOhWOkfhG0SHTnkICjxsh"
TOKEN_URL = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
DATA_SEND_URL = "http://127.0.0.1:5002/receive_data"

# Setup Logging
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(levelname)s - %(message)s',
	handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Flask App
app = Flask(__name__)

def get_token():
	"""Obtain an access token from Keycloak using client credentials"""
	logger.info("📡 Attempting to authenticate with Keycloak using client credentials...")
	try:
    	data = {
        	"grant_type": "client_credentials",
        	"client_id": CLIENT_ID,
        	"client_secret": CLIENT_SECRET
    	}
   	 
    	start_time = datetime.now()
    	response = requests.post(TOKEN_URL, data=data)
    	elapsed_time = (datetime.now() - start_time).total_seconds()
   	 
    	if response.status_code == 200:
        	token_data = response.json()
        	token = token_data.get("access_token")
        	logger.info(f"✅ AUTHENTICATION SUCCESSFUL - Token obtained in {elapsed_time:.2f}s")
        	# Display truncated token for verification
        	truncated_token = token[:10] + "..." + token[-10:] if token else "None"
        	logger.info(f"🔑 Token: {truncated_token}")
        	return token
    	else:
        	logger.error(f"❌ AUTHENTICATION FAILED - HTTP {response.status_code}")
        	logger.error(f"Response: {response.text}")
        	return None
	except requests.RequestException as e:
    	logger.error(f"❌ AUTHENTICATION ERROR: {e}")
    	return None

def read_serial_data():
	"""Read data from serial port"""
	try:
    	ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    	logger.info(f"🔌 Connected to serial port {SERIAL_PORT} at {BAUD_RATE} baud")
   	 
    	while True:
        	raw_data = ser.readline().decode().strip()
        	if raw_data:
            	timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            	logger.info(f"📥 [{timestamp}] RAW DATA RECEIVED: {raw_data}")
           	 
            	try:
                	sensor_data = json.loads(raw_data)
                	logger.info(f"📊 PARSED DATA: {json.dumps(sensor_data, indent=2)}")
               	 
                	# Get authentication token
                	token = get_token()
               	 
                	if token:
                    	# Add authentication metadata before sending
                    	authenticated_data = add_auth_metadata(sensor_data)
                    	send_authenticated_data(authenticated_data, token)
                	else:
                    	logger.error("🚫 No valid token, data not sent")
            	except json.JSONDecodeError:
                	logger.error(f"⚠️ Invalid JSON received: {raw_data}")
	except serial.SerialException as e:
    	logger.error(f"❌ Serial connection error: {e}")
    	logger.info("⏳ Attempting to reconnect in 5 seconds...")
    	threading.Timer(5.0, read_serial_data).start()

def add_auth_metadata(data):
	"""Add authentication metadata to the sensor data"""
	# Create a copy of the original data to avoid modifying it directly
	enhanced_data = data.copy()
    
	# Add authentication metadata
	enhanced_data["auth_status"] = {
    	"authenticated": True,
    	"auth_time": datetime.now().isoformat(),
    	"auth_provider": "Keycloak",
    	"auth_method": "client_credentials",
    	"client_id": CLIENT_ID,
    	"processor": "PrathikRajRC"  # As requested, including the user login
	}
    
	logger.info(f"🔐 Added authentication metadata to data")
	return enhanced_data

def send_authenticated_data(data, token):
	"""Send authenticated data to app_send.py"""
	logger.info("📤 Sending authenticated data...")
    
	headers = {
    	"Authorization": f"Bearer {token}",
    	"Content-Type": "application/json"
	}
    
	try:
    	start_time = datetime.now()
    	response = requests.post(DATA_SEND_URL, json=data, headers=headers)
    	elapsed_time = (datetime.now() - start_time).total_seconds()
   	 
    	if response.status_code == 200:
        	logger.info(f"✅ DATA SENT SUCCESSFULLY in {elapsed_time:.2f}s")
        	logger.info(f"📊 Sent data: {json.dumps(data, indent=2)}")
    	else:
        	logger.error(f"❌ DATA SEND FAILED - HTTP {response.status_code}")
        	logger.error(f"Response: {response.text}")
	except requests.RequestException as e:
    	logger.error(f"❌ DATA SEND ERROR: {e}")

@app.route("/start", methods=["GET"])
def start():
	"""Start serial data reading in a separate thread"""
	logger.info("🚀 Starting serial data reading thread")
	threading.Thread(target=read_serial_data, daemon=True).start()
	return jsonify({"message": "Serial reading started", "timestamp": datetime.now().isoformat()}), 200

@app.route("/auth_status", methods=["GET"])
def auth_status():
	"""Check authentication status with Keycloak"""
	token = get_token()
	if token:
    	return jsonify({
        	"status": "authenticated",
        	"message": "Successfully authenticated with Keycloak",
        	"timestamp": datetime.now().isoformat()
    	}), 200
	else:
    	return jsonify({
        	"status": "unauthenticated",
        	"message": "Failed to authenticate with Keycloak",
        	"timestamp": datetime.now().isoformat()
    	}), 401

@app.route("/health", methods=["GET"])
def health_check():
	"""Simple health check endpoint"""
	return jsonify({
    	"status": "healthy",
    	"timestamp": datetime.now().isoformat()
	}), 200

if __name__ == "__main__":
	logger.info("🌟 ESP32 Reader Server starting...")
	logger.info(f"⚙️ Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
	logger.info(f"⚙️ Processor: PrathikRajRC")
	logger.info(f"⚙️ Server configured for Keycloak at {KEYCLOAK_URL}")
	logger.info(f"⚙️ Reading from {SERIAL_PORT} and forwarding to {DATA_SEND_URL}")
    
	# Start reading serial data immediately
	threading.Thread(target=read_serial_data, daemon=True).start()
    
	app.run(host="0.0.0.0", port=5001)





