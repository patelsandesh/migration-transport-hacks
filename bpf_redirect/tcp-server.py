import socket
import sys
import threading
import errno
import time


def handle_client(client_socket, client_address):
    """Handle incoming client connections"""
    print(f"Connection from {client_address}")

    try:
        while True:
            try:
                # Receive data from client
                data = client_socket.recv(1024)
                if not data:
                    break

                # Echo the data back to client
                message = f"Server received: {data.decode('utf-8')}"
                print(f"Received from {client_address}: {data.decode('utf-8')}")
                client_socket.send(message.encode("utf-8"))

            except socket.error as e:
                if e.errno == errno.EAGAIN or e.errno == errno.EWOULDBLOCK:
                    # Resource temporarily unavailable, retry after short delay
                    time.sleep(0.001)
                    continue
                else:
                    raise

    except Exception as e:
        print(f"Error handling client {client_address}: {e}")
    finally:
        client_socket.close()
        print(f"Connection with {client_address} closed")


def main():
    if len(sys.argv) != 2:
        print("Usage: python tcp-server.py <port>")
        sys.exit(1)

    try:
        port = int(sys.argv[1])
    except ValueError:
        print("Error: Port must be a valid integer")
        sys.exit(1)

    # Create socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        # Bind to all interfaces (0.0.0.0) and specified port
        server_socket.bind(("0.0.0.0", port))
        server_socket.listen(5)

        print(f"TCP Server listening on 0.0.0.0:{port}")

        while True:
            # Accept incoming connections
            client_socket, client_address = server_socket.accept()

            # Handle each client in a separate thread
            client_thread = threading.Thread(
                target=handle_client, args=(client_socket, client_address)
            )
            client_thread.daemon = True
            client_thread.start()

    except KeyboardInterrupt:
        print("\nServer shutting down...")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()
