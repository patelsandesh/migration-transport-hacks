CLANG ?= clang
LLC ?= llc
ARCH := $(shell uname -m | sed 's/x86_64/x86/' | sed 's/aarch64/arm64/')

BPF_CFLAGS = -target bpf -D__TARGET_ARCH_$(ARCH) -Wall -O2 -g

all: sockops.o sk_skb.o

%.o: %.c bpf_redirect.h
	$(CLANG) $(BPF_CFLAGS) -c $< -o $@

clean:
	rm -f *.o

.PHONY: all clean