import socket
import time
import threading

def handle_client(conn, addr):
    """Handle client connection in a separate thread"""
    print(f"S2: Handling client {addr} in separate thread")
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            print(f"S2: Received from client: {data.decode()}")
            response = f"S2 Echo: {data.decode()}"
            conn.sendall(response.encode())
    except Exception as e:
        print(f"S2: Error handling client {addr}: {e}")
    finally:
        conn.close()
        print(f"S2: Connection with {addr} closed.")

def start_server(ip='10.117.30.218', port=8899):
    # Wait a bit to ensure S1 has closed its listening socket
    print("S2: Waiting for S1 to release the port...")
    time.sleep(2)
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((ip, port))
        server_socket.listen(1)
        print(f"S2: Server listening on {ip}:{port} (reusing the port)")
        
        # Accept one connection from C2
        conn, addr = server_socket.accept()
        print(f"S2: Connection established with {addr}")
        
        # Handle the client in a separate thread
        client_thread = threading.Thread(target=handle_client, args=(conn, addr))
        client_thread.daemon = True
        client_thread.start()
        
        print("S2: Handling client connection...")
        try:
            client_thread.join()  # Wait for client thread to finish
        except KeyboardInterrupt:
            print("S2: Server shutting down")
            conn.close()
            
    except Exception as e:
        print(f"S2: Error binding to port {port}: {e}")
    finally:
        server_socket.close()

if __name__ == "__main__":
    start_server()