import socket
import time
import logging
import os
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UnixSender:
    def __init__(self, socket_path='/tmp/tcp_sender.sock'):
        self.socket_path = socket_path
        self.chunk_size = 8192
        self.test_data = b'x' * self.chunk_size  # 8KB of test data
        
    def send_data(self, duration_seconds=40):
        """Send data continuously for specified duration."""
        try:
            # Create Unix domain socket
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            
            # Connect to receiver
            logger.info(f"Connecting to Unix socket: {self.socket_path}")
            sock.connect(self.socket_path)
            logger.info("Connected to receiver")
            
            logger.info(f"Starting data transmission for {duration_seconds} seconds")
            logger.info(f"Chunk size: {self.chunk_size} bytes")
            
            start_time = time.time()
            bytes_sent = 0
            chunks_sent = 0
            last_report_time = start_time
            last_report_bytes = 0
            
            while time.time() - start_time < duration_seconds:
                # Send data chunk
                sock.sendall(self.test_data)
                bytes_sent += self.chunk_size
                chunks_sent += 1
                
                # Report progress every second
                current_time = time.time()
                if current_time - last_report_time >= 1.0:
                    elapsed = current_time - start_time
                    interval_bytes = bytes_sent - last_report_bytes
                    interval_mbps = interval_bytes / (1024 * 1024)
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
            logger.info("SENDER FINAL RESULTS:")
            logger.info(f"Duration: {total_time:.2f} seconds")
            logger.info(f"Data sent: {total_mb:.2f} MB")
            logger.info(f"Chunks sent: {chunks_sent}")
            logger.info(f"Average bandwidth: {avg_mbps:.2f} MBps")
            logger.info(f"Average throughput: {total_mb/total_time:.2f} MB/s")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Error during transmission: {e}")
        finally:
            try:
                sock.close()
            except:
                pass

def main():
    socket_path = input("Unix socket path (default:/tmp/tcp_sender.sock): ").strip() or "/tmp/tcp_sender.sock"
    duration = int(input("Duration in seconds (default: 40): ") or "40")
    
    sender = UnixSender(socket_path)
    sender.send_data(duration_seconds=duration)

if __name__ == "__main__":
    main()