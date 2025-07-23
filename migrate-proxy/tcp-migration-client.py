import asyncio
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MigrationTCPClient:
    def __init__(self, server_host, server_port=9999, unix_socket_path=None):
        self.server_host = server_host
        self.server_port = server_port
        self.unix_socket_path = unix_socket_path or '/tmp/qemu_migration_source.sock'
        
    async def connect_and_forward(self):
        """Connect to TCP server and forward unix socket data."""
        
        # Remove existing unix socket if it exists
        if os.path.exists(self.unix_socket_path):
            os.unlink(self.unix_socket_path)
        
        # Connect to TCP server
        try:
            tcp_reader, tcp_writer = await asyncio.open_connection(
                self.server_host, self.server_port
            )
            logger.info(f"Connected to migration server at {self.server_host}:{self.server_port}")
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            return
        
        # Create unix socket server for QEMU source
        try:
            unix_server = await asyncio.start_unix_server(
                lambda r, w: self.handle_qemu_connection(r, w, tcp_reader, tcp_writer),
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
            tcp_writer.close()
            await tcp_writer.wait_closed()
            if os.path.exists(self.unix_socket_path):
                os.unlink(self.unix_socket_path)
    
    async def handle_qemu_connection(self, unix_reader, unix_writer, tcp_reader, tcp_writer):
        """Handle QEMU connection and forward to/from TCP server."""
        logger.info("QEMU connected to unix socket")
        
        try:
            # Create bidirectional forwarding tasks
            unix_to_tcp = asyncio.create_task(
                self.forward_data(unix_reader, tcp_writer, "Unix->TCP")
            )
            tcp_to_unix = asyncio.create_task(
                self.forward_data(tcp_reader, unix_writer, "TCP->Unix")
            )
            
            # Wait for either task to complete
            done, pending = await asyncio.wait(
                [unix_to_tcp, tcp_to_unix],
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
    
    async def forward_data(self, reader, writer, direction):
        """Forward data between reader and writer."""
        total_bytes = 0
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    logger.info(f"{direction}: Connection closed by peer")
                    break
                
                writer.write(data)
                await writer.drain()
                total_bytes += len(data)
                
                if total_bytes % (1024 * 1024) == 0:  # Log every MB
                    logger.info(f"{direction}: Forwarded {total_bytes // (1024*1024)} MB")
                    
        except asyncio.CancelledError:
            logger.info(f"{direction}: Forwarding cancelled")
        except Exception as e:
            logger.error(f"{direction}: Error forwarding data: {e}")
        finally:
            logger.info(f"{direction}: Total bytes forwarded: {total_bytes}")

async def main():
    # Configuration
    server_host = '192.168.1.100'  # Replace with destination server IP
    server_port = 9999
    unix_socket_path = '/tmp/qemu_migration_source.sock'
    
    client = MigrationTCPClient(server_host, server_port, unix_socket_path)
    
    try:
        await client.connect_and_forward()
    except KeyboardInterrupt:
        logger.info("Shutting down client...")

if __name__ == "__main__":
    asyncio.run(main())