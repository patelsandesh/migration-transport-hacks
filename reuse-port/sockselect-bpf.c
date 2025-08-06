#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>
#include <linux/in.h>
#include <linux/ip.h>
#include <linux/tcp.h>

struct
{
    __uint(type, BPF_MAP_TYPE_REUSEPORT_SOCKARRAY);
    __type(key, __u32);
    __type(value, __u32); // Changed to __u32 for socket fd
    __uint(max_entries, 128);
    __uint(pinning, LIBBPF_PIN_BY_NAME);
} mig_servers SEC(".maps");

SEC("sk_reuseport/selector")
int hot_standby_selector(struct sk_reuseport_md *reuse)
{
    int action;
    __u32 s_even = 0, s_odd = 1;

    if (reuse->ip_protocol != IPPROTO_TCP)
    {
        return SK_DROP;
    }

    void *data = reuse->data;
    void *data_end = reuse->data_end;

    struct tcphdr *tcp = data;
    if ((void *)(tcp + 1) > data_end)
        return SK_DROP;

    __u16 src_port = bpf_ntohs(tcp->source);
    bpf_printk("TCP source port: %u, %u\n", src_port, (__u16)tcp->source);

    if (src_port % 2 == 0)
    {
        // Even source port, select socket 0
        bpf_printk("Selecting socket with index: %u\n", s_even);
        if (bpf_sk_select_reuseport(reuse, &mig_servers, &s_even, 0) == 0)
        {
            action = SK_PASS;
        }
        else
        {
            return SK_DROP;
        }
    }
    else
    {
        // Odd source port, select socket 1
        bpf_printk("Selecting socket with index: %u\n", s_odd);
        if (bpf_sk_select_reuseport(reuse, &mig_servers, &s_odd, 0) == 0)
        {
            action = SK_PASS;
        }
        else
        {
            return SK_DROP;
        }
    }

    return action;
}

char _license[] SEC("license") = "GPL";