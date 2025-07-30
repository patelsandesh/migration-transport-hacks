# TCP Performance Testing Suite

This suite provides comprehensive tools for testing TCP bandwidth performance with SSL/TLS encryption and Unix domain socket integration.

## Overview

The suite consists of four main components:
- **TCP SSL Sender/Receiver**: Direct TCP bandwidth testing with SSL encryption
- **Unix Domain Socket Bridge**: Local IPC for data forwarding
- **Hybrid Mode**: Combines TCP SSL with Unix socket forwarding

## Components

### 1. TCP SSL Communication
- `send.py` - SSL TCP client for bandwidth testing
- `receive.py` - SSL TCP server with optional Unix socket forwarding

### 2. Unix Domain Socket Communication  
- `unix-sender.py` - Unix domain socket client
- `unix-receiver.py` - Unix domain socket server

## Script Execution Order

### For TCP SSL Testing Only
```bash
# Terminal 1 - Start the receiver first
python3 receive.py

# Terminal 2 - Start the sender
python3 send.py
```

### For Hybrid Mode (TCP SSL with Unix Socket Forwarding)
```bash
# Terminal 1 - Start the Unix receiver first (data destination)
python3 unix-receiver.py

# Terminal 2 - Start the TCP receiver with Unix forwarding enabled
python3 receive.py --forward-to-unix

# Terminal 3 - Start the TCP sender
python3 send.py

# Terminal 4 - Start the TCP sender
python3 unix-sender.py
```

## Features

- **SSL/TLS Encryption**: Mutual certificate authentication
- **Real-time Metrics**: Bandwidth reporting every second
- **Rate Limiting**: Configurable target bandwidth
- **Multi-threading**: Concurrent client support
- **Unix Socket Integration**: Data forwarding capabilities
- **Comprehensive Statistics**: Detailed performance reports

## Prerequisites

### SSL Certificates
The suite requires SSL certificates in `../../migrate-websocket/certs/`:



