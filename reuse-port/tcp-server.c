#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <errno.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <linux/bpf.h>
#include <bpf/bpf.h>
#include <bpf/libbpf.h>

#define PORT 8899
#define BACKLOG 128

// Alternative function to get BPF program fd from pinned program
int get_pinned_bpf_prog(const char *pin_path)
{
    int prog_fd = bpf_obj_get(pin_path);
    if (prog_fd < 0)
    {
        perror("Failed to get pinned BPF program");
        fprintf(stderr, "Make sure the program is pinned at %s\n", pin_path);
        return -1;
    }

    printf("Retrieved pinned BPF program, fd: %d\n", prog_fd);
    return prog_fd;
}

int update_bpf_map_pinned(__u32 value, __u32 key)
{
    int map_fd;
    const char *map_path = "/sys/fs/bpf/mig_servers";

    __u32 existing_value = 0;

    // Open the pinned map
    map_fd = bpf_obj_get(map_path);
    if (map_fd < 0)
    {
        perror("Failed to open pinned BPF map");
        fprintf(stderr, "Make sure the map is pinned at %s\n", map_path);
        return -1;
    }

    // Read existing value from the map at key_index
    if (bpf_map_lookup_elem(map_fd, &key, &existing_value) == 0)
    {
        printf("Read existing value from map at key %u: %u\n", key, existing_value);
    }
    else
    {
        printf("No existing value found at key %u (this is normal for first update)\n", key);
    }

    // Update the map with socket fd using __u32 types
    if (bpf_map_update_elem(map_fd, &key, &value, BPF_ANY) < 0)
    {
        perror("bpf_map_update_elem");
        close(map_fd);
        return -1;
    }

    printf("Updated pinned mig_servers map at key %u with socket fd: %u\n",
           key, value);
    close(map_fd);
    return 0;
}

int create_tcp_server(int key_index)
{
    int server_fd, opt = 1;
    struct sockaddr_in address;
    int bpf_prog_fd;
    const char *pin_path = "/sys/fs/bpf/soselect_prog";

    // Create socket
    server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd == 0)
    {
        perror("socket failed");
        return -1;
    }

    // Set SO_REUSEADDR option (add this)
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)))
    {
        perror("setsockopt SO_REUSEADDR failed");
        close(server_fd);
        return -1;
    }
    printf("SO_REUSEADDR enabled on socket %d\n", server_fd);

    // Set SO_REUSEPORT option
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEPORT, &opt, sizeof(opt)))
    {
        perror("setsockopt SO_REUSEPORT failed");
        close(server_fd);
        return -1;
    }
    printf("SO_REUSEPORT enabled on socket %d\n", server_fd);

    // Set up address structure
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(PORT);

    // Bind socket
    if (bind(server_fd, (struct sockaddr *)&address, sizeof(address)) < 0)
    {
        perror("bind failed");
        close(server_fd);
        return -1;
    }
    printf("Socket bound to port %d\n", PORT);

    // Start listening
    if (listen(server_fd, BACKLOG) < 0)
    {
        perror("listen failed");
        close(server_fd);
        return -1;
    }
    printf("Server listening on port %d\n", PORT);

    // Try to get pinned BPF program first
    bpf_prog_fd = get_pinned_bpf_prog(pin_path);
    if (bpf_prog_fd < 0)
    {
        // If pinned program doesn't exist, load and pin it
        printf("Pinned program not found, loading from object file...\n");
        return -1;
    }

    // Attach BPF program to socket using SO_ATTACH_REUSEPORT_EBPF
    if (setsockopt(server_fd, SOL_SOCKET, SO_ATTACH_REUSEPORT_EBPF,
                   &bpf_prog_fd, sizeof(bpf_prog_fd)))
    {
        perror("setsockopt SO_ATTACH_REUSEPORT_EBPF failed");
        close(bpf_prog_fd);
        close(server_fd);
        return -1;
    }
    printf("BPF program attached to socket with SO_ATTACH_REUSEPORT_EBPF\n");
    // Add this line to close the BPF program fd after successful attachment
    close(bpf_prog_fd);
    // Update BPF map with socket fd
    if (update_bpf_map_pinned(server_fd, key_index) < 0)
    {
        fprintf(stderr, "Warning: Failed to update BPF map\n");
        // Continue anyway, as the server can still function
    }

    return server_fd;
}

void handle_client(int client_fd)
{
    char buffer[1024] = {0};
    ssize_t bytes_read;

    bytes_read = read(client_fd, buffer, sizeof(buffer) - 1);
    if (bytes_read > 0)
    {
        buffer[bytes_read] = '\0';
        printf("Received from client: %s\n", buffer);

        // Echo back to client
        const char *response = "Hello from TCP server with eBPF load balancing!\n";
        send(client_fd, response, strlen(response), 0);
    }

    close(client_fd);
}

int main(int argc, char *argv[])
{
    int server_fd, client_fd;
    struct sockaddr_in client_addr;
    socklen_t client_len = sizeof(client_addr);
    int key_index = 0;

    // Allow key index to be specified as command line argument
    if (argc > 1)
    {
        key_index = atoi(argv[1]);
    }

    printf("Starting TCP server with SO_REUSEPORT and eBPF load balancing...\n");

    // Create and configure server
    server_fd = create_tcp_server(key_index);
    if (server_fd < 0)
    {
        exit(EXIT_FAILURE);
    }

    printf("Server ready. Process ID: %d\n", getpid());
    printf("You can start multiple instances of this server for load balancing.\n");

    // Main server loop
    while (1)
    {
        client_fd = accept(server_fd, (struct sockaddr *)&client_addr, &client_len);
        if (client_fd < 0)
        {
            perror("accept failed");
            continue;
        }

        printf("Accepted connection from %s:%d\n",
               inet_ntoa(client_addr.sin_addr), ntohs(client_addr.sin_port));

        // Handle client (in a real server, you'd typically fork or use threads)
        handle_client(client_fd);
    }

    close(server_fd);
    return 0;
}