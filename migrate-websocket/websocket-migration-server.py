import asyncio
import websockets
import ssl
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MigrationWebSocketServer:
    def __init__(self, host='0.0.0.0', port=8766, unix_socket_path=None, cert_dir='certs'):
        self.host = host
        self.port = port
        self.unix_socket_path = unix_socket_path or '/tmp/qemu_migration_dest.sock'
        self.cert_dir = cert_dir
        self.server = None
        
    def create_ssl_context(self):
        """Create SSL context for secure WebSocket connections."""
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        
        # Load server certificate and key
        cert_file = os.path.join(self.cert_dir, 'server-cert.pem')
        key_file = os.path.join(self.cert_dir, 'server-key.pem')
        ca_file = os.path.join(self.cert_dir, 'ca.pem')
        
        if not all(os.path.exists(f) for f in [cert_file, key_file, ca_file]):
            raise FileNotFoundError(f"Certificate files not found in {self.cert_dir}. Run generate_certificates.py first.")
        
        ssl_context.load_cert_chain(cert_file, key_file)
        
        # Enable client certificate verification
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        ssl_context.load_verify_locations(ca_file)
        
        logger.info("SSL context created with client certificate verification")
        return ssl_context
        
    async def handle_client(self, websocket):
        """Handle incoming WebSocket connection and forward to unix socket."""
        client_addr = websocket.remote_address
        
        # Get client certificate info
        client_cert = websocket.transport.get_extra_info('ssl_object').getpeercert()
        client_cn = None
        if client_cert:
            for item in client_cert.get('subject', []):
                for key, value in item:
                    if key == 'commonName':
                        client_cn = value
                        break
        
        logger.info(f"Secure WebSocket client connected from {client_addr} (CN: {client_cn})")
        
        try:
            # Wait for the unix socket to be available (QEMU creates it after migrate-incoming)
            logger.info(f"Waiting for unix socket at {self.unix_socket_path}")
            unix_reader, unix_writer = await self.wait_for_unix_socket()
            
            logger.info(f"Connected to QEMU unix socket at {self.unix_socket_path}")
            
            # Create bidirectional forwarding tasks
            ws_to_unix = asyncio.create_task(
                self.forward_ws_to_unix(websocket, unix_writer)
            )
            unix_to_ws = asyncio.create_task(
                self.forward_unix_to_ws(unix_reader, websocket)
            )
            
            # Wait for either task to complete (indicating connection closed)
            done, pending = await asyncio.wait(
                [ws_to_unix, unix_to_ws],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Close unix socket connection
            unix_writer.close()
            await unix_writer.wait_closed()
            logger.info("Disconnected from QEMU unix socket")
                
        except asyncio.CancelledError:
            logger.info("Client handler cancelled")
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            logger.info(f"Secure WebSocket client {client_addr} disconnected")
    
    async def wait_for_unix_socket(self, max_retries=30, retry_delay=1):
        """Wait for unix socket to become available and connect to it."""
        for attempt in range(max_retries):
            try:
                if os.path.exists(self.unix_socket_path):
                    # Try to connect to the unix socket
                    unix_reader, unix_writer = await asyncio.open_unix_connection(
                        path=self.unix_socket_path
                    )
                    return unix_reader, unix_writer
                else:
                    logger.info(f"Unix socket not found, waiting... (attempt {attempt + 1}/{max_retries})")
                    
            except (ConnectionRefusedError, FileNotFoundError) as e:
                logger.info(f"Cannot connect to unix socket, retrying... (attempt {attempt + 1}/{max_retries}): {e}")
            
            await asyncio.sleep(retry_delay)
        
        raise Exception(f"Failed to connect to unix socket {self.unix_socket_path} after {max_retries} attempts")
    
    async def forward_ws_to_unix(self, websocket, unix_writer):
        """Forward data from WebSocket to Unix socket."""
        total_bytes = 0
        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    unix_writer.write(message)
                    await unix_writer.drain()
                    total_bytes += len(message)
                    
                    if total_bytes % (1024 * 1024) == 0:  # Log every MB
                        logger.info(f"WebSocket->Unix: Forwarded {total_bytes // (1024*1024)} MB")
                        
        except asyncio.CancelledError:
            logger.info("WebSocket->Unix: Forwarding cancelled")
        except Exception as e:
            logger.error(f"WebSocket->Unix: Error forwarding data: {e}")
        finally:
            logger.info(f"WebSocket->Unix: Total bytes forwarded: {total_bytes}")
    
    async def forward_unix_to_ws(self, unix_reader, websocket):
        """Forward data from Unix socket to WebSocket."""
        total_bytes = 0
        try:
            while True:
                data = await unix_reader.read(8192)
                if not data:
                    logger.info("Unix->WebSocket: Connection closed by peer")
                    break
                
                await websocket.send(data)
                total_bytes += len(data)
                
                if total_bytes % (1024 * 1024) == 0:  # Log every MB
                    logger.info(f"Unix->WebSocket: Forwarded {total_bytes // (1024*1024)} MB")
                    
        except asyncio.CancelledError:
            logger.info("Unix->WebSocket: Forwarding cancelled")
        except Exception as e:
            logger.error(f"Unix->WebSocket: Error forwarding data: {e}")
        finally:
            logger.info(f"Unix->WebSocket: Total bytes forwarded: {total_bytes}")
    
    async def start(self):
        """Start the secure WebSocket server."""
        # Create SSL context
        ssl_context = self.create_ssl_context()
        
        # Create a wrapper function that properly handles the websockets callback
        async def handler(websocket):
            await self.handle_client(websocket)
        
        self.server = await websockets.serve(
            handler,
            self.host,
            self.port,
            ssl=ssl_context
        )
        
        logger.info(f"Secure Migration WebSocket server listening on wss://{self.host}:{self.port}")
        logger.info(f"Will connect to unix socket at: {self.unix_socket_path}")
        logger.info("Client certificate authentication enabled")
        
        await self.server.wait_closed()
    
    async def stop(self):
        """Stop the WebSocket server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()

async def main():
    # Configuration
    host = '0.0.0.0'  # Listen on all interfaces
    port = 8766  # Changed from 8765 to 8766 for secure WebSocket
    unix_socket_path = '/tmp/qemu_migration_dest.sock'
    cert_dir = 'certs'
    
    server = MigrationWebSocketServer(host, port, unix_socket_path, cert_dir)
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        await server.stop()

if __name__ == "__main__":
    asyncio.run(main())
