# eBPF SO_REUSEPORT Selector for Hot-Standby Servers

This project demonstrates how to use `SO_REUSEPORT` with an eBPF program to control how incoming connections are distributed between multiple server processes listening on the same port. This can be used to implement a hot-standby setup or a custom load balancer.

## Objective

The goal is to have two independent TCP server processes listening on the same port. An eBPF program attached to the `SO_REUSEPORT` socket group will inspect incoming connections and decide which server should handle it. In this example, the selection is based on the client's source port:
-   Connections from even source ports are directed to one server.
-   Connections from odd source ports are directed to the other server.

## Files

-   `sockselect-bpf.c`: The eBPF program that gets attached to the reuseport socket group. It defines a `BPF_MAP_TYPE_REUSEPORT_SOCKARRAY` map called `mig_servers` to hold the listening sockets. The program selects a socket based on the source port of the incoming TCP connection.
-   `tcp-server.c`: A user-space TCP server application. It creates a socket, enables `SO_REUSEPORT`, attaches the eBPF program, and adds its own socket descriptor to the `mig_servers` map at a specific index.
-   `unload.sh`: A simple script to clean up by removing the pinned eBPF program and map from the BPF filesystem.
-   `Makefile`: (To be created) For compiling the eBPF program and the TCP server.

## How it Works

1.  The eBPF program (`sockselect-bpf.c`) is compiled and loaded into the kernel. It's pinned to the BPF filesystem at `/sys/fs/bpf/soselect_prog`, and its map `mig_servers` is pinned at `/sys/fs/bpf/mig_servers`.
2.  The first `tcp-server` instance is started, e.g., `./tcp-server 0`.
    -   It creates a TCP socket and sets the `SO_REUSEPORT` option.
    -   It attaches the pinned eBPF program to its socket.
    -   It updates the `mig_servers` map at index `0` with its socket file descriptor.
3.  The second `tcp-server` instance is started, e.g., `./tcp-server 1`.
    -   It performs the same steps, but updates the `mig_servers` map at index `1`.
4.  When a new TCP connection arrives:
    -   The kernel invokes the attached eBPF program.
    -   The program checks the client's source port.
    -   If the port is even, it selects the socket at index `0` from the map.
    -   If the port is odd, it selects the socket at index `1`.
    -   The connection is then passed to the selected server's `accept()` queue.

## Build and Run

You will need `clang`, `llvm`, `libbpf-dev`, and `libelf-dev` to compile the code.

2.  **Compile the code**:
    ```bash
    make
    ```

3.  **Load the eBPF program** (as root):
    ```bash
    sudo make load
    ```

4.  **Run the servers** in separate terminals (as root, or with capabilities to update BPF maps):
    
    *Terminal 1:*
    ```bash
    sudo ./tcp-server 0
    ```
    
    *Terminal 2:*
    ```bash
    sudo ./tcp-server 1
    ```

5.  **Test the connection** from a client. You can use `netcat` (`nc`).

    *Connect from an even source port:*
    ```bash
    # The -p option might require root privileges
    nc -p 50000 localhost 8899
    ```
    This connection should be handled by the first server (`./tcp-server 0`).

    *Connect from an odd source port:*
    ```bash
    nc -p 50001 localhost 8899
    ```
    This connection should be handled by the second server (`./tcp-server 1`).

6.  **Clean up**:
    ```bash
    sudo make unload
    ```
