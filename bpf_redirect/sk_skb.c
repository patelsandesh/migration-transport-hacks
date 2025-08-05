#include "bpf_redirect.h"

SEC("sk_skb/stream_verdict")
int sk_skb_stream_verdict_prog(struct __sk_buff *skb) {

    if (skb->local_port == PROXY_PORT) {
        bpf_printk("redirecting to server port %d\n", SERVER_PORT);
        return bpf_sk_redirect_map(skb, &sockmap, SERVER_PORT, 0);
    }

    if (bpf_ntohl(skb->remote_port) == SERVER_PORT) {
        bpf_printk("redirecting to proxy port %d\n", PROXY_PORT);
        return bpf_sk_redirect_map(skb, &sockmap, PROXY_PORT, 0);
    }

    return SK_PASS;
}

char _license[] SEC("license") = "GPL";