#!/bin/bash
set -eux

# Compile the BPF code
make

# Create a cgroup for the sock_ops program
CGROUP_PATH=/sys/fs/cgroup/bpf_proxy
sudo mkdir -p $CGROUP_PATH

# Load BPF programs and pin the map
# The map is defined in both object files. We load one, pin the map,
# then load the second program reusing the pinned map.
sudo bpftool prog load sockops.o /sys/fs/bpf/sockops_prog
sudo bpftool prog load sk_skb.o /sys/fs/bpf/sk_skb_prog map name sockmap pinned /sys/fs/bpf/sockmap

# Attach the sock_ops program to the cgroup
SOCKOPS_ID=$(sudo bpftool prog show pinned /sys/fs/bpf/sockops_prog | head -n1 | cut -d: -f1)
sudo bpftool cgroup attach $CGROUP_PATH sock_ops id $SOCKOPS_ID



# Attach the sk_skb program to the sockmap
# SK_SKB_ID=$(sudo bpftool prog show pinned /sys/fs/bpf/sk_skb_prog | head -n1 | cut -d: -f1)
# MAP_ID=$(sudo bpftool map show name sockmap | head -n1 | cut -d: -f1)
# sudo bpftool prog attach id $SK_SKB_ID sk_skb_stream_verdict id $MAP_ID

sudo bpftool prog attach pinned /sys/fs/bpf/sk_skb_prog sk_skb_stream_verdict name sockmap pinned /sys/fs/bpf/sockmap

echo "BPF programs loaded and attached."
echo "Run your proxy and server, then add their PIDs to the cgroup:"
echo "sudo sh -c 'echo \$(pgrep -f your_proxy_process) > $CGROUP_PATH/cgroup.procs'"
echo "sudo sh -c 'echo \$(pgrep -f your_server_process) > $CGROUP_PATH/cgroup.procs'"