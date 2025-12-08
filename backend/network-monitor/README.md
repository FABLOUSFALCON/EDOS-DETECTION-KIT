# Network Monitor Service

🔍 **Real-time network and system monitoring service for EDOS Detection Dashboard**

## Overview

This standalone Python service monitors:

- 📊 **Network Traffic**: Upload/download speeds in real-time
- 💻 **System Resources**: CPU, memory, and disk I/O metrics
- 🔒 **Port Security**: Open ports, running services, and risk assessment
- ⚡ **Live Updates**: Publishes data to Redis for dashboard consumption

## Architecture

```
┌─────────────────┐    ┌─────────┐    ┌──────────────┐    ┌─────────────┐
│ Network Monitor │───▶│  Redis  │───▶│ Backend API  │───▶│  Frontend   │
│    (Python)     │    │ Channel │    │   (FastAPI)  │    │ (Next.js)   │
└─────────────────┘    └─────────┘    └──────────────┘    └─────────────┘
```

## Data Structure

The service publishes this JSON structure to Redis:

```json
{
  "networkSpeeds": [
    {
      "timestamp": "2025-12-08T10:30:00Z",
      "download": 85.5,
      "upload": 23.2
    }
  ],
  "systemMetrics": {
    "cpu": {
      "usage": 45.2,
      "cores": 8,
      "processes": 203
    },
    "memory": {
      "used": 8.5,
      "total": 16,
      "available": 7.5
    },
    "disk": {
      "used": 450,
      "total": 1000,
      "readSpeed": 120.5,
      "writeSpeed": 85.3
    }
  },
  "openPorts": [
    {
      "port": 22,
      "protocol": "TCP",
      "service": "SSH",
      "program": "sshd",
      "status": "open",
      "risk": "medium"
    }
  ],
  "isConnected": true,
  "lastUpdate": "2025-12-08T10:30:00Z"
}
```

## Installation

```bash
# Navigate to the network monitor directory
cd backend/network-monitor

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Start the Service

```bash
python main.py
```

### Check Redis Data

```bash
# View latest data
redis-cli GET "network_analysis:latest"

# Subscribe to real-time updates
redis-cli SUBSCRIBE "network_analysis:updates"
```

## Configuration

- **Redis Host**: `localhost` (configurable in `main.py`)
- **Redis Port**: `6379` (configurable in `main.py`)
- **Update Interval**: `2 seconds` (configurable in `main.py`)
- **Network Speed History**: `30 data points` (1 minute of history)

## Features

### ✅ Implemented

- Real-time system metrics collection (CPU, memory, disk)
- Open port scanning with service detection
- Risk assessment for security analysis
- Redis publishing with expiration
- Graceful shutdown handling
- Comprehensive logging

### 🚧 Future Enhancements

- Actual network speed calculation (currently simulated)
- Network interface selection
- Custom port scanning ranges
- Historical data storage
- Performance optimizations
- Docker containerization

## Logging

Logs are written to:

- **Console**: Real-time monitoring output
- **File**: `network_monitor.log` for persistent logging

## Security

### Port Risk Assessment

- **High Risk**: Telnet (23), FTP (21), RDP (3389), Windows SMB
- **Medium Risk**: SSH (22), Mail servers, Databases
- **Low Risk**: HTTP/HTTPS, DNS, other standard services

## Dependencies

- **redis**: Redis client for data publishing
- **psutil**: System and process utilities
- **aioredis**: Async Redis client support
- **Python 3.8+**: Required for async/await support

## Integration

This service is designed to work with:

- **Backend API**: FastAPI service that subscribes to Redis
- **Frontend Dashboard**: React/Next.js network analysis page
- **Existing Infrastructure**: Cicflowmeter and ML prediction services

---

**Part of EDOS Detection Kit** 🛡️
