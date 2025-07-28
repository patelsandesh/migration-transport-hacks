import asyncio
import websockets
import ssl
import time
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebSocketSender:
    def __init__(self, server_url, cert_dir='../../migrate-websocket/certs'):
        self.server_url = server_url
        self.cert_dir = cert_dir
        self.chunk_size = 8192
        self.test_data = b'x' * self.chunk_size  # 8KB of data
        
    def create_ssl_context(self):
        """Create SSL context for secure WebSocket connection."""
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
        
    async def benchmark_send(self, duration_seconds=30, target_mbps=None):
        """Send data continuously and benchmark bandwidth."""
        ssl_context = self.create_ssl_context()
        
        try:
            async with websockets.connect(self.server_url, ssl=ssl_context) as websocket:
                logger.info(f"Connected to {self.server_url}")
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
                    await websocket.send(self.test_data)
                    bytes_sent += self.chunk_size
                    chunks_sent += 1
                    
                    # Apply rate limiting if target bandwidth is set
                    if send_delay > 0:
                        await asyncio.sleep(send_delay)
                    
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

async def main():
    server_url = 'wss://10.117.30.218:8766'
    sender = WebSocketSender(server_url)
    
    print("WebSocket Bandwidth Test - Sender")
    print("Options:")
    print("1. Unlimited bandwidth test (30 seconds)")
    print("2. Rate-limited bandwidth test")
    print("3. Custom duration test")
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice == '1':
        await sender.benchmark_send(duration_seconds=30)
    elif choice == '2':
        target_mbps = float(input("Enter target bandwidth (MBps): "))
        duration = int(input("Enter duration (seconds, default 30): ") or "30")
        await sender.benchmark_send(duration_seconds=duration, target_mbps=target_mbps)
    elif choice == '3':
        duration = int(input("Enter duration (seconds): "))
        await sender.benchmark_send(duration_seconds=duration)
    else:
        print("Invalid choice, running default test")
        await sender.benchmark_send(duration_seconds=30)

if __name__ == "__main__":
    asyncio.run(main())