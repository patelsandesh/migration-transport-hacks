import socket
import time
import logging
import os
import signal
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UnixReceiver:
    def __init__(self, socket_path='/tmp/tcp_receiver.sock'):
        self.socket_path = socket_path
        self.chunk_size = 8192
        self.running = True
        
    def signal_handler(self, signum, frame):
        """Handle interrupt signal gracefully."""
        logger.info("Received interrupt signal, shutting down...")
        self.running = False
        
    def receive_data(self, duration_seconds=40):
        """Receive data continuously for specified duration."""
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Remove existing socket file if it exists
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        try:
            # Create Unix domain socket
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.bind(self.socket_path)
            sock.listen(1)
            
            logger.info(f"Unix domain socket server listening on {self.socket_path}")
            logger.info("Waiting for sender connection...")
            
            # Accept connection
            client_sock, _ = sock.accept()
            logger.info("Sender connected")
            
            logger.info(f"Starting data reception for {duration_seconds} seconds")
            logger.info(f"Expected chunk size: {self.chunk_size} bytes")
            
            start_time = time.time()
            bytes_received = 0
            chunks_received = 0
            last_report_time = start_time
            last_report_bytes = 0
            
            # Set socket timeout to avoid blocking indefinitely
            client_sock.settimeout(1.0)
            
            while self.running and (time.time() - start_time < duration_seconds):
                try:
                    # Receive data chunk
                    data = client_sock.recv(self.chunk_size)
                    if not data:
                        logger.warning("Sender disconnected")
                        break
                    
                    bytes_received += len(data)
                    chunks_received += 1
                    
                    # Report progress every second
                    current_time = time.time()
                    if current_time - last_report_time >= 1.0:
                        elapsed = current_time - start_time
                        interval_bytes = bytes_received - last_report_bytes
                        interval_mbps = interval_bytes / (1024 * 1024)
                        total_mbps = bytes_received / (elapsed * 1024 * 1024)
                        
                        logger.info(f"Time: {elapsed:.1f}s | "
                                  f"Received: {bytes_received / (1024*1024):.1f} MB | "
                                  f"Chunks: {chunks_received} | "
                                  f"Interval: {interval_mbps:.2f} MBps | "
                                  f"Avg: {total_mbps:.2f} MBps")
                        
                        last_report_time = current_time
                        last_report_bytes = bytes_received
                        
                except socket.timeout:
                    # Continue on timeout to check if we should stop
                    continue
                except Exception as e:
                    logger.error(f"Error receiving data: {e}")
                    break
            
            # Final statistics
            total_time = time.time() - start_time
            total_mb = bytes_received / (1024 * 1024)
            avg_mbps = bytes_received / (total_time * 1024 * 1024) if total_time > 0 else 0
            
            logger.info("=" * 60)
            logger.info("RECEIVER FINAL RESULTS:")
            logger.info(f"Duration: {total_time:.2f} seconds")
            logger.info(f"Data received: {total_mb:.2f} MB")
            logger.info(f"Chunks received: {chunks_received}")
            logger.info(f"Average bandwidth: {avg_mbps:.2f} MBps")
            logger.info(f"Average throughput: {total_mb/total_time:.2f} MB/s" if total_time > 0 else "N/A")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Error during reception: {e}")
        finally:
            try:
                client_sock.close()
                sock.close()
                if os.path.exists(self.socket_path):
                    os.unlink(self.socket_path)
            except:
                pass

def main():
    socket_path = input("Unix socket path (default: /tmp/tcp_receiver.sock): ").strip() or "/tmp/tcp_receiver.sock"
    duration = int(input("Duration in seconds (default: 40): ") or "40")
    
    receiver = UnixReceiver(socket_path)
    receiver.receive_data(duration_seconds=duration)

if __name__ == "__main__":
    main()