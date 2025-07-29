import socket
import time
import threading

def handle_client(conn, addr):
    """Handle client connection in a separate thread"""
    print(f"S1: Handling client {addr} in separate thread")
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            print(f"S1: Received from client: {data.decode()}")
            response = f"S1 Echo: {data.decode()}"
            conn.sendall(response.encode())
    except Exception as e:
        print(f"S1: Error handling client {addr}: {e}")
    finally:
        conn.close()
        print(f"S1: Connection with {addr} closed.")

def start_server(ip='10.117.30.218', port=8899):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((ip, port))
    server_socket.listen(1)
    print(f"S1: Server listening on {ip}:{port}")

    # Accept one connection
    conn, addr = server_socket.accept()
    print(f"S1: Connection established with {addr}")
    
    # Close the server socket immediately after accepting
    print("S1: Closing server socket while keeping client connection active")
    server_socket.close()
    
    # Start handling the client in a separate thread
    client_thread = threading.Thread(target=handle_client, args=(conn, addr))
    client_thread.daemon = True
    client_thread.start()
    
    # Keep the main thread alive to maintain the connection
    print("S1: Server socket closed, but client connection remains active")
    try:
        client_thread.join()  # Wait for client thread to finish
    except KeyboardInterrupt:
        print("S1: Server shutting down")
        conn.close()

if __name__ == "__main__":
    start_server()