import asyncio
import websockets
import ssl
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MigrationWebSocketClient:
    def __init__(self, server_url, unix_socket_path=None, cert_dir='certs'):
        self.server_url = server_url
        self.unix_socket_path = unix_socket_path or '/tmp/qemu_migration_source.sock'
        self.cert_dir = cert_dir
        self.websocket = None
        
    def create_ssl_context(self):
        """Create SSL context for secure WebSocket connection."""
        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        
        # Load client certificate and key
        cert_file = os.path.join(self.cert_dir, 'client-cert.pem')
        key_file = os.path.join(self.cert_dir, 'client-key.pem')
        ca_file = os.path.join(self.cert_dir, 'ca.pem')
        
        if not all(os.path.exists(f) for f in [cert_file, key_file, ca_file]):
            raise FileNotFoundError(f"Certificate files not found in {self.cert_dir}. Run generate_certificates.py first.")
        
        # Load client certificate for authentication
        ssl_context.load_cert_chain(cert_file, key_file)
        
        # Load CA certificate to verify server
        ssl_context.load_verify_locations(ca_file)
        
        # Verify server certificate
        ssl_context.check_hostname = False  # Set to True if using proper hostname
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        
        logger.info("SSL context created with client certificate authentication")
        return ssl_context
        
    async def connect_and_forward(self):
        """Connect to WebSocket server and forward unix socket data."""
        
        # Remove existing unix socket if it exists
        if os.path.exists(self.unix_socket_path):
            os.unlink(self.unix_socket_path)
        
        # Create SSL context
        ssl_context = self.create_ssl_context()
        
        # Connect to secure WebSocket server
        try:
            self.websocket = await websockets.connect(
                self.server_url,
                ssl=ssl_context
            )
            logger.info(f"Securely connected to migration server at {self.server_url}")
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            return
        
        # Create unix socket server for QEMU source
        try:
            unix_server = await asyncio.start_unix_server(
                self.handle_qemu_connection,
                path=self.unix_socket_path
            )
            
            logger.info(f"Unix socket server started at {self.unix_socket_path}")
            logger.info("Waiting for QEMU to connect...")
            
            # Serve the unix socket
            async with unix_server:
                await unix_server.serve_forever()
                
        except Exception as e:
            logger.error(f"Unix socket server error: {e}")
        finally:
            await self.websocket.close()
            if os.path.exists(self.unix_socket_path):
                os.unlink(self.unix_socket_path)
    
    async def handle_qemu_connection(self, unix_reader, unix_writer):
        """Handle QEMU connection and forward to/from WebSocket server."""
        logger.info("QEMU connected to unix socket")
        
        try:
            # Create bidirectional forwarding tasks
            unix_to_ws = asyncio.create_task(
                self.forward_unix_to_ws(unix_reader)
            )
            ws_to_unix = asyncio.create_task(
                self.forward_ws_to_unix(unix_writer)
            )
            
            # Wait for either task to complete
            done, pending = await asyncio.wait(
                [unix_to_ws, ws_to_unix],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        except Exception as e:
            logger.error(f"Error in QEMU connection handler: {e}")
        finally:
            unix_writer.close()
            await unix_writer.wait_closed()
            logger.info("QEMU disconnected from unix socket")
    
    async def forward_unix_to_ws(self, unix_reader):
        """Forward data from Unix socket to WebSocket."""
        total_bytes = 0
        try:
            while True:
                data = await unix_reader.read(8192)
                if not data:
                    logger.info("Unix->WebSocket: Connection closed by peer")
                    break
                
                await self.websocket.send(data)
                total_bytes += len(data)
                
                if total_bytes % (1024 * 1024) == 0:  # Log every MB
                    logger.info(f"Unix->WebSocket: Forwarded {total_bytes // (1024*1024)} MB")
                    
        except asyncio.CancelledError:
            logger.info("Unix->WebSocket: Forwarding cancelled")
        except Exception as e:
            logger.error(f"Unix->WebSocket: Error forwarding data: {e}")
        finally:
            logger.info(f"Unix->WebSocket: Total bytes forwarded: {total_bytes}")
    
    async def forward_ws_to_unix(self, unix_writer):
        """Forward data from WebSocket to Unix socket."""
        total_bytes = 0
        try:
            async for message in self.websocket:
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

async def main():
    # Configuration
    server_url = 'wss://10.117.30.218:8766'  # Changed to wss:// and port 8766
    unix_socket_path = '/tmp/qemu_migration_source.sock'
    cert_dir = 'certs'
    
    client = MigrationWebSocketClient(server_url, unix_socket_path, cert_dir)
    
    try:
        await client.connect_and_forward()
    except KeyboardInterrupt:
        logger.info("Shutting down client...")

if __name__ == "__main__":
    asyncio.run(main())
