import socket
import ssl
import time
import logging
import os
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TCPReceiver:
    def __init__(self, host='0.0.0.0', port=8765, cert_dir='../../migrate-websocket/certs'):
        self.host = host
        self.port = port
        self.cert_dir = cert_dir
        self.buffer_size = 8192
        
    def create_ssl_context(self):
        """Create SSL context for secure TCP server."""
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        
        # Load server certificate and key
        cert_file = os.path.join(self.cert_dir, 'server-cert.pem')
        key_file = os.path.join(self.cert_dir, 'server-key.pem')
        ca_file = os.path.join(self.cert_dir, 'ca.pem')
        
        if not all(os.path.exists(f) for f in [cert_file, key_file, ca_file]):
            raise FileNotFoundError(f"Certificate files not found in {self.cert_dir}")
        
        ssl_context.load_cert_chain(cert_file, key_file)
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        ssl_context.load_verify_locations(ca_file)
        
        return ssl_context
    
    def create_unix_socket_client(self, socket_path):
        """Create Unix domain socket client to send data."""
        unix_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            unix_sock.connect(socket_path)
            logger.info(f"Connected to Unix domain socket {socket_path}")
            return unix_sock
        except Exception as e:
            logger.error(f"Failed to connect to Unix socket {socket_path}: {e}")
            unix_sock.close()
            return None
        
    def handle_client_unix(self, ssl_sock, client_addr, unix_socket_path):
        """Handle incoming TCP connection and forward data to Unix socket."""
        logger.info(f"Client connected from {client_addr}")
        
        # Connect to Unix socket
        unix_sock = self.create_unix_socket_client(unix_socket_path)
        if not unix_sock:
            logger.error(f"Cannot forward data for client {client_addr} - Unix socket connection failed")
            ssl_sock.close()
            return
        
        try:
            start_time = time.time()
            bytes_received = 0
            chunks_received = 0
            last_report_time = start_time
            last_report_bytes = 0
            
            while True:
                try:
                    data = ssl_sock.recv(self.buffer_size)
                    if not data:
                        break
                    
                    # Forward data to Unix socket
                    unix_sock.sendall(data)
                    
                    bytes_received += len(data)
                    chunks_received += 1
                    
                    # Report progress every second
                    current_time = time.time()
                    if current_time - last_report_time >= 1.0:
                        elapsed = current_time - start_time
                        interval_bytes = bytes_received - last_report_bytes
                        interval_mbps = interval_bytes / (1024 * 1024)  # Convert to MBps
                        total_mbps = bytes_received / (elapsed * 1024 * 1024)
                        
                        logger.info(f"Time: {elapsed:.1f}s | "
                                  f"Received: {bytes_received / (1024*1024):.1f} MB | "
                                  f"Chunks: {chunks_received} | "
                                  f"Interval: {interval_mbps:.2f} MBps | "
                                  f"Avg: {total_mbps:.2f} MBps | "
                                  f"Forwarded to Unix socket")
                        
                        last_report_time = current_time
                        last_report_bytes = bytes_received
                        
                except ssl.SSLWantReadError:
                    continue
                except (ConnectionResetError, ssl.SSLError) as e:
                    logger.info(f"Client {client_addr} disconnected: {e}")
                    break
                except Exception as e:
                    logger.error(f"Error forwarding data to Unix socket: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Error handling client {client_addr}: {e}")
        finally:
            # Final statistics
            if bytes_received > 0:
                total_time = time.time() - start_time
                total_mb = bytes_received / (1024 * 1024)
                avg_mbps = bytes_received / (total_time * 1024 * 1024)
                
                logger.info("=" * 60)
                logger.info(f"CLIENT {client_addr} DISCONNECTED - FINAL RESULTS:")
                logger.info(f"Duration: {total_time:.2f} seconds")
                logger.info(f"Data received: {total_mb:.2f} MB")
                logger.info(f"Chunks received: {chunks_received}")
                logger.info(f"Average bandwidth: {avg_mbps:.2f} MBps")
                logger.info(f"Average throughput: {total_mb/total_time:.2f} MB/s")
                logger.info("=" * 60)
            
            logger.info(f"Client {client_addr} disconnected")
            unix_sock.close()
            ssl_sock.close()
        
    def handle_client(self, ssl_sock, client_addr):
        """Handle incoming TCP connection and measure receive bandwidth."""
        logger.info(f"Client connected from {client_addr}")
        
        try:
            start_time = time.time()
            bytes_received = 0
            chunks_received = 0
            last_report_time = start_time
            last_report_bytes = 0
            
            while True:
                try:
                    data = ssl_sock.recv(self.buffer_size)
                    if not data:
                        break
                        
                    bytes_received += len(data)
                    chunks_received += 1
                    
                    # Report progress every second
                    current_time = time.time()
                    if current_time - last_report_time >= 1.0:
                        elapsed = current_time - start_time
                        interval_bytes = bytes_received - last_report_bytes
                        interval_mbps = interval_bytes / (1024 * 1024)  # Convert to MBps
                        total_mbps = bytes_received / (elapsed * 1024 * 1024)
                        
                        logger.info(f"Time: {elapsed:.1f}s | "
                                  f"Received: {bytes_received / (1024*1024):.1f} MB | "
                                  f"Chunks: {chunks_received} | "
                                  f"Interval: {interval_mbps:.2f} MBps | "
                                  f"Avg: {total_mbps:.2f} MBps")
                        
                        last_report_time = current_time
                        last_report_bytes = bytes_received
                        
                except ssl.SSLWantReadError:
                    continue
                except (ConnectionResetError, ssl.SSLError) as e:
                    logger.info(f"Client {client_addr} disconnected: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Error handling client {client_addr}: {e}")
        finally:
            # Final statistics
            if bytes_received > 0:
                total_time = time.time() - start_time
                total_mb = bytes_received / (1024 * 1024)
                avg_mbps = bytes_received / (total_time * 1024 * 1024)
                
                logger.info("=" * 60)
                logger.info(f"CLIENT {client_addr} DISCONNECTED - FINAL RESULTS:")
                logger.info(f"Duration: {total_time:.2f} seconds")
                logger.info(f"Data received: {total_mb:.2f} MB")
                logger.info(f"Chunks received: {chunks_received}")
                logger.info(f"Average bandwidth: {avg_mbps:.2f} MBps")
                logger.info(f"Average throughput: {total_mb/total_time:.2f} MB/s")
                logger.info("=" * 60)
            
            logger.info(f"Client {client_addr} disconnected")
            ssl_sock.close()
        
    def start_server(self, unix_socket_path=None):
        """Start the TCP server."""
        ssl_context = self.create_ssl_context()
        
        # Create server socket
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.port))
        server_sock.listen(5)
        
        logger.info(f"TCP bandwidth test server listening on {self.host}:{self.port}")
        if unix_socket_path:
            logger.info(f"Data will be forwarded to Unix socket: {unix_socket_path}")
        logger.info("Waiting for client connections...")
        logger.info("Server supports multiple concurrent connections")
        
        try:
            while True:
                client_sock, client_addr = server_sock.accept()
                
                # Wrap client socket with SSL
                ssl_sock = ssl_context.wrap_socket(client_sock, server_side=True)
                
                # Handle each client in a separate thread
                if unix_socket_path:
                    client_thread = threading.Thread(
                        target=self.handle_client_unix,
                        args=(ssl_sock, client_addr, unix_socket_path),
                        daemon=True
                    )
                else:
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(ssl_sock, client_addr),
                        daemon=True
                    )
                client_thread.start()
                
        except KeyboardInterrupt:
            logger.info("Shutting down server...")
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            server_sock.close()

def main():
    receiver = TCPReceiver()
    
    print("TCP Bandwidth Test - Receiver")
    print("Options:")
    print("1. Standard receive mode (measure only)")
    print("2. Unix socket output mode (forward data)")
    
    choice = input("Enter choice (1-2): ").strip()
    
    unix_socket_path = None
    if choice == '2':
        unix_socket_path = input("Unix socket path (default: /tmp/tcp_receiver.sock): ").strip() or "/tmp/tcp_receiver.sock"
    
    try:
        receiver.start_server(unix_socket_path=unix_socket_path)
    except KeyboardInterrupt:
        logger.info("Server shutdown complete")
    except Exception as e:
        logger.error(f"Server error: {e}")

if __name__ == "__main__":
    print("TCP Bandwidth Test - Receiver")
    print("Starting server...")
    main()