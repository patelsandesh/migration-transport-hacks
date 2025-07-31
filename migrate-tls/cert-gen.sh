#!/bin/bash
# filepath: /Users/sandesh.patel/dev/crypto/migrate/migrate-tls/generate_certs.sh

set -e  # Exit on any error

# Configuration
CERT_DIR="."
CA_KEY="x509-ca-key.pem"
CA_CERT="x509-ca.pem"
SERVER_KEY="x509-server-key.pem"
SERVER_CERT="x509-server.pem"
SERVER_CSR="x509-server.csr"

# Certificate validity period (in days)
VALIDITY_DAYS=365

# Certificate subject information
CA_SUBJECT="/C=US/ST=CA/L=San Francisco/O=Test CA/CN=Test CA"
SERVER_SUBJECT="/C=US/ST=CA/L=San Francisco/O=Test Server/CN=localhost"

echo "Generating certificates and keys for TLS server..."

# Clean up existing certificates
echo "Cleaning up existing certificates..."
rm -f $CA_KEY $CA_CERT $SERVER_KEY $SERVER_CERT $SERVER_CSR

# Generate CA private key
echo "Generating CA private key..."
openssl genrsa -out $CA_KEY 4096

# Generate CA certificate
echo "Generating CA certificate..."
openssl req -new -x509 -days $VALIDITY_DAYS -key $CA_KEY -out $CA_CERT \
    -subj "$CA_SUBJECT"

# Generate server private key
echo "Generating server private key..."
openssl genrsa -out $SERVER_KEY 4096

# Generate server certificate signing request
echo "Generating server certificate signing request..."
openssl req -new -key $SERVER_KEY -out $SERVER_CSR \
    -subj "$SERVER_SUBJECT"

# Create extensions file for server certificate
cat > server_extensions.conf << EOF
[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = *.localhost
IP.1 = 127.0.0.1
IP.2 = ::1
EOF

# Generate server certificate signed by CA
echo "Generating server certificate signed by CA..."
openssl x509 -req -in $SERVER_CSR -CA $CA_CERT -CAkey $CA_KEY \
    -CAcreateserial -out $SERVER_CERT -days $VALIDITY_DAYS \
    -extensions v3_req -extfile server_extensions.conf

# Clean up temporary files
rm -f $SERVER_CSR server_extensions.conf x509-ca.srl

# Set appropriate permissions
chmod 600 $CA_KEY $SERVER_KEY
chmod 644 $CA_CERT $SERVER_CERT

echo "Certificate generation completed!"
echo ""
echo "Generated files:"
echo "  CA Certificate: $CA_CERT"
echo "  CA Private Key: $CA_KEY"
echo "  Server Certificate: $SERVER_CERT"
echo "  Server Private Key: $SERVER_KEY"
echo ""
echo "Certificate information:"
echo "========================"
echo "CA Certificate:"
openssl x509 -in $CA_CERT -text -noout | grep -E "(Subject:|Not Before|Not After)"
echo ""
echo "Server Certificate:"
openssl x509 -in $SERVER_CERT -text -noout | grep -E "(Subject:|Issuer:|Not Before|Not After|DNS:|IP Address:)"
echo ""
echo "To verify the server certificate against the CA:"
echo "openssl verify -CAfile $CA_CERT $SERVER_CERT"
echo ""
echo "Verification result:"
openssl verify -CAfile $CA_CERT $SERVER_CERT