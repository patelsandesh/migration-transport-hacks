import asyncio
import tempfile
import os
from qemu.qmp import QMPClient

#!/usr/bin/env python3


async def execute_and_monitor_migration(qmp_client, destination_uri):
    """
    Execute the migration command and monitor its progress.
    
    Args:
        qmp_client: An instance of QMPClient connected to the QEMU QMP socket.
        destination_uri: The destination URI for migration.
    """
    # Start migration
    print(f"Starting migration to: {destination_uri}")
    migrate_result = await qmp_client.execute('migrate', {
        'uri': destination_uri
    })
    print(f"Migration command result: {migrate_result}")
    
    # Monitor migration progress
    while True:
        migration_info = await qmp_client.execute('query-migrate')
        status = migration_info.get('status', 'unknown')
        
        print(f"Migration status: {status}")
        
        if status == 'completed':
            print("Migration completed successfully!")
            break
        elif status == 'failed':
            print("Migration failed!")
            break
        elif status == 'cancelled':
            print("Migration was cancelled!")
            break
        
        # Wait before checking again
        await asyncio.sleep(1)


async def migrate_vm_unix_socket(qmp_socket_path, destination_uri=None):
    """
    Migrate a QEMU VM using QMP commands over unix domain socket.
    
    Args:
        qmp_socket_path: Path to QEMU QMP socket
        destination_uri: Optional destination URI, defaults to unix socket in /tmp
    """
    
    # Create unix socket in /tmp for migration if not provided
    if destination_uri is None:
        temp_fd, temp_socket_path = tempfile.mkstemp(
            suffix='.sock', 
            prefix='qemu_migrate_', 
            dir='/tmp'
        )
        os.close(temp_fd)
        os.unlink(temp_socket_path)  # Remove the file, keep the path
        destination_uri = f"unix:{temp_socket_path}"
    
    qmp_client = QMPClient()
    
    try:
        # Connect to QEMU QMP socket
        await qmp_client.connect(qmp_socket_path)
        
        print(f"Connected to QMP socket: {qmp_socket_path}")
        
        # Check VM status
        result = await qmp_client.execute('query-status')
        print(f"VM Status: {result}")
        
        # Execute and monitor migration
        await execute_and_monitor_migration(qmp_client, destination_uri)
            
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        await qmp_client.disconnect()

async def main():
    # Default QMP socket path - adjust as needed
    qmp_socket = "/var/run/qemu-server/vm.qmp"
    
    # You can specify a custom destination URI if needed
    # destination = "unix:/tmp/custom_migrate.sock"
    destination = None
    
    await migrate_vm_unix_socket(qmp_socket, destination)

if __name__ == "__main__":
    asyncio.run(main())