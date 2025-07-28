import socket
import ssl
import time
import logging
import os
import threading
import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TCPSender:
    def __init__(self, server_host, server_port, cert_dir='../../migrate-websocket/certs'):
        self.server_host = server_host
        self.server_port = server_port
        self.cert_dir = cert_dir
        self.chunk_size = 8192
        self.test_data = b'x' * self.chunk_size  # 8KB of data
        
    def create_ssl_context(self):
        """Create SSL context for secure TCP connection."""
        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        
        # Load client certificate and key
        cert_file = os.path.join(self.cert_dir, 'client-cert.pem')
        key_file = os.path.join(self.cert_dir, 'client-key.pem')
        ca_file = os.path.join(self.cert_dir, 'ca.pem')
        
        if not all(os.path.exists(f) for f in [cert_file, key_file, ca_file]):
            raise FileNotFoundError(f"Certificate files not found in {self.cert_dir}")
        
        # Load client certificate for authentication
        ssl_context.load_cert_chain(cert_file, key_file)
        ssl_context.load_verify_locations(ca_file)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        
        return ssl_context
    
    def create_unix_socket_server(self, socket_path):
        """Create Unix domain socket server to receive data."""
        # Remove existing socket file if it exists
        if os.path.exists(socket_path):
            os.unlink(socket_path)
        
        unix_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        unix_sock.bind(socket_path)
        unix_sock.listen(1)
        logger.info(f"Unix domain socket server listening on {socket_path}")
        return unix_sock
        
    def benchmark_send_unix(self, duration_seconds=30, unix_socket_path='/tmp/tcp_sender.sock', target_mbps=None):
        """Send data from Unix domain socket and benchmark bandwidth."""
        ssl_context = self.create_ssl_context()
        
        # Create Unix domain socket server
        unix_server = self.create_unix_socket_server(unix_socket_path)
        
        try:
            # Create TCP socket and wrap with SSL
            tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ssl_sock = ssl_context.wrap_socket(tcp_sock, server_hostname=self.server_host)
            
            # Connect to TCP server
            ssl_sock.connect((self.server_host, self.server_port))
            logger.info(f"Connected to TCP server {self.server_host}:{self.server_port}")
            logger.info(f"Waiting for Unix socket connection on {unix_socket_path}")
            logger.info(f"Starting bandwidth test for {duration_seconds} seconds")
            
            if target_mbps:
                logger.info(f"Target bandwidth: {target_mbps} MBps")
            
            # Wait for Unix socket connection
            unix_client, _ = unix_server.accept()
            logger.info("Unix socket client connected")
            
            start_time = time.time()
            bytes_sent = 0
            chunks_sent = 0
            last_report_time = start_time
            last_report_bytes = 0
            
            # Calculate delay between sends if target bandwidth is specified
            send_delay = 0
            if target_mbps:
                target_bps = target_mbps * 1024 * 1024
                send_delay = self.chunk_size / target_bps
            
            # Set sockets to non-blocking for select
            unix_client.setblocking(False)
            
            while time.time() - start_time < duration_seconds:
                try:
                    # Use select to check if data is available
                    ready, _, _ = select.select([unix_client], [], [], 0.1)
                    
                    if ready:
                        # Read data from Unix socket
                        data = unix_client.recv(self.chunk_size)
                        if not data:
                            logger.warning("Unix socket client disconnected")
                            break
                        
                        # Send data to TCP server
                        ssl_sock.sendall(data)
                        bytes_sent += len(data)
                        chunks_sent += 1
                        
                        # Apply rate limiting if target bandwidth is set
                        if send_delay > 0:
                            time.sleep(send_delay)
                    
                    # Report progress every second
                    current_time = time.time()
                    if current_time - last_report_time >= 1.0:
                        elapsed = current_time - start_time
                        interval_bytes = bytes_sent - last_report_bytes
                        interval_mbps = interval_bytes / (1024 * 1024)
                        total_mbps = bytes_sent / (elapsed * 1024 * 1024) if elapsed > 0 else 0
                        
                        logger.info(f"Time: {elapsed:.1f}s | "
                                  f"Sent: {bytes_sent / (1024*1024):.1f} MB | "
                                  f"Chunks: {chunks_sent} | "
                                  f"Interval: {interval_mbps:.2f} MBps | "
                                  f"Avg: {total_mbps:.2f} MBps")
                        
                        last_report_time = current_time
                        last_report_bytes = bytes_sent
                        
                except socket.error:
                    # No data available, continue
                    pass
            
            # Final statistics
            total_time = time.time() - start_time
            total_mb = bytes_sent / (1024 * 1024)
            avg_mbps = bytes_sent / (total_time * 1024 * 1024) if total_time > 0 else 0
            
            logger.info("=" * 60)
            logger.info("FINAL RESULTS:")
            logger.info(f"Duration: {total_time:.2f} seconds")
            logger.info(f"Data sent: {total_mb:.2f} MB")
            logger.info(f"Chunks sent: {chunks_sent}")
            logger.info(f"Average bandwidth: {avg_mbps:.2f} MBps")
            logger.info(f"Average throughput: {total_mb/total_time:.2f} MB/s" if total_time > 0 else "N/A")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Error during benchmark: {e}")
        finally:
            try:
                unix_client.close()
                unix_server.close()
                os.unlink(unix_socket_path)
                ssl_sock.close()
            except:
                pass
        
    def benchmark_send(self, duration_seconds=30, target_mbps=None):
        """Send data continuously and benchmark bandwidth."""
        ssl_context = self.create_ssl_context()
        
        try:
            # Create socket and wrap with SSL
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ssl_sock = ssl_context.wrap_socket(sock, server_hostname=self.server_host)
            
            # Connect to server
            ssl_sock.connect((self.server_host, self.server_port))
            logger.info(f"Connected to {self.server_host}:{self.server_port}")
            logger.info(f"Starting bandwidth test for {duration_seconds} seconds")
            logger.info(f"Chunk size: {self.chunk_size} bytes")
            
            if target_mbps:
                logger.info(f"Target bandwidth: {target_mbps} MBps")
            
            start_time = time.time()
            bytes_sent = 0
            chunks_sent = 0
            last_report_time = start_time
            last_report_bytes = 0
            
            # Calculate delay between sends if target bandwidth is specified
            send_delay = 0
            if target_mbps:
                # Convert MBps to bytes per second
                target_bps = target_mbps * 1024 * 1024
                # Calculate delay needed between chunks
                send_delay = self.chunk_size / target_bps
            
            while time.time() - start_time < duration_seconds:
                # Send data chunk
                ssl_sock.sendall(self.test_data)
                bytes_sent += self.chunk_size
                chunks_sent += 1
                
                # Apply rate limiting if target bandwidth is set
                if send_delay > 0:
                    time.sleep(send_delay)
                
                # Report progress every second
                current_time = time.time()
                if current_time - last_report_time >= 1.0:
                    elapsed = current_time - start_time
                    interval_bytes = bytes_sent - last_report_bytes
                    interval_mbps = interval_bytes / (1024 * 1024)  # Convert to MBps
                    total_mbps = bytes_sent / (elapsed * 1024 * 1024)
                    
                    logger.info(f"Time: {elapsed:.1f}s | "
                              f"Sent: {bytes_sent / (1024*1024):.1f} MB | "
                              f"Chunks: {chunks_sent} | "
                              f"Interval: {interval_mbps:.2f} MBps | "
                              f"Avg: {total_mbps:.2f} MBps")
                    
                    last_report_time = current_time
                    last_report_bytes = bytes_sent
            
            # Final statistics
            total_time = time.time() - start_time
            total_mb = bytes_sent / (1024 * 1024)
            avg_mbps = bytes_sent / (total_time * 1024 * 1024)
            
            logger.info("=" * 60)
            logger.info("FINAL RESULTS:")
            logger.info(f"Duration: {total_time:.2f} seconds")
            logger.info(f"Data sent: {total_mb:.2f} MB")
            logger.info(f"Chunks sent: {chunks_sent}")
            logger.info(f"Average bandwidth: {avg_mbps:.2f} MBps")
            logger.info(f"Average throughput: {total_mb/total_time:.2f} MB/s")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Error during benchmark: {e}")
        finally:
            try:
                ssl_sock.close()
            except:
                pass

def main():
    server_host = '10.117.30.218'
    server_port = 8765
    sender = TCPSender(server_host, server_port)
    
    print("TCP Bandwidth Test - Sender")
    print("Options:")
    print("1. Unlimited bandwidth test (30 seconds)")
    print("2. Rate-limited bandwidth test")
    print("3. Custom duration test")
    print("4. Unix socket input test (unlimited)")
    print("5. Unix socket input test (rate-limited)")
    
    choice = input("Enter choice (1-5): ").strip()
    
    if choice == '1':
        sender.benchmark_send(duration_seconds=30)
    elif choice == '2':
        target_mbps = float(input("Enter target bandwidth (MBps): "))
        duration = int(input("Enter duration (seconds, default 30): ") or "30")
        sender.benchmark_send(duration_seconds=duration, target_mbps=target_mbps)
    elif choice == '3':
        duration = int(input("Enter duration (seconds): "))
        sender.benchmark_send(duration_seconds=duration)
    elif choice == '4':
        duration = int(input("Enter duration (seconds, default 30): ") or "30")
        socket_path = input("Unix socket path (default: /tmp/tcp_sender.sock): ").strip() or "/tmp/tcp_sender.sock"
        sender.benchmark_send_unix(duration_seconds=duration, unix_socket_path=socket_path)
    elif choice == '5':
        target_mbps = float(input("Enter target bandwidth (MBps): "))
        duration = int(input("Enter duration (seconds, default 30): ") or "30")
        socket_path = input("Unix socket path (default: /tmp/tcp_sender.sock): ").strip() or "/tmp/tcp_sender.sock"
        sender.benchmark_send_unix(duration_seconds=duration, unix_socket_path=socket_path, target_mbps=target_mbps)
    else:
        print("Invalid choice, running default test")
        sender.benchmark_send(duration_seconds=30)

if __name__ == "__main__":
    main()