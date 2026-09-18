"""
target_https_server.py
=======================
Simulates "the real website" our MITM relay will secretly talk to.
Uses its own self-signed cert (completely unrelated to our CA) - this
represents any real HTTPS site on the internet.
"""

import ssl
import socket
import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

HOST = "127.0.0.1"
PORT = 9443


def make_selfsigned_cert():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.local")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("test.local")]), critical=False)
        .sign(key, hashes.SHA256())
    )
    with open("/tmp/target_cert.pem", "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open("/tmp/target_key.pem", "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))


def run():
    make_selfsigned_cert()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain("/tmp/target_cert.pem", "/tmp/target_key.pem")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen(5)
    print(f"[target] Real backend listening on {HOST}:{PORT} (self-signed, simulates a real site)")

    while True:
        conn, addr = sock.accept()
        try:
            tls_conn = context.wrap_socket(conn, server_side=True)
            request = tls_conn.recv(4096)
            print(f"[target] Got request:\n{request.decode(errors='replace')[:200]}")
            body = b"<html><body><h1>REAL SECRET CONTENT FROM THE ACTUAL WEBSITE</h1></body></html>"
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/html\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"Connection: close\r\n\r\n" + body
            )
            tls_conn.sendall(response)
            tls_conn.close()
        except Exception as e:
            print(f"[target] error: {e}")


if __name__ == "__main__":
    run()