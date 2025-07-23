import asyncio
import tempfile
import os
from qemu.qmp import QMPClient

#!/usr/bin/env python3


async def monitor_incoming_migration(qmp_client):
    """
    Monitor the incoming migration progress.
    
    Args:
        qmp_client: An instance of QMPClient connected to the QEMU QMP socket.
    """
    print("Monitoring incoming migration...")
    
    while True:
        migration_info = await qmp_client.execute('query-migrate')
        status = migration_info.get('status', 'unknown')
        
        print(f"Migration status: {status}")
        
        if status == 'completed':
            print("Migration received successfully!")
            break
        elif status == 'failed':
            print("Migration reception failed!")
            break
        elif status == 'cancelled':
            print("Migration was cancelled!")
            break
        elif status == 'active':
            # Show progress if available
            if 'ram' in migration_info:
                ram_info = migration_info['ram']
                transferred = ram_info.get('transferred', 0)
                total = ram_info.get('total', 0)
                if total > 0:
                    progress = (transferred / total) * 100
                    print(f"Migration progress: {progress:.2f}%")
        
        # Wait before checking again
        await asyncio.sleep(1)


async def setup_incoming_migration(qmp_socket_path, incoming_uri=None):
    """
    Setup QEMU VM to receive incoming migration over unix socket.
    
    Args:
        qmp_socket_path: Path to QEMU QMP socket
        incoming_uri: Optional incoming URI, defaults to unix socket in /tmp
    """
    
    # Create unix socket in /tmp for incoming migration if not provided
    if incoming_uri is None:
        temp_fd, temp_socket_path = tempfile.mkstemp(
            suffix='.sock', 
            prefix='qemu_incoming_', 
            dir='/tmp'
        )
        os.close(temp_fd)
        os.unlink(temp_socket_path)  # Remove the file, keep the path
        incoming_uri = f"unix:{temp_socket_path}"
    
    print(f"Setting up incoming migration on: {incoming_uri}")
    
    qmp_client = QMPClient()
    
    try:
        # Connect to QEMU QMP socket
        await qmp_client.connect(qmp_socket_path)
        
        print(f"Connected to QMP socket: {qmp_socket_path}")
        
        # Check VM status
        result = await qmp_client.execute('query-status')
        print(f"VM Status: {result}")
        
        # Setup incoming migration
        print(f"Setting up incoming migration from: {incoming_uri}")
        migrate_incoming_result = await qmp_client.execute('migrate-incoming', {
            'uri': incoming_uri
        })
        print(f"Migrate-incoming command result: {migrate_incoming_result}")
        
        # Monitor the incoming migration
        await monitor_incoming_migration(qmp_client)
            
    except Exception as e:
        print(f"Error during incoming migration setup: {e}")
    finally:
        await qmp_client.disconnect()


async def main():
    # Default QMP socket path for destination VM - adjust as needed
    qmp_socket = "/var/run/qemu-server/vm-dest.qmp"
    
    # You can specify a custom incoming URI if needed
    # This should match the destination URI used in unix-send.py
    # incoming = "unix:/tmp/custom_migrate.sock"
    incoming = None
    
    await setup_incoming_migration(qmp_socket, incoming)

if __name__ == "__main__":
    asyncio.run(main())