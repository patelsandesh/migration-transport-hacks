/* This example code is placed in the public domain. */

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <gnutls/gnutls.h>
#include <gnutls/x509.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/un.h>

/* A very basic TLS client, with X.509 authentication and server certificate
 * verification. Note that error recovery is minimal for simplicity.
 */

#define CHECK(x) assert((x) >= 0)
#define LOOP_CHECK(rval, cmd)                                             \
	do {                                                              \
		rval = cmd;                                               \
	} while (rval == GNUTLS_E_AGAIN || rval == GNUTLS_E_INTERRUPTED); \
	assert(rval >= 0)

#define MAX_BLOCK_SIZE (32*1024)
#define BUFFERSIZE (32*1024*1024*1024UL)

#define SOCKET_PATH "/tmp/fd_socket"
#define BUFFER_SIZE 256

int send_fd(int socket_fd, int fd_to_send) {
    struct msghdr msg;
    struct iovec iov;
    char buf[1] = {'X'};  // Dummy data
    char control[CMSG_SPACE(sizeof(int))];
    struct cmsghdr *cmsg;
    
    // Initialize message structure
    memset(&msg, 0, sizeof(msg));
    memset(control, 0, sizeof(control));
    
    // Set up the data part of the message
    iov.iov_base = buf;
    iov.iov_len = sizeof(buf);
    msg.msg_iov = &iov;
    msg.msg_iovlen = 1;
    
    // Set up the control message for file descriptor passing
    msg.msg_control = control;
    msg.msg_controllen = sizeof(control);
    
    cmsg = CMSG_FIRSTHDR(&msg);
    cmsg->cmsg_level = SOL_SOCKET;
    cmsg->cmsg_type = SCM_RIGHTS;
    cmsg->cmsg_len = CMSG_LEN(sizeof(int));
    
    // Copy the file descriptor into the control message
    memcpy(CMSG_DATA(cmsg), &fd_to_send, sizeof(int));
    
    // Send the message with the file descriptor
    if (sendmsg(socket_fd, &msg, 0) == -1) {
        perror("sendmsg");
        return -1;
    }
    
    return 0;
}

int prepare_and_send_fd(int file_fd) {

    int sock_fd;
    struct sockaddr_un server_addr;
    
    // Create Unix domain socket
    sock_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sock_fd == -1) {
        perror("socket");
        close(file_fd);
        exit(EXIT_FAILURE);
    }
    
    // Set up server address
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sun_family = AF_UNIX;
    strncpy(server_addr.sun_path, SOCKET_PATH, sizeof(server_addr.sun_path) - 1);
    
    // Connect to server
    if (connect(sock_fd, (struct sockaddr *)&server_addr, sizeof(server_addr)) == -1) {
        perror("connect");
        fprintf(stderr, "Make sure the server is running and listening on %s\n", SOCKET_PATH);
        close(sock_fd);
        close(file_fd);
        exit(EXIT_FAILURE);
    }
    
    printf("Connected to server at %s\n", SOCKET_PATH);
    
    // Send the file descriptor
    if (send_fd(sock_fd, file_fd) == -1) {
        fprintf(stderr, "Failed to send file descriptor\n");
        close(sock_fd);
        close(file_fd);
        exit(EXIT_FAILURE);
    }
    
    printf("File descriptor sent successfully!\n");
    
    // Wait for acknowledgment from server (optional)
    char ack_buf[BUFFER_SIZE];
    ssize_t bytes_received = recv(sock_fd, ack_buf, sizeof(ack_buf) - 1, 0);
    if (bytes_received > 0) {
        ack_buf[bytes_received] = '\0';
        printf("Server response: %s\n", ack_buf);
    }
    
    // Clean up
    close(sock_fd);
    close(file_fd);
    
    return 0;
}

int tcp_connect(void)
{
	const char *PORT = "5556";
	const char *SERVER = "10.117.25.140";
	int err, sd;
	struct sockaddr_in sa;

	/* connects to server
	 */
	sd = socket(AF_INET, SOCK_STREAM, 0);

	memset(&sa, '\0', sizeof(sa));
	sa.sin_family = AF_INET;
	sa.sin_port = htons(atoi(PORT));
	inet_pton(AF_INET, SERVER, &sa.sin_addr);

	err = connect(sd, (struct sockaddr *)&sa, sizeof(sa));
	if (err < 0) {
		fprintf(stderr, "Connect error\n");
		exit(1);
	}

	return sd;
}

/* closes the given socket descriptor.
 */
void tcp_close(int sd)
{
	shutdown(sd, SHUT_RDWR); /* no more receptions */
	close(sd);
}


int main(void)
{
	int ret, sd, ii;
	gnutls_session_t session;
	// char buffer[MAX_BLOCK_SIZE + 1];
	char *desc;
	gnutls_datum_t out;
	int type;
	unsigned status;
	gnutls_certificate_credentials_t xcred;
	char *txbuf;
    // char *rxbuf;
	struct timespec t1;
    unsigned long start_time, end_time, total_time;

	if (gnutls_check_version("3.4.6") == NULL) {
		fprintf(stderr,
			"GnuTLS 3.4.6 or later is required for this example\n");
		exit(1);
	}

	/* for backwards compatibility with gnutls < 3.3.0 */
	CHECK(gnutls_global_init());

	/* X509 stuff */
	CHECK(gnutls_certificate_allocate_credentials(&xcred));

	/* sets the system trusted CAs for Internet PKI */
	CHECK(gnutls_certificate_set_x509_system_trust(xcred));

	/* If client holds a certificate it can be set using the following:
	 *
	 gnutls_certificate_set_x509_key_file (xcred, "cert.pem", "key.pem", 
	 GNUTLS_X509_FMT_PEM); 
	 */

	/* Initialize TLS session */
	CHECK(gnutls_init(&session, GNUTLS_CLIENT));

	CHECK(gnutls_server_name_set(session, GNUTLS_NAME_DNS,
				     "www.example.com",
				     strlen("www.example.com")));

	/* It is recommended to use the default priorities */
	// CHECK(gnutls_set_default_priority(session));
	CHECK(gnutls_priority_set_direct(session, "NORMAL:+ECDHE-RSA:+AES-256-GCM", NULL));


	/* put the x509 credentials to the current session
	 */
	CHECK(gnutls_credentials_set(session, GNUTLS_CRD_CERTIFICATE, xcred));
	// gnutls_session_set_verify_cert(session, "www.example.com", 0);

	/* connect to the peer
	 */
	sd = tcp_connect();

	gnutls_transport_set_int(session, sd);
	gnutls_handshake_set_timeout(session, GNUTLS_DEFAULT_HANDSHAKE_TIMEOUT);

	/* Perform the TLS handshake
	 */
	do {
		ret = gnutls_handshake(session);
	} while (ret < 0 && gnutls_error_is_fatal(ret) == 0);
	if (ret < 0) {
		if (ret == GNUTLS_E_CERTIFICATE_VERIFICATION_ERROR) {
			/* check certificate verification status */
			type = gnutls_certificate_type_get(session);
			status = gnutls_session_get_verify_cert_status(session);
			CHECK(gnutls_certificate_verification_status_print(
				status, type, &out, 0));
			printf("cert verify output: %s\n", out.data);
			gnutls_free(out.data);
		}
		fprintf(stderr, "*** Handshake failed: %s\n",
			gnutls_strerror(ret));
		goto end;
	} else {
		desc = gnutls_session_get_desc(session);
		printf("- Session info: %s\n", desc);
		gnutls_free(desc);
	}

	gnutls_transport_ktls_enable_flags_t ktls_flags = gnutls_transport_is_ktls_enabled(session);

	if (ktls_flags & GNUTLS_KTLS_SEND) {
		printf("KTLS is enabled for sending data.\n");
	}
	if (ktls_flags & GNUTLS_KTLS_RECV) {
		printf("KTLS is enabled for receiving data.\n");
	}
	if (ktls_flags == 0) {
		printf("KTLS is not enabled for this session.\n");
	}

    prepare_and_send_fd(sd);

end:

	tcp_close(sd);

	gnutls_deinit(session);

	gnutls_certificate_free_credentials(xcred);

	gnutls_global_deinit();

	return 0;
}
