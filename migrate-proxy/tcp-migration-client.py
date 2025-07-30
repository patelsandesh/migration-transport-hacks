import asyncio
import os
import logging
from collections import defaultdict, deque

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CircularQueue:
    def __init__(self, maxsize=1000):
        self.queue = deque(maxlen=maxsize)
        self.lock = asyncio.Lock()
        self.not_empty = asyncio.Condition(self.lock)
        self.closed = False
    
    async def put(self, item):
        async with self.not_empty:
            if not self.closed:
                self.queue.append(item)
                self.not_empty.notify()
    
    async def get(self):
        async with self.not_empty:
            while len(self.queue) == 0 and not self.closed:
                await self.not_empty.wait()
            if self.queue:
                return self.queue.popleft()
            return None
    
    async def close(self):
        async with self.not_empty:
            self.closed = True
            self.not_empty.notify_all()

class MigrationTCPClient:
    def __init__(self, server_host, server_port=9999, unix_socket_path=None):
        self.server_host = server_host
        self.server_port = server_port
        self.unix_socket_path = unix_socket_path or '/tmp/qemu_migration_source.sock'
        self.connection_counter = 0
        self.read_histogram = defaultdict(int)  # Track histogram of bytes read
        
    async def connect_and_forward(self):
        """Create unix socket server and handle multiple QEMU connections."""
        
        # Remove existing unix socket if it exists
        if os.path.exists(self.unix_socket_path):
            os.unlink(self.unix_socket_path)
        
        # Create unix socket server for QEMU source
        try:
            unix_server = await asyncio.start_unix_server(
                self.handle_new_qemu_connection,
                path=self.unix_socket_path
            )
            
            logger.info(f"Unix socket server started at {self.unix_socket_path}")
            logger.info("Waiting for QEMU connections...")
            
            # Serve the unix socket
            async with unix_server:
                await unix_server.serve_forever()
                
        except Exception as e:
            logger.error(f"Unix socket server error: {e}")
        finally:
            if os.path.exists(self.unix_socket_path):
                os.unlink(self.unix_socket_path)
    
    async def handle_new_qemu_connection(self, unix_reader, unix_writer):
        """Handle each new QEMU connection by creating a dedicated TCP connection."""
        self.connection_counter += 1
        connection_id = self.connection_counter
        logger.info(f"QEMU connection #{connection_id} established")
        
        tcp_reader = None
        tcp_writer = None
        
        try:
            # Create a new TCP connection to the server for this QEMU connection
            tcp_reader, tcp_writer = await asyncio.open_connection(
                self.server_host, self.server_port
            )
            logger.info(f"Connection #{connection_id}: Created TCP connection to {self.server_host}:{self.server_port}")
            
            # Create bidirectional forwarding tasks for this connection pair
            unix_to_tcp = asyncio.create_task(
                self.forward_data(unix_reader, tcp_writer, f"Connection #{connection_id} Unix->TCP")
            )
            tcp_to_unix = asyncio.create_task(
                self.forward_data(tcp_reader, unix_writer, f"Connection #{connection_id} TCP->Unix")
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
            logger.error(f"Connection #{connection_id}: Error in connection handler: {e}")
        finally:
            # Clean up connections
            if tcp_writer:
                tcp_writer.close()
                await tcp_writer.wait_closed()
            unix_writer.close()
            await unix_writer.wait_closed()
            logger.info(f"Connection #{connection_id}: QEMU and TCP connections closed")
    
    async def forward_data(self, reader, writer, direction):
        """Forward data between reader and writer using a circular queue."""
        total_bytes = 0
        queue = CircularQueue(maxsize=1000)
        
        async def read_task():
            try:
                while True:
                    data = await reader.read(8192)
                    if not data:
                        logger.info(f"{direction}: Connection closed by peer")
                        break
                    
                    # Track bytes read in histogram
                    bytes_read = len(data)
                    self.read_histogram[bytes_read] += 1
                    
                    await queue.put(data)
                    
            except asyncio.CancelledError:
                logger.info(f"{direction}: Read task cancelled")
            except Exception as e:
                logger.error(f"{direction}: Error reading data: {e}")
            finally:
                await queue.close()
        
        async def write_task():
            nonlocal total_bytes
            try:
                while True:
                    data = await queue.get()
                    if data is None:  # Queue closed and empty
                        break
                    
                    writer.write(data)
                    # await writer.drain()
                    total_bytes += len(data)
                    
                    if total_bytes % (1024 * 1024) == 0:  # Log every MB
                        logger.info(f"{direction}: Forwarded {total_bytes // (1024*1024)} MB")
                        
            except asyncio.CancelledError:
                logger.info(f"{direction}: Write task cancelled")
            except Exception as e:
                logger.error(f"{direction}: Error writing data: {e}")
        
        try:
            # Start both read and write tasks
            read_worker = asyncio.create_task(read_task())
            write_worker = asyncio.create_task(write_task())
            
            # Wait for both to complete
            await asyncio.gather(read_worker, write_worker, return_exceptions=True)
            
        except asyncio.CancelledError:
            logger.info(f"{direction}: Forwarding cancelled")
        except Exception as e:
            logger.error(f"{direction}: Error in forwarding tasks: {e}")
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

async def main():
    # Configuration
    server_host = '10.117.30.218'  # Replace with destination server IP
    server_port = 9999
    unix_socket_path = '/tmp/qemu_migration_source.sock'
    
    client = MigrationTCPClient(server_host, server_port, unix_socket_path)
    
    try:
        await client.connect_and_forward()
    except KeyboardInterrupt:
        logger.info("Shutting down client...")
    finally:
        # Print histogram when exiting
        client.print_histogram()

if __name__ == "__main__":
    asyncio.run(main())