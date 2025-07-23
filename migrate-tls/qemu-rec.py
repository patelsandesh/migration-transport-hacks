import asyncio
import socket
from qemu.qmp import QMPClient
import json
import ssl
import os
MIGRATE_URI = "tcp:0:4444"
SERVER_PORT = 4444

# upgrade a tcp socket.socket object to tls and enable ktls
async def upgrade_to_tls(socket):
    try:
        # Upgrade the socket to TLS
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        # ssl context set option SSL_OP_ENABLE_KTLS
        context.options |= ssl.OP_ENABLE_KTLS  # Enable KTLS support
        # load the certificate and key files
        context.load_cert_chain("/etc/pki/qemu/server-cert.pem", "/etc/pki/qemu/server-key.pem")
        print("Loaded default certificates for TLS context")
        # Wrap the socket with SSL
        socket = context.wrap_socket(socket)
        print(f"Upgraded socket to TLS with KTLS enabled")
        # ssl wrap socket with 
        return socket  # Return the upgraded socket
    except Exception as e:
        print(f"Error upgrading socket to TLS: {e}")
        return None

# create a tcp sever to listen on the port 4444
async def server(host="0", port=SERVER_PORT):
    # Create a TCP socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.set_inheritable(True)
    
    try:
        # Bind the socket to address and port
        server_socket.bind((host, port))
        
        # Start listening (max 1 pending connections)
        server_socket.listen(1)
        print(f"Server listening on {host}:{port}")
        # Upgrade the client socket to TLS
        server_socket = await upgrade_to_tls(server_socket)
        client_socket, client_address = server_socket.accept()
        print(f"Accepted connection from {client_address}, socketfd {client_socket}")
        return client_socket
    except Exception as e:
        print(f"Error creating server socket: {e}")
        print("Closing server socket")
        server_socket.close()
        return None
        

# functtion to add fd to qemu using qmp command
async def qemu_add_fd(qemp, socketfd):
    res = {}
    # socketfd = socket.fileno()
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

async def migrate_incoming_tcp(qemp, uri):
    margs =  {"uri": uri}
    print(f"Executing migrate with payload: {margs}")
    try:
        res = await qemp.execute("migrate-incoming", margs)
        print(res)
    except Exception as e:
        print(f"Error during migration: {e}")
        await qemp.disconnect()

# receive the migration using socket fd
# and execute the migrate-incoming command with payload
async def migrate_incoming_fd(qemp, socket_fd):
    margs = {"uri": f"fd:{socket_fd}"}
    print(f"Executing migrate-incoming with payload: {margs}")
    try:
        res = await qemp.execute("migrate-incoming", margs)
        print(res)
    except Exception as e:
        print(f"Error during migration: {e}")
        await qemp.disconnect()


async def main(fd):
    qemp = QMPClient("test-vm")
    await qemp.connect('/tmp/qemu-monitor.sock')
    try:
        res = await qemp.execute('query-status')
        print(res)
    except Exception as e:
        print(f"Error executing query-status: {e}")
        await qemp.disconnect()
    
    if fd is None:
        socket = await server("0", SERVER_PORT)
        if not socket:
            print("Failed to create server socket.")
        else:
            socket = socket.fileno()
    else:
        socket = fd
        print(f"Using provided file descriptor: {socket}")

    fdset = await qemu_add_fd(qemp, socket)
    await migrate_incoming_fd(qemp, fdset)

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