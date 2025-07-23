# QEMU Live Migration TCP Proxy

This set of scripts facilitates the live migration of a QEMU virtual machine from a source host to a destination host over a network. It works by creating a TCP tunnel to proxy the migration data, which QEMU natively sends over a Unix domain socket.

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
┌───────────────────┐         TCP Tunnel          ┌────────────────────┐
│ tcp-client.py     ├<═══════════════════════════>│ tcp-server.py      │
│ (Unix-to-TCP)     │                             │ (TCP-to-Unix)      │
└───────────────────┘                             └────────────────────┘
         ▲                                                 ▲
         │ 2. Start Migration                            │ 3. Prepare for Migration
         │                                                 │
┌───────────────────┐                           ┌────────────────────┐
│ unix-send-tcp.py  │                           │ unix-receive-tcp.py│
│ (QMP Client)      │                           │ (QMP Client)       │
└───────────────────┘                           └────────────────────┘
```

## File Descriptions

*   **`tcp-migration-server.py` (Destination Host):** This script runs on the destination machine. It starts a TCP server that listens for a connection from the `tcp-migration-client.py`. Once a client connects, it waits for the destination QEMU to create a migration Unix socket (triggered by `unix-receive-tcp.py`) and then forwards all data from the TCP connection to this Unix socket.

*   **`tcp-migration-client.py` (Source Host):** This script runs on the source machine. It connects to the `tcp-migration-server.py` on the destination host. After establishing a connection, it creates a local Unix socket that the source QEMU will use as its migration target. It forwards all data from the local Unix socket to the TCP connection.

*   **`unix-receive-tcp.py` (Destination Host):** This is a QMP (QEMU Machine Protocol) client script. It connects to the destination QEMU instance and issues the `migrate-incoming` command. This tells the destination QEMU to start listening for migration data on a specified Unix socket.

*   **`unix-send-tcp.py` (Source Host):** This is a QMP client script. It connects to the source QEMU instance and issues the `migrate` command, pointing to the Unix socket created by `tcp-migration-client.py`. This initiates the migration process.

## Pre-run Configuration

Before running the scripts, you **must** update the configuration variables within the files to match your environment.

#### 1. In `tcp-migration-client.py` (on the Source Host):
   - **`server_host`**: Change this to the IP address of your **destination host**. This is the most critical change.
     ```python
     # filepath: /Users/sandesh.patel/dev/crypto/migrate/migrate-proxy/tcp-migration-client.py
     # ...existing code...
     async def main():
         # Configuration
         server_host = '192.168.1.100'  # <-- CHANGE THIS to your destination host's IP
         server_port = 9999
     # ...existing code...
     ```

#### 2. In `unix-send-tcp.py` (on the Source Host):
   - **`qmp_socket`**: Ensure this path points to your source VM's QMP socket.
     ```python
     # filepath: /Users/sandesh.patel/dev/crypto/migrate/migrate-proxy/unix-send-tcp.py
     # ...existing code...
     async def main():
         # Default QMP socket path - adjust as needed
         qmp_socket = "/var/run/qemu-server/vm-source.qmp" # <-- VERIFY OR CHANGE THIS
     # ...existing code...
     ```

#### 3. In `unix-receive-tcp.py` (on the Destination Host):
   - **`qmp_socket`**: Ensure this path points to your destination VM's QMP socket.
     ```python
     # filepath: /Users/sandesh.patel/dev/crypto/migrate/migrate-proxy/unix-receive-tcp.py
     # ...existing code...
     async def main():
         # Default QMP socket path for destination VM - adjust as needed
         qmp_socket = "/var/run/qemu-server/vm-dest.qmp" # <-- VERIFY OR CHANGE THIS
     # ...existing code...
     ```

**Note:** The Unix socket paths (`/tmp/qemu_migration_source.sock` and `/tmp/qemu_migration_dest.sock`) and the TCP port (`9999`) are configured to match across the scripts by default. You only need to change them if you have a specific reason to do so, ensuring they remain consistent between the client/server and sender/receiver pairs.

## How to Run

The scripts must be executed in a specific order. You will need two terminals on the source host and two on the destination host.

#### Step 1: On the **Destination Host** (Terminal 1)
Start the TCP proxy server. It will wait for a client to connect.
```bash
python tcp-migration-server.py
```

#### Step 2: On the **Source Host** (Terminal 1)
Start the TCP proxy client. It will connect to the server.
```bash
python tcp-migration-client.py
```
After this step, the TCP tunnel is established. The client will create a local Unix socket and wait for the source QEMU to connect.

#### Step 3: On the **Destination Host** (Terminal 2)
Prepare the destination QEMU to receive the migration.
```bash
python unix-receive-tcp.py
```
This script will command QEMU to listen on the Unix socket. The `tcp-migration-server.py` will detect this and complete its connection, ready to forward data.

#### Step 4: On the **Source Host** (Terminal 2)
Start the migration.
```bash
python unix-send-tcp.py
```
This script commands the source QEMU to begin migrating to the Unix socket managed by the `tcp-migration-client.py`. The migration data will now flow across the network.

You can monitor the progress in all four terminals.
