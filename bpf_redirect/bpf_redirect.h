#ifndef __BPF_REDIRECT_H
#define __BPF_REDIRECT_H

#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

#define SERVER_PORT 9999
#define PROXY_PORT 8888

struct {
    __uint(type, BPF_MAP_TYPE_SOCKMAP);
    __uint(max_entries, 32);
    __type(key, __u32);
    __type(value, __u32); // socket FD
    __uint(pinning, LIBBPF_PIN_BY_NAME);
} sockmap SEC(".maps");

#endif /* __BPF_REDIRECT_H */