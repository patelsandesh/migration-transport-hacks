import asyncio
import websockets
import ssl
import time
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebSocketReceiver:
    def __init__(self, host='0.0.0.0', port=8766, cert_dir='../../migrate-websocket/certs'):
        self.host = host
        self.port = port
        self.cert_dir = cert_dir
        
    def create_ssl_context(self):
        """Create SSL context for secure WebSocket server."""
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
        
    async def handle_client(self, websocket):
        """Handle incoming WebSocket connection and measure receive bandwidth."""
        client_addr = websocket.remote_address
        logger.info(f"Client connected from {client_addr}")
        
        try:
            start_time = time.time()
            bytes_received = 0
            chunks_received = 0
            last_report_time = start_time
            last_report_bytes = 0
            
            async for message in websocket:
                if isinstance(message, bytes):
                    bytes_received += len(message)
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
                        
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Error handling client: {e}")
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
        
    async def start_server(self):
        """Start the WebSocket server."""
        ssl_context = self.create_ssl_context()
        
        server = await websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            ssl=ssl_context
        )
        
        logger.info(f"WebSocket bandwidth test server listening on wss://{self.host}:{self.port}")
        logger.info("Waiting for client connections...")
        logger.info("Server supports multiple concurrent connections")
        
        await server.wait_closed()

async def main():
    receiver = WebSocketReceiver()
    
    try:
        await receiver.start_server()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    except Exception as e:
        logger.error(f"Server error: {e}")

if __name__ == "__main__":
    print("WebSocket Bandwidth Test - Receiver")
    print("Starting server...")
    asyncio.run(main())