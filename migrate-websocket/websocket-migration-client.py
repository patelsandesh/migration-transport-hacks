import asyncio
import websockets
import ssl
import os
import logging
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MigrationWebSocketClient:
    def __init__(self, server_url, unix_socket_path=None, cert_dir='certs'):
        self.server_url = server_url
        self.unix_socket_path = unix_socket_path or '/tmp/qemu_migration_source.sock'
        self.cert_dir = cert_dir
        self.active_connections = {}  # Track active connections
        
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
        
    async def start_unix_server(self):
        """Start unix socket server and handle multiple QEMU connections."""
        
        # Remove existing unix socket if it exists
        if os.path.exists(self.unix_socket_path):
            os.unlink(self.unix_socket_path)
        
        # Create unix socket server for QEMU source
        try:
            unix_server = await asyncio.start_unix_server(
                self.handle_qemu_connection,
                path=self.unix_socket_path
            )
            
            logger.info(f"Unix socket server started at {self.unix_socket_path}")
            logger.info("Waiting for QEMU connections...")
            logger.info("Supporting multiple concurrent QEMU connections")
            
            # Serve the unix socket
            async with unix_server:
                await unix_server.serve_forever()
                
        except Exception as e:
            logger.error(f"Unix socket server error: {e}")
        finally:
            # Clean up any remaining connections
            for connection_id in list(self.active_connections.keys()):
                await self.cleanup_connection(connection_id)
            
            if os.path.exists(self.unix_socket_path):
                os.unlink(self.unix_socket_path)
    
    async def handle_qemu_connection(self, unix_reader, unix_writer):
        """Handle QEMU connection and create corresponding WebSocket connection."""
        connection_id = str(uuid.uuid4())[:8]
        logger.info(f"QEMU connection {connection_id} established on unix socket")
        
        try:
            # Create SSL context
            ssl_context = self.create_ssl_context()
            
            # Create WebSocket connection for this QEMU connection
            websocket = await websockets.connect(
                self.server_url,
                ssl=ssl_context
            )
            logger.info(f"WebSocket connection {connection_id} established to {self.server_url}")
            
            # Store connection info
            self.active_connections[connection_id] = {
                'websocket': websocket,
                'unix_reader': unix_reader,
                'unix_writer': unix_writer
            }
            
            # Create bidirectional forwarding tasks
            unix_to_ws = asyncio.create_task(
                self.forward_unix_to_ws(unix_reader, websocket, connection_id)
            )
            ws_to_unix = asyncio.create_task(
                self.forward_ws_to_unix(websocket, unix_writer, connection_id)
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
            logger.error(f"Error in QEMU connection {connection_id}: {e}")
        finally:
            await self.cleanup_connection(connection_id)
    
    async def cleanup_connection(self, connection_id):
        """Clean up a connection and its resources."""
        if connection_id in self.active_connections:
            conn_info = self.active_connections[connection_id]
            
            # Close WebSocket
            if 'websocket' in conn_info:
                await conn_info['websocket'].close()
            
            # Close unix socket
            if 'unix_writer' in conn_info:
                conn_info['unix_writer'].close()
                await conn_info['unix_writer'].wait_closed()
            
            del self.active_connections[connection_id]
            logger.info(f"Connection {connection_id} cleaned up")
    
    async def forward_unix_to_ws(self, unix_reader, websocket, connection_id):
        """Forward data from Unix socket to WebSocket."""
        total_bytes = 0
        try:
            while True:
                data = await unix_reader.read(8192)
                if not data:
                    logger.info(f"Unix->WebSocket [{connection_id}]: Connection closed by peer")
                    break
                
                await websocket.send(data)
                total_bytes += len(data)
                
                if total_bytes % (1024 * 1024) == 0:  # Log every MB
                    logger.info(f"Unix->WebSocket [{connection_id}]: Forwarded {total_bytes // (1024*1024)} MB")
                    
        except asyncio.CancelledError:
            logger.info(f"Unix->WebSocket [{connection_id}]: Forwarding cancelled")
        except Exception as e:
            logger.error(f"Unix->WebSocket [{connection_id}]: Error forwarding data: {e}")
        finally:
            logger.info(f"Unix->WebSocket [{connection_id}]: Total bytes forwarded: {total_bytes}")
    
    async def forward_ws_to_unix(self, websocket, unix_writer, connection_id):
        """Forward data from WebSocket to Unix socket."""
        total_bytes = 0
        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    unix_writer.write(message)
                    await unix_writer.drain()
                    total_bytes += len(message)
                    
                    if total_bytes % (1024 * 1024) == 0:  # Log every MB
                        logger.info(f"WebSocket->Unix [{connection_id}]: Forwarded {total_bytes // (1024*1024)} MB")
                        
        except asyncio.CancelledError:
            logger.info(f"WebSocket->Unix [{connection_id}]: Forwarding cancelled")
        except Exception as e:
            logger.error(f"WebSocket->Unix [{connection_id}]: Error forwarding data: {e}")
        finally:
            logger.info(f"WebSocket->Unix [{connection_id}]: Total bytes forwarded: {total_bytes}")

async def main():
    # Configuration
    server_url = 'wss://10.117.30.218:8766'  # Changed to wss:// and port 8766
    unix_socket_path = '/tmp/qemu_migration_source.sock'
    cert_dir = 'certs'
    
    client = MigrationWebSocketClient(server_url, unix_socket_path, cert_dir)
    
    try:
        await client.start_unix_server()
    except KeyboardInterrupt:
        logger.info("Shutting down client...")

if __name__ == "__main__":
    asyncio.run(main())
