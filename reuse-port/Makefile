CLANG ?= clang
LLC ?= llc
ARCH := $(shell uname -m | sed 's/x86_64/x86/' | sed 's/aarch64/arm64/')

BPF_CFLAGS = -target bpf -D__TARGET_ARCH_$(ARCH) -Wall -O2 -g
CC_CFLAGS = -Wall -O2 -g

all: sockselect-bpf.o tcp-server

tcp-server: tcp-server.c
	$(CC) $(CC_CFLAGS) -o $@ $< -lbpf

%.o: %.c
	$(CLANG) $(BPF_CFLAGS) -c $< -o $@

clean:
	rm -f *.o tcp-server

.PHONY: all clean