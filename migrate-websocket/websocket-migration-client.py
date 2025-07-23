import asyncio
import websockets
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MigrationWebSocketClient:
    def __init__(self, server_url, unix_socket_path=None):
        self.server_url = server_url
        self.unix_socket_path = unix_socket_path or '/tmp/qemu_migration_source.sock'
        self.websocket = None
        
    async def connect_and_forward(self):
        """Connect to WebSocket server and forward unix socket data."""
        
        # Remove existing unix socket if it exists
        if os.path.exists(self.unix_socket_path):
            os.unlink(self.unix_socket_path)
        
        # Connect to WebSocket server
        try:
            self.websocket = await websockets.connect(self.server_url)
            logger.info(f"Connected to migration server at {self.server_url}")
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
    server_url = 'ws://10.117.30.218:8765'  # Replace with destination server IP/URL
    unix_socket_path = '/tmp/qemu_migration_source.sock'
    
    client = MigrationWebSocketClient(server_url, unix_socket_path)
    
    try:
        await client.connect_and_forward()
    except KeyboardInterrupt:
        logger.info("Shutting down client...")

if __name__ == "__main__":
    asyncio.run(main())
