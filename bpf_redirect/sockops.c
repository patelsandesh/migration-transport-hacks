#include "bpf_redirect.h"

struct {
    __uint(type, BPF_MAP_TYPE_SOCKMAP);
    __uint(max_entries, 32);
    __type(key, __u32);
    __type(value, __u64);
    __uint(pinning, LIBBPF_PIN_BY_NAME);
} sockmap SEC(".maps");

SEC("sockops")
int sockops_prog(struct bpf_sock_ops *skops) {
    bpf_printk("proxy program loaded \n");
    __u32 err = 0;
    switch (skops->op) {
    case BPF_SOCK_OPS_PASSIVE_ESTABLISHED_CB: // SYN-ACK
        if (skops->local_port == PROXY_PORT) {
            __u32 key = 1; // this would be index in array so can not be more than map size
            bpf_printk("setup proxy port %d\n", PROXY_PORT);
            err = bpf_sock_map_update(skops, &sockmap, &key, BPF_ANY);
            if (err) {
                bpf_printk("bpf_sock_map_update failed with error %d\n", err);
            }
        } else if (skops->local_port == SERVER_PORT) {
            __u32 key = 2;
            bpf_printk("setup server port %d\n", SERVER_PORT);
            err = bpf_sock_map_update(skops, &sockmap, &key, BPF_ANY);
            if (err) {
                bpf_printk("bpf_sock_map_update failed with error %d\n", err);
            }
        }
        break;
    // case BPF_SOCK_OPS_ACTIVE_ESTABLISHED_CB: // SYN
    //     if (bpf_ntohl(skops->remote_port) == SERVER_PORT) {
    //         __u32 key = SERVER_PORT;
    //         bpf_printk("setup server port %d\n", SERVER_PORT);
    //         bpf_sock_map_update(skops, &sockmap, &key, BPF_ANY);
    //     }
    //     break;
    // }
    }
    return 0;
}

char _license[] SEC("license") = "GPL";