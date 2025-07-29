import socket
import time

def start_client(server_ip='10.117.30.218', server_port=8899):
    # Wait a bit to ensure S2 is listening
    print("C2: Waiting for S2 to start listening...")
    time.sleep(5)
    
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        print(f"C2: Connecting to server at {server_ip}:{server_port}")
        client_socket.connect((server_ip, server_port))
        print("C2: Connected to S2")
        
        # Send data periodically
        counter = 1
        while True:
            message = f"C2 message {counter}"
            print(f"C2: Sending: {message}")
            client_socket.sendall(message.encode())
            
            # Receive response
            response = client_socket.recv(1024)
            print(f"C2: Received: {response.decode()}")
            
            counter += 1
            time.sleep(4)  # Send data every 4 seconds
            
    except KeyboardInterrupt:
        print("C2: Client shutting down")
    except Exception as e:
        print(f"C2: Error: {e}")
    finally:
        client_socket.close()
        print("C2: Connection closed")

if __name__ == "__main__":
    start_client()