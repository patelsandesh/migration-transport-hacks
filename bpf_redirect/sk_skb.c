#include "bpf_redirect.h"


struct {
    __uint(type, BPF_MAP_TYPE_SOCKMAP);
    __uint(max_entries, 32);
    __type(key, __u32);
    __type(value, __u64);
} sockmap SEC(".maps");

SEC("sk_skb/stream_verdict")
int sk_skb_stream_verdict_prog(struct __sk_buff *skb) {
    bpf_printk("redirection program loaded\n");
    if (skb->local_port == PROXY_PORT) {
        bpf_printk("redirecting to server port %d\n", SERVER_PORT);
        return bpf_sk_redirect_map(skb, &sockmap, 2, BPF_F_INGRESS);
    }

    if (skb->local_port == SERVER_PORT) {
        bpf_printk("redirecting to proxy port %d\n", PROXY_PORT);
        return bpf_sk_redirect_map(skb, &sockmap, 1, 0);
    }

    return SK_PASS;
}

char _license[] SEC("license") = "GPL";