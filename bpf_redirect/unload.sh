#!/bin/bash
set -eux

CGROUP_PATH=/sys/fs/cgroup/bpf_proxy

# Detach the sock_ops program from the cgroup
if [ -d "$CGROUP_PATH" ]; then
    echo "Detaching BPF program from cgroup $CGROUP_PATH"
    # This command can fail if no program is attached, so we ignore errors.
    sudo bpftool cgroup detach $CGROUP_PATH sock_ops &>/dev/null || true
fi

# Unpin and remove BPF programs and map
echo "Removing pinned BPF objects"
sudo rm -f /sys/fs/bpf/sockops_prog
sudo rm -f /sys/fs/bpf/sk_skb_prog
sudo rm -f /sys/fs/bpf/sockmap

# Remove the cgroup directory
if [ -d "$CGROUP_PATH" ]; then
    echo "Removing cgroup $CGROUP_PATH"
    sudo rmdir $CGROUP_PATH
fi

# Clean compiled files
make clean

echo "BPF programs detached and cleaned up."