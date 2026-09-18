"""
http_parser.py
==============
A minimal HTTP/1.1 message reader for reading requests/responses off a
DECRYPTED stream (works on both raw sockets and ssl.SSLSocket objects -
they both support the same .recv() interface).

Why we need this: once we've decrypted a connection, the browser doesn't
send just ONE request and disconnect - it reuses the same connection for
MANY requests (HTTP keep-alive). To inspect each one individually (e.g.
to later spot a specific YouTube video request), we need to correctly
figure out where one message ends and the next begins - which requires
respecting Content-Length or chunked transfer-encoding, exactly like a
real HTTP client/server does.
"""


def _recv_until(sock, delimiter=b"\r\n\r\n"):
    buf = b""
    while delimiter not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            return buf, b""
        buf += chunk
    idx = buf.index(delimiter) + len(delimiter)
    return buf[:idx], buf[idx:]


def _parse_headers(header_bytes: bytes):
    lines = header_bytes.decode(errors="replace").split("\r\n")
    start_line = lines[0]
    headers = {}
    for line in lines[1:]:
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        headers[k.strip().lower()] = v.strip()
    return start_line, headers


def read_http_message(sock, leftover=b""):
    """
    Reads ONE complete HTTP message (request or response) from sock.
    `leftover` is any bytes already read from a previous call that
    belong to the NEXT message.

    Returns (raw_bytes, start_line, headers, new_leftover) or
    (None, None, None, b"") if the connection closed cleanly.
    """
    header_block, rest = leftover, b""
    if b"\r\n\r\n" not in header_block:
        more, rest = _recv_until(sock)
        header_block += more
    else:
        idx = header_block.index(b"\r\n\r\n") + 4
        rest = header_block[idx:]
        header_block = header_block[:idx]

    if not header_block:
        return None, None, None, b""

    start_line, headers = _parse_headers(header_block)

    body = b""
    content_length = headers.get("content-length")
    transfer_encoding = headers.get("transfer-encoding", "")

    if content_length is not None:
        content_length = int(content_length)
        while len(body) + len(rest) < content_length:
            body += rest
            rest = sock.recv(4096)
            if not rest:
                break
        total = body + rest
        body = total[:content_length]
        leftover_out = total[content_length:]

    elif "chunked" in transfer_encoding.lower():
        buf = rest
        while True:
            while b"\r\n" not in buf:
                more = sock.recv(4096)
                if not more:
                    break
                buf += more
            if b"\r\n" not in buf:
                break
            size_line, buf = buf.split(b"\r\n", 1)
            try:
                chunk_size = int(size_line.strip(), 16)
            except ValueError:
                break
            if chunk_size == 0:
                while len(buf) < 2:
                    more = sock.recv(4096)
                    if not more:
                        break
                    buf += more
                buf = buf[2:]
                break
            while len(buf) < chunk_size + 2:
                more = sock.recv(4096)
                if not more:
                    break
                buf += more
            body += buf[:chunk_size]
            buf = buf[chunk_size + 2:]
        leftover_out = buf
    else:
        leftover_out = rest

    return header_block + body, start_line, headers, leftover_out