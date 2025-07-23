import asyncio
from qemu.qmp import QMPClient
import json
import socket
import ssl
import os

MIGRATE_URI = "tcp:10.117.28.118:4444"
DESTINATION_IP = "10.117.28.118"
DESTION_PORT = 4444
DESTINATION_HOST = "nested-ahv"


# upgrade a tcp socket.socket object to tls and enable ktls
async def upgrade_to_tls(socket):
    try:
        # Upgrade the socket to TLS
        context = ssl.create_default_context()
        context.check_hostname = False  # Disable hostname checking for simplicity
        # ssl context set option SSL_OP_ENABLE_KTLS
        context.options |= ssl.OP_ENABLE_KTLS  # Enable KTLS support
        context.verify_mode = ssl.CERT_NONE  # Disable certificate verification for simplicity
        # Wrap the socket with SSL
        socket = context.wrap_socket(socket, server_hostname=DESTINATION_HOST)
        print(f"Upgraded socket to TLS with KTLS enabled")
        # ssl wrap socket with 
        return socket  # Return the upgraded socket
    except Exception as e:
        print(f"Error upgrading socket to TLS: {e}")
        return None

# create a tcp client to connect to the destination and return the socket
async def create_tcp_client(host=DESTINATION_IP, port=DESTION_PORT):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.set_inheritable(True)
    client_socket = await upgrade_to_tls(client_socket)
    if not client_socket:
        print("Failed to upgrade socket to TLS, exiting.")
        return
    try:
        client_socket.connect((host, port))
        print(f"Connected to {host}:{port}")
        return client_socket
    except Exception as e:
        print(f"Error connecting to {host}:{port}: {e}")
        return None

# run the qmp migrate command with payload-
# {
#   "execute": "migrate",
#   "arguments": { "uri": "tcp:192.168.1.2:4446" }
# }
async def migrate_tcp(qemp, uri):
    margs =  {"uri": uri}
    print(f"Executing migrate with payload: {margs}")
    try:
        res = await qemp.execute("migrate", margs)
        print(res)
    except Exception as e:
        print(f"Error during migration: {e}")
        await qemp.disconnect()

# migrate using socket fd
async def migrate_fd(qemp, socket_fd):
    margs = {"uri": f"fd:{socket_fd}"}
    print(f"Executing migrate with payload: {margs}")
    try:
        res = await qemp.execute("migrate", margs)
        print(res)
    except Exception as e:
        print(f"Error during migration: {e}")
        await qemp.disconnect()

# functtion to add fd to qemu using qmp command
async def qemu_add_fd(qemp, socketfd):
    res = {}
    print(f"Socket file descriptor: {socketfd}")
    # Register the socket with QMP
    qemp.send_fd_scm(socketfd)
    # add fd to qmp using add-fd command
    getfd_args = {"fdname": "migfd"}
    print(f"getfd with payyload {getfd_args}")
    try:
        res = await qemp.execute("getfd", getfd_args)
        print(res)
    except Exception as e:
        print(f"Error getting fd: {e}")
        await qemp.disconnect()
    print(f"Got fd with response: {res}")

    return "migfd"

async def main(fd = None):
    qemp = QMPClient("test-vm")
    await qemp.connect('/tmp/qemu-monitor.sock')
    try:
        res = await qemp.execute('query-status')
        print(res)
    except Exception as e:
        print(f"Error executing query-status: {e}")
        await qemp.disconnect()

    if fd is None:
        client_socket = await create_tcp_client(DESTINATION_IP, DESTION_PORT)
        if not client_socket:
            print("Failed to create TCP client, exiting.")
            return
        else:
            client_socket = client_socket.fileno()
    else:
        client_socket = fd
        print(f"Using provided file descriptor: {client_socket}")

    fdset = await qemu_add_fd(qemp, client_socket)
    # Now perform the migration
    print("Starting migration...")
    # The migrate command will use the socket registered above 
    await migrate_fd(qemp, fdset)

    await qemp.disconnect()


def receive_fd():
    # Create Unix domain socket
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    
    # Bind to socket file
    socket_path = "/tmp/fd_socket"
    if os.path.exists(socket_path):
        os.unlink(socket_path)
    sock.bind(socket_path)
    sock.listen(1)
    
    print("Waiting for connection...")
    conn, addr = sock.accept()
    
    try:
        # Receive message with ancillary data
        data, ancdata, msg_flags, address = conn.recvmsg(1024, socket.CMSG_LEN(4))
        
        # Extract file descriptor from ancillary data
        for cmsg_level, cmsg_type, cmsg_data in ancdata:
            if cmsg_level == socket.SOL_SOCKET and cmsg_type == socket.SCM_RIGHTS:
                # Unpack the file descriptor
                import struct
                fd = struct.unpack("i", cmsg_data)[0]
                print(f"Received file descriptor: {fd}")
                
                return fd
    
    except Exception as e:
        print(f"Error receiving fd: {e}")
    finally:
        conn.close()
        sock.close()
        os.unlink(socket_path)



if __name__ == "__main__":
    fd = receive_fd()
    if fd is not None:
        print(f"Received file descriptor: {fd}")
    else:
        print("Failed to receive file descriptor.")
    asyncio.run(main(fd))