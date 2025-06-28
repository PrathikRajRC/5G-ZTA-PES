# Zero Trust Architecture for Securing Smart IoT Devices in 5G Networks

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Last Updated](https://img.shields.io/badge/last%20updated-May%202025-brightgreen)

## Project Overview

Zero Trust Architecture for Securing Smart IoT Devices in 5G Networks is a comprehensive implementation of Zero Trust Architecture (ZTA) designed specifically for resource-constrained IoT devices operating in 5G network environments. This framework addresses the security challenges inherent in dynamic 5G networks by removing implicit trust and enforcing continuous authentication for all connected devices.

## Key Features

- **OAuth 2.0 Authentication**: Integration with Keycloak for robust identity verification and access control
- **Hybrid Encryption**: RSA for secure key exchange + ChaCha20-Poly1305 for lightweight authenticated encryption
- **Real-time Monitoring**: Dashboard for visualizing authenticated vs. unauthenticated transmissions
- **5G Network Integration**: Compatible with Open5GS core network and UERANSIM
- **Resource-Optimized Design**: Tailored for constrained IoT devices (ESP32)
- **UDP-based Secure Communication**: Encrypted channel for device-to-network communication

## System Architecture

![Network Architecture](./Network.png)

The system employs a multi-layered security approach:

1. **IoT Device Layer**: ESP32 sensors with temperature and distance measurement capabilities
2. **Edge Layer**: Raspberry Pi configured as User Equipment (UE) for 5G connectivity
3. **Authentication Layer**: Keycloak OAuth 2.0 server for identity management and token issuance
4. **Core Network Layer**: Open5GS-based 5G core network for simulated production environment

## Installation Requirements

### Prerequisites
- Python 3.8+
- Open5GS
- UERANSIM
- Keycloak server
- ESP32 with micropython support
- Raspberry Pi 4 or newer

### Setup Instructions

```bash
# Clone the repository
git clone https://github.com/PrathikRajRC/5G-ZTA-PES.git
cd 5G-ZTA-PES

# Install dependencies
pip install -r requirements.txt

# Configure Keycloak settings
cp config.example.py config.py
# Edit config.py with your Keycloak server details

# Start the authentication service
python zta_service.py

# Run the dashboard (in a separate terminal)
python dashboard.py
```

## Usage Guide

1. **Device Registration**:
   - Register IoT devices on the Keycloak server
   - Configure device credentials in the firmware

2. **Secure Communication**:
   - Deploy the ESP32 firmware (`esp32/main.py`)
   - The device will authenticate with Keycloak and receive access tokens
   - All sensor data is encrypted before transmission

3. **Monitoring**:
   - Access the dashboard at `http://localhost:5000`
   - Monitor authenticated devices and data streams
   - View security alerts and access logs

## Dashboard Interface

![Dashboard](./dashboard.png)


## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- This research was conducted at PES University
- Thanks to the Open5GS and UERANSIM communities for their excellent 5G simulation tools
