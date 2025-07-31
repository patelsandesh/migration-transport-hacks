/* This example code is placed in the public domain. */

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/un.h>
#include <string.h>
#include <unistd.h>
#include <gnutls/gnutls.h>
#include <assert.h>

#define KEYFILE "x509-server-key.pem"
#define CERTFILE "x509-server.pem"
#define CAFILE "x509-ca.pem"
// #define CRLFILE "crl.pem"

#define CHECK(x) assert((x) >= 0)
#define LOOP_CHECK(rval, cmd) \
	do {                  \
		rval = cmd;   \
	} while (rval == GNUTLS_E_AGAIN || rval == GNUTLS_E_INTERRUPTED)

/* The OCSP status file contains up to date information about revocation
 * of the server's certificate. That can be periodically be updated
 * using:
 * $ ocsptool --ask --load-cert your_cert.pem --load-issuer your_issuer.pem
 *            --load-signer your_issuer.pem --outfile ocsp-status.der
 */
#define OCSP_STATUS_FILE "ocsp-status.der"

/* This is a sample TLS 1.0 echo server, using X.509 authentication and
 * OCSP stapling support.
 */

// #define MAX_BUF 1024
#define PORT 5556 /* listen to 5556 port */
#define MAX_BLOCK_SIZE (8*1024*1024)
#define BUFFERSIZE 17179869184


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

int main(void)
{
	int listen_sd;
	int sd, ret;
	gnutls_certificate_credentials_t x509_cred;
	gnutls_priority_t priority_cache;
	struct sockaddr_in sa_serv;
	struct sockaddr_in sa_cli;
	socklen_t client_len;
	char topbuf[512];
	gnutls_session_t session;
	char *buffer;
	int optval = 1;

	buffer = malloc(2*MAX_BLOCK_SIZE);
	/* for backwards compatibility with gnutls < 3.3.0 */
	CHECK(gnutls_global_init());

	CHECK(gnutls_certificate_allocate_credentials(&x509_cred));

	CHECK(gnutls_certificate_set_x509_trust_file(x509_cred, CAFILE,
						     GNUTLS_X509_FMT_PEM));

	// CHECK(gnutls_certificate_set_x509_crl_file(x509_cred, CRLFILE,
	// 					   GNUTLS_X509_FMT_PEM));

	/* The following code sets the certificate key pair as well as, 
	 * an OCSP response which corresponds to it. It is possible
	 * to set multiple key-pairs and multiple OCSP status responses
	 * (the latter since 3.5.6). See the manual pages of the individual
	 * functions for more information.
	 */
	CHECK(gnutls_certificate_set_x509_key_file(x509_cred, CERTFILE, KEYFILE,
						   GNUTLS_X509_FMT_PEM));

	// CHECK(gnutls_certificate_set_ocsp_status_request_file(
	// 	x509_cred, OCSP_STATUS_FILE, 0));

	CHECK(gnutls_priority_init(&priority_cache, NULL, NULL));

	/* Instead of the default options as shown above one could specify
	 * additional options such as server precedence in ciphersuite selection
	 * as follows:
	 * gnutls_priority_init2(&priority_cache,
	 *                       "%SERVER_PRECEDENCE",
	 *                       NULL, GNUTLS_PRIORITY_INIT_DEF_APPEND);
	 */

#if GNUTLS_VERSION_NUMBER >= 0x030506
	/* only available since GnuTLS 3.5.6, on previous versions see
	 * gnutls_certificate_set_dh_params(). */
	gnutls_certificate_set_known_dh_params(x509_cred,
					       GNUTLS_SEC_PARAM_MEDIUM);
#endif

	/* Socket operations
	 */
	listen_sd = socket(AF_INET, SOCK_STREAM, 0);

	memset(&sa_serv, '\0', sizeof(sa_serv));
	sa_serv.sin_family = AF_INET;
	sa_serv.sin_addr.s_addr = INADDR_ANY;
	sa_serv.sin_port = htons(PORT); /* Server Port number */

	setsockopt(listen_sd, SOL_SOCKET, SO_REUSEADDR, (void *)&optval,
		   sizeof(int));

	bind(listen_sd, (struct sockaddr *)&sa_serv, sizeof(sa_serv));

	listen(listen_sd, 1024);

	printf("Server ready. Listening to port '%d'.\n\n", PORT);

	client_len = sizeof(sa_cli);
	for (;;) {
		CHECK(gnutls_init(&session, GNUTLS_SERVER));
		// CHECK(gnutls_priority_set(session, priority_cache));
		CHECK(gnutls_priority_set_direct(session, "NORMAL:+ECDHE-RSA:+AES-256-GCM", NULL));
		CHECK(gnutls_credentials_set(session, GNUTLS_CRD_CERTIFICATE,
					     x509_cred));

		/* We don't request any certificate from the client.
		 * If we did we would need to verify it. One way of
		 * doing that is shown in the "Verifying a certificate"
		 * example.
		 */
		gnutls_certificate_server_set_request(session,
						      GNUTLS_CERT_IGNORE);
		gnutls_handshake_set_timeout(session,
					     GNUTLS_DEFAULT_HANDSHAKE_TIMEOUT);

		sd = accept(listen_sd, (struct sockaddr *)&sa_cli, &client_len);

		printf("- connection from %s, port %d\n",
		       inet_ntop(AF_INET, &sa_cli.sin_addr, topbuf,
				 sizeof(topbuf)),
		       ntohs(sa_cli.sin_port));

		gnutls_transport_set_int(session, sd);

		LOOP_CHECK(ret, gnutls_handshake(session));
		if (ret < 0) {
			close(sd);
			gnutls_deinit(session);
			fprintf(stderr, "*** Handshake has failed (%s)\n\n",
				gnutls_strerror(ret));
			continue;
		}
		printf("- Handshake was completed\n");

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
        break;
		printf("\n");
		/* do not wait for the peer to close the connection.
		 */
		LOOP_CHECK(ret, gnutls_bye(session, GNUTLS_SHUT_WR));

		close(sd);
		gnutls_deinit(session);
	}
	close(listen_sd);

	gnutls_certificate_free_credentials(x509_cred);
	gnutls_priority_deinit(priority_cache);

	gnutls_global_deinit();

	return 0;
}
