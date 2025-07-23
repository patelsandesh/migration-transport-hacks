import asyncio
import socket
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MigrationTCPServer:
    def __init__(self, host='0.0.0.0', port=9999, unix_socket_path=None):
        self.host = host
        self.port = port
        self.unix_socket_path = unix_socket_path or '/tmp/qemu_migration_dest.sock'
        self.server = None
        
    async def handle_client(self, reader, writer):
        """Handle incoming TCP connection and forward to unix socket."""
        client_addr = writer.get_extra_info('peername')
        logger.info(f"Client connected from {client_addr}")
        
        try:
            # Wait for the unix socket to be available (QEMU creates it after migrate-incoming)
            logger.info(f"Waiting for unix socket at {self.unix_socket_path}")
            unix_reader, unix_writer = await self.wait_for_unix_socket()
            
            logger.info(f"Connected to QEMU unix socket at {self.unix_socket_path}")
            
            # Create bidirectional forwarding tasks
            tcp_to_unix = asyncio.create_task(
                self.forward_data(reader, unix_writer, "TCP->Unix")
            )
            unix_to_tcp = asyncio.create_task(
                self.forward_data(unix_reader, writer, "Unix->TCP")
            )
            
            # Wait for either task to complete (indicating connection closed)
            done, pending = await asyncio.wait(
                [tcp_to_unix, unix_to_tcp],
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
            writer.close()
            await writer.wait_closed()
            logger.info(f"Client {client_addr} disconnected")
    
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
    
    async def start(self):
        """Start the TCP server."""
        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )
        
        addr = self.server.sockets[0].getsockname()
        logger.info(f"Migration TCP server listening on {addr[0]}:{addr[1]}")
        logger.info(f"Will connect to unix socket at: {self.unix_socket_path}")
        
        async with self.server:
            await self.server.serve_forever()
    
    async def stop(self):
        """Stop the TCP server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()

async def main():
    # Configuration
    host = '0.0.0.0'  # Listen on all interfaces
    port = 9999
    unix_socket_path = '/tmp/qemu_migration_dest.sock'
    
    server = MigrationTCPServer(host, port, unix_socket_path)
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        await server.stop()

if __name__ == "__main__":
    asyncio.run(main())