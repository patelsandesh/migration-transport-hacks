#!/usr/bin/env python3

import os
import subprocess
import sys
from pathlib import Path

def run_command(cmd, check=True):
    """Run a shell command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=check)
    if result.returncode != 0 and check:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result

def generate_certificates(cert_dir="certs", server_cn="localhost", validity_days=365):
    """Generate CA, server, and client certificates."""
    
    # Create certificate directory
    cert_path = Path(cert_dir)
    cert_path.mkdir(exist_ok=True)
    
    os.chdir(cert_path)
    
    print(f"Generating certificates in {cert_path.absolute()}")
    
    # 1. Generate CA private key
    print("\n1. Generating CA private key...")
    run_command([
        "openssl", "genrsa", "-out", "ca-key.pem", "4096"
    ])
    
    # 2. Generate CA certificate
    print("\n2. Generating CA certificate...")
    run_command([
        "openssl", "req", "-new", "-x509", "-days", str(validity_days),
        "-key", "ca-key.pem", "-sha256", "-out", "ca.pem",
        "-subj", "/C=US/ST=CA/L=San Francisco/O=Migration/CN=Migration CA"
    ])
    
    # 3. Generate server private key
    print("\n3. Generating server private key...")
    run_command([
        "openssl", "genrsa", "-out", "server-key.pem", "4096"
    ])
    
    # 4. Generate server certificate signing request
    print("\n4. Generating server CSR...")
    run_command([
        "openssl", "req", "-subj", f"/C=US/ST=CA/L=San Francisco/O=Migration/CN={server_cn}",
        "-sha256", "-new", "-key", "server-key.pem", "-out", "server.csr"
    ])
    
    # 5. Create server extensions file
    print("\n5. Creating server extensions...")
    with open("server-extfile.cnf", "w") as f:
        f.write(f"subjectAltName = DNS:{server_cn},IP:127.0.0.1,IP:0.0.0.0\n")
        f.write("extendedKeyUsage = serverAuth\n")
    
    # 6. Generate server certificate signed by CA
    print("\n6. Generating server certificate...")
    run_command([
        "openssl", "x509", "-req", "-days", str(validity_days), "-sha256",
        "-in", "server.csr", "-CA", "ca.pem", "-CAkey", "ca-key.pem",
        "-out", "server-cert.pem", "-extfile", "server-extfile.cnf",
        "-CAcreateserial"
    ])
    
    # 7. Generate client private key
    print("\n7. Generating client private key...")
    run_command([
        "openssl", "genrsa", "-out", "client-key.pem", "4096"
    ])
    
    # 8. Generate client certificate signing request
    print("\n8. Generating client CSR...")
    run_command([
        "openssl", "req", "-subj", "/C=US/ST=CA/L=San Francisco/O=Migration/CN=migration-client",
        "-new", "-key", "client-key.pem", "-out", "client.csr"
    ])
    
    # 9. Create client extensions file
    print("\n9. Creating client extensions...")
    with open("client-extfile.cnf", "w") as f:
        f.write("extendedKeyUsage = clientAuth\n")
    
    # 10. Generate client certificate signed by CA
    print("\n10. Generating client certificate...")
    run_command([
        "openssl", "x509", "-req", "-days", str(validity_days), "-sha256",
        "-in", "client.csr", "-CA", "ca.pem", "-CAkey", "ca-key.pem",
        "-out", "client-cert.pem", "-extfile", "client-extfile.cnf",
        "-CAcreateserial"
    ])
    
    # 11. Clean up CSR and extension files
    print("\n11. Cleaning up temporary files...")
    for temp_file in ["server.csr", "client.csr", "server-extfile.cnf", "client-extfile.cnf"]:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    
    # 12. Set appropriate permissions
    print("\n12. Setting file permissions...")
    for key_file in ["ca-key.pem", "server-key.pem", "client-key.pem"]:
        os.chmod(key_file, 0o600)
    
    for cert_file in ["ca.pem", "server-cert.pem", "client-cert.pem"]:
        os.chmod(cert_file, 0o644)
    
    print(f"\nCertificates generated successfully in {cert_path.absolute()}")
    print("\nGenerated files:")
    print("- ca.pem (CA certificate)")
    print("- ca-key.pem (CA private key)")
    print("- server-cert.pem (Server certificate)")
    print("- server-key.pem (Server private key)")
    print("- client-cert.pem (Client certificate)")
    print("- client-key.pem (Client private key)")
    
    # Verify certificates
    print("\n13. Verifying certificates...")
    run_command([
        "openssl", "verify", "-CAfile", "ca.pem", "server-cert.pem"
    ])
    run_command([
        "openssl", "verify", "-CAfile", "ca.pem", "client-cert.pem"
    ])
    
    print("\nAll certificates verified successfully!")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate certificates for secure WebSocket migration")
    parser.add_argument("--cert-dir", default="certs", help="Directory to store certificates")
    parser.add_argument("--server-cn", default="localhost", help="Server common name")
    parser.add_argument("--validity-days", type=int, default=365, help="Certificate validity in days")
    
    args = parser.parse_args()
    
    # Check if openssl is available
    try:
        run_command(["openssl", "version"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: OpenSSL is not installed or not in PATH")
        sys.exit(1)
    
    generate_certificates(args.cert_dir, args.server_cn, args.validity_days)

if __name__ == "__main__":
    main()
