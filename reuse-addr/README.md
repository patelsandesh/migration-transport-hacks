# Port Reuse Experiment

This experiment demonstrates how two servers can reuse the same port while maintaining active client connections.

## Scenario

1. **S1** starts listening on port 8899
2. **C1** connects to S1
3. **S1** immediately closes its listening socket but keeps the C1 connection active
4. **S2** starts listening on the same port 8899 (now available)
5. **C2** connects to S2
6. Both C1-S1 and C2-S2 connections remain active, transferring data

## Project Structure

```
reuse-addr
├── c1.py       # Client 1 implementation
├── c2.py       # Client 2 implementation
├── s1.py       # Server 1 implementation
├── s2.py       # Server 2 implementation
└── README.md    # Project documentation
```

## Running the Experiment

### Terminal 1 - Start S1
```bash
python s1.py
```

### Terminal 2 - Start S2
```bash
python s2.py
```

### Terminal 3 - Start C1
```bash
python c1.py
```

### Terminal 4 - Start C2
```bash
python c2.py
```

## Notes

- Ensure that the specified IP address (10.117.30.218) is reachable from the machines running the clients and servers.
- Adjust firewall settings if necessary to allow communication on the specified ports.