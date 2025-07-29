import socket
import time

def start_client(server_ip='10.117.30.218', server_port=8899):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        print(f"C1: Connecting to server at {server_ip}:{server_port}")
        client_socket.connect((server_ip, server_port))
        print("C1: Connected to S1")
        
        # Send data periodically
        counter = 1
        while True:
            message = f"C1 message {counter}"
            print(f"C1: Sending: {message}")
            client_socket.sendall(message.encode())
            
            # Receive response
            response = client_socket.recv(1024)
            print(f"C1: Received: {response.decode()}")
            
            counter += 1
            time.sleep(3)  # Send data every 3 seconds
            
    except KeyboardInterrupt:
        print("C1: Client shutting down")
    except Exception as e:
        print(f"C1: Error: {e}")
    finally:
        client_socket.close()
        print("C1: Connection closed")

if __name__ == "__main__":
    start_client()