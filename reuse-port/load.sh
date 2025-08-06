#!/bin/bash
# filepath: /root/qmp/reuse-port/bpftool-commands.txt

# Basic bpftool commands for this project:

# Load and pin program:
bpftool prog load sockselect-bpf.o /sys/fs/bpf/soselect_prog type sk_reuseport

# Pin map:
# bpftool map pin name mig_servers /sys/fs/bpf/mig_servers

# List programs:
# bpftool prog list

# Show specific program:
bpftool prog show pinned /sys/fs/bpf/soselect_prog

# List maps:
# bpftool map list

# Show map contents:
# bpftool map dump pinned /sys/fs/bpf/mig_servers
