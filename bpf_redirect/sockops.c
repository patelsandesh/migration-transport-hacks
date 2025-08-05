#include "bpf_redirect.h"

SEC("sockops")
int sockops_prog(struct bpf_sock_ops *skops) {
    bpf_printk("proxy program loaded \n");
    switch (skops->op) {
    case BPF_SOCK_OPS_PASSIVE_ESTABLISHED_CB: // SYN-ACK
        if (skops->local_port == PROXY_PORT) {
            __u32 key = PROXY_PORT;
            bpf_printk("setup proxy port %d\n", PROXY_PORT);
            bpf_sock_map_update(skops, &sockmap, &key, BPF_ANY);
        }
        break;
    case BPF_SOCK_OPS_ACTIVE_ESTABLISHED_CB: // SYN
        if (bpf_ntohl(skops->remote_port) == SERVER_PORT) {
            __u32 key = SERVER_PORT;
            bpf_printk("setup server port %d\n", SERVER_PORT);
            bpf_sock_map_update(skops, &sockmap, &key, BPF_ANY);
        }
        break;
    }

    return 0;
}

char _license[] SEC("license") = "GPL";