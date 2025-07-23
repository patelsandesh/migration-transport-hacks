# Secure WebSocket QEMU Migration

This project provides secure WebSocket-based QEMU migration with TLS encryption and mutual certificate authentication.

## Features

- TLS encryption for all WebSocket communications
- Mutual certificate authentication (client and server verification)
- Bidirectional data forwarding between QEMU unix sockets and WebSocket connections
- Progress logging and error handling

## Architecture

The migration process involves four main scripts running in a coordinated manner across the source and destination hosts.

```
    Source Host                                 Destination Host
┌───────────────────┐                           ┌────────────────────┐
│   QEMU Source VM  │                           │   QEMU Dest VM     │
└───────────────────┘                           └────────────────────┘
         │                                                 ▲
         │ 1. migrate                                      │ 4. migrate-incoming
         │    (unix socket)                                │    (unix socket)
         ▼                                                 │
┌───────────────────┐      Secure WebSocket Tunnel ┌────────────────────┐
│ websocket-        ├<═══════════════════════════>│ websocket-         │
│ client.py         │                             │ server.py          │
│ (Unix-to-WS)      │                             │ (WS-to-Unix)       │
└───────────────────┘                             └────────────────────┘
         ▲                                                 ▲
         │ 2. Start Migration                            │ 3. Prepare for Migration
         │                                                 │
┌───────────────────┐                           ┌────────────────────┐
│ unix-send-        │                           │ unix-receive-      │
│ websocket.py      │                           │ websocket.py       │
│ (QMP Client)      │                           │ (QMP Client)       │
└───────────────────┘                           └────────────────────┘
```

## Setup

### 1. Generate Certificates

First, generate the required certificates:

```bash
python3 generate_certificates.py --server-cn your-server-hostname
```

This creates a `certs/` directory with:
- `ca.pem` - Certificate Authority certificate
- `server-cert.pem` - Server certificate
- `client-cert.pem` - Client certificate
- `*-key.pem` - Private keys

### 2. Copy Certificates

Copy the certificates to both source and destination machines:

**On destination machine:**
```bash
# Copy all certificate files
scp certs/* destination-host:/path/to/certs/
```

**On source machine:**
```bash
# Copy client certificate, key, and CA certificate
scp certs/client-cert.pem certs/client-key.pem certs/ca.pem source-host:/path/to/certs/
```

## File Descriptions

*   **`websocket-migration-server.py` (Destination Host):** This script runs on the destination machine. It starts a secure WebSocket server that listens for a connection from the `websocket-migration-client.py`. Once a client connects, it waits for the destination QEMU to create a migration Unix socket (triggered by `unix-receive-websocket.py`) and then forwards all data from the WebSocket connection to this Unix socket.

*   **`websocket-migration-client.py` (Source Host):** This script runs on the source machine. It connects to the `websocket-migration-server.py` on the destination host using TLS. After establishing a connection, it creates a local Unix socket that the source QEMU will use as its migration target. It forwards all data from the local Unix socket to the WebSocket connection.

*   **`unix-receive-websocket.py` (Destination Host):** This is a QMP (QEMU Machine Protocol) client script. It connects to the destination QEMU instance and issues the `migrate-incoming` command. This tells the destination QEMU to start listening for migration data on a specified Unix socket.

*   **`unix-send-websocket.py` (Source Host):** This is a QMP client script. It connects to the source QEMU instance and issues the `migrate` command, pointing to the Unix socket created by `websocket-migration-client.py`. This initiates the migration process.

## Configuration

### Server Configuration
- Default port: 8766 (wss://)
- Host: 0.0.0.0 (all interfaces)
- Certificates directory: `./certs`

### Client Configuration
- Server URL: Update in `websocket-migration-client.py`
- Certificates directory: `./certs`

## Dependencies

The WebSocket scripts require the `websockets` library. Install it using:

```bash
pip install websockets
```

## How to Run

The scripts must be executed in a specific order. You will need two terminals on the source host and two on the destination host.

#### Step 1: On the **Destination Host** (Terminal 1)
Start the secure WebSocket proxy server. It will wait for a client to connect.
```bash
python3 websocket-migration-server.py
```

#### Step 2: On the **Source Host** (Terminal 1)
Start the secure WebSocket proxy client. It will connect to the server.
```bash
python3 websocket-migration-client.py
```
After this step, the WebSocket tunnel is established. The client will create a local Unix socket and wait for the source QEMU to connect.

#### Step 3: On the **Destination Host** (Terminal 2)
Prepare the destination QEMU to receive the migration.
```bash
python unix-receive-websocket.py
```
This script will command QEMU to listen on the Unix socket. The `websocket-migration-server.py` will detect this and complete its connection, ready to forward data.

#### Step 4: On the **Source Host** (Terminal 2)
Start the migration.
```bash
python unix-send-websocket.py
```
This script commands the source QEMU to begin migrating to the Unix socket managed by the `websocket-migration-client.py`. The migration data will now flow across the network via the secure WebSocket.

You can monitor the progress in all four terminals.

## Security Features

- **TLS 1.2+ encryption** for all data in transit
- **Mutual authentication** using X.509 certificates
- **Certificate validation** against custom CA
- **Secure key storage** with proper file permissions

## Troubleshooting

### Certificate Issues
```bash
# Verify certificates
openssl verify -CAfile certs/ca.pem certs/server-cert.pem
openssl verify -CAfile certs/ca.pem certs/client-cert.pem

# Check certificate details
openssl x509 -in certs/server-cert.pem -text -noout
```

### Connection Issues
- Ensure firewall allows port 8766
- Verify certificate files exist and have correct permissions
- Check server hostname matches certificate CN or SAN
- Verify CA certificate is the same on both machines

### Debug Logging
Set environment variable for verbose logging:
```bash
export PYTHONPATH=.
python3 -m logging.basicConfig level=DEBUG websocket-migration-server.py
```

## Advantages of Secure WebSocket over TCP

- **Standardized Protocol:** WebSocket is a well-established web standard
- **Firewall Friendly:** Often easier to traverse firewalls and proxies
- **Built-in Framing:** WebSocket handles message framing automatically
- **Extensible:** Easy to add authentication, compression, or other features
- **Browser Compatible:** Can potentially be used with web-based management tools
- **Enhanced Security:** TLS encryption and mutual authentication ensure secure communication
