#!/bin/bash
# filepath: /root/qmp/reuse-port/unload.sh

# Remove pinned program
rm /sys/fs/bpf/soselect_prog 2>/dev/null

# Remove pinned map
rm /sys/fs/bpf/mig_servers 2>/dev/null

# Show remaining programs
# bpftool prog list