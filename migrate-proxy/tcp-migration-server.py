import asyncio
import socket
import os
import logging
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MigrationTCPServer:
    def __init__(self, host='0.0.0.0', port=9999, unix_socket_path=None):
        self.host = host
        self.port = port
        self.unix_socket_path = unix_socket_path or '/tmp/qemu_migration_dest.sock'
        self.server = None
        self.connection_counter = 0
        self.read_histogram = defaultdict(int)  # Track histogram of bytes read
        
    async def handle_client(self, reader, writer):
        """Handle incoming TCP connection and forward to unix socket."""
        self.connection_counter += 1
        connection_id = self.connection_counter
        client_addr = writer.get_extra_info('peername')
        logger.info(f"Connection #{connection_id}: Client connected from {client_addr}")
        
        unix_reader = None
        unix_writer = None
        
        try:
            # Connect to the unix socket for this TCP connection
            logger.info(f"Connection #{connection_id}: Connecting to unix socket at {self.unix_socket_path}")
            unix_reader, unix_writer = await self.connect_to_unix_socket()
            
            logger.info(f"Connection #{connection_id}: Connected to QEMU unix socket")
            
            # Create bidirectional forwarding tasks
            tcp_to_unix = asyncio.create_task(
                self.forward_data(reader, unix_writer, f"Connection #{connection_id} TCP->Unix")
            )
            unix_to_tcp = asyncio.create_task(
                self.forward_data(unix_reader, writer, f"Connection #{connection_id} Unix->TCP")
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
                
        except asyncio.CancelledError:
            logger.info(f"Connection #{connection_id}: Client handler cancelled")
        except Exception as e:
            logger.error(f"Connection #{connection_id}: Error handling client: {e}")
        finally:
            # Clean up connections
            if unix_writer:
                unix_writer.close()
                await unix_writer.wait_closed()
            writer.close()
            await writer.wait_closed()
            logger.info(f"Connection #{connection_id}: Client {client_addr} and unix socket disconnected")
    
    async def connect_to_unix_socket(self, max_retries=30, retry_delay=1):
        """Connect to unix socket."""
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
                
                # Track bytes read in histogram
                bytes_read = len(data)
                self.read_histogram[bytes_read] += 1
                
                writer.write(data)
                await writer.drain()
                total_bytes += bytes_read
                
                if total_bytes % (1024 * 1024) == 0:  # Log every MB
                    logger.info(f"{direction}: Forwarded {total_bytes // (1024*1024)} MB")
                    
        except asyncio.CancelledError:
            logger.info(f"{direction}: Forwarding cancelled")
        except Exception as e:
            logger.error(f"{direction}: Error forwarding data: {e}")
        finally:
            logger.info(f"{direction}: Total bytes forwarded: {total_bytes}")
    
    def print_histogram(self):
        """Print histogram of bytes read when exiting."""
        logger.info("=== Read Bytes Histogram ===")
        if not self.read_histogram:
            logger.info("No data read")
            return
            
        # Sort by byte count for better readability
        sorted_histogram = sorted(self.read_histogram.items())
        total_reads = sum(self.read_histogram.values())
        
        for byte_count, frequency in sorted_histogram:
            percentage = (frequency / total_reads) * 100
            logger.info(f"{byte_count:5d} bytes: {frequency:5d} times ({percentage:5.1f}%)")
        
        logger.info(f"Total reads: {total_reads}")
        logger.info("============================")
    
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
    finally:
        # Print histogram when exiting
        server.print_histogram()

if __name__ == "__main__":
    asyncio.run(main())