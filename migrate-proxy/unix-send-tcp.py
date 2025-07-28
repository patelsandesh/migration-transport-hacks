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

async def migrate_vm_tcp_forwarded(qmp_socket_path, tcp_unix_socket_path=None):
    """
    Migrate a QEMU VM using TCP-forwarded unix socket.
    
    Args:
        qmp_socket_path: Path to QEMU QMP socket
        tcp_unix_socket_path: Path to unix socket that forwards to TCP
    """
    
    if tcp_unix_socket_path is None:
        tcp_unix_socket_path = "/tmp/qemu_migration_source.sock"
    
    destination_uri = f"unix:{tcp_unix_socket_path}"
    
    qmp_client = QMPClient()
    
    try:
        # Connect to QEMU QMP socket
        await qmp_client.connect(qmp_socket_path)
        
        print(f"Connected to QMP socket: {qmp_socket_path}")
        
        # Check VM status
        result = await qmp_client.execute('query-status')
        print(f"VM Status: {result}")
        
        # Enable multifd migration capability
        print("Enabling multifd migration capability")
        await qmp_client.execute('migrate-set-capabilities', {
            'capabilities': [{'capability': 'multifd', 'state': True}]
        })

        # Configure migration parameters
        print("Setting migration multfd channels to 2...")
        await qmp_client.execute('migrate-set-parameters', {
            'multifd-channels': 2
        })
    
        
        print("Migration parameters configured successfully")
        
        # Execute and monitor migration
        await execute_and_monitor_migration(qmp_client, destination_uri)
            
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        await qmp_client.disconnect()

async def main():
    # Default QMP socket path - adjust as needed
    qmp_socket = "/tmp/qemu-monitor.sock"
    
    # TCP-forwarded unix socket path (created by tcp-migration-client.py)
    tcp_unix_socket = "/tmp/qemu_migration_source.sock"
    
    await migrate_vm_tcp_forwarded(qmp_socket, tcp_unix_socket)

if __name__ == "__main__":
    asyncio.run(main())