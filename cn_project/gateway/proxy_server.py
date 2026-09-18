"""
proxy_server.py
================
StudyFocus proxy - the opposite security model from our earlier blocklist
project: ALLOWLIST-based. Only domains explicitly approved for the active
age profile are permitted; everything else is blocked by default.

Also tracks TIME (not just bytes) spent on each allowed domain, since
that's what actually matters for a focus app - "how many minutes did I
spend on GeeksforGeeks today", not "how many bytes did I download".

No TLS interception here - domain-level blind tunneling is enough for
allow/deny decisions, which keeps this simple and stable (no certificate
trust issues, unlike our earlier MITM experiment).
"""

import socket
import threading
import time
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from allowlist_config import get_allowed_domains, AGE_PROFILES

PROXY_PORT = 8888
MANAGEMENT_PORT = 8889
SESSION_START = time.time()

# --- Active configuration (changeable via /set-profile, see below) -----
current_age_profile = "13-18"
allowed_domains = get_allowed_domains(current_age_profile)

# --- Time tracking --------------------------------------------------------
# usage[ip][site] = seconds spent today (reset at midnight - see reset_if_new_day)
# "site" here means the CANONICAL allowlist domain (e.g. "google.com"), not
# the raw hostname - this fixes a real bug where one visit to Google was
# fragmenting into a dozen near-zero entries (www.google.com,
# encrypted-tbn0.gstatic.com, ogads-pa.clients6.google.com, ...) instead of
# being counted as one meaningful total under "google.com".
usage_lock = threading.Lock()
usage = {}
last_reset_date = time.strftime("%Y-%m-%d")

# last_activity[ip][site] = timestamp of the most recent request to that site.
# Used to merge rapid-fire requests (page loading its images/scripts, or
# repeated searches seconds apart) into ONE continuous session instead of
# counting each request as a separate, tiny, disconnected visit.
last_activity = {}
SESSION_GAP_SECONDS = 120   # requests within 2 min of each other = still "using the site"
ASSUMED_VIEW_SECONDS = 5    # credited time for a single page hit with no recent prior activity

DAILY_LIMIT_SECONDS = None  # None = no cap on total daily study time


def reset_if_new_day():
    global last_reset_date, usage, last_activity
    today = time.strftime("%Y-%m-%d")
    with usage_lock:
        if today != last_reset_date:
            usage.clear()
            last_activity.clear()
            last_reset_date = today


def canonical_site(host: str) -> str:
    """Maps a raw hostname to the allowlist domain it matched, so
    subdomains/CDNs of the same site are grouped together."""
    host = host.lower()
    for domain in allowed_domains:
        if domain in host:
            return domain
    return host


def is_allowed(host: str) -> bool:
    host = host.lower()
    return any(domain in host for domain in allowed_domains)


def add_time(ip: str, site: str, seconds: float):
    reset_if_new_day()
    with usage_lock:
        usage.setdefault(ip, {})
        usage[ip][site] = usage[ip].get(site, 0) + seconds


def bridge_gap_if_recent(ip: str, site: str):
    """If there was recent activity on this site, credit the GAP since then
    as time spent - the user was likely still reading/using the page even
    though no new request happened in that window. Without this, only the
    duration of each individual connection gets counted, which massively
    undercounts real HTTPS browsing (browsers open many short-lived
    connections per page, with idle gaps between them while you read)."""
    now = time.time()
    with usage_lock:
        last_activity.setdefault(ip, {})
        last_seen = last_activity[ip].get(site)
    if last_seen is not None and (now - last_seen) < SESSION_GAP_SECONDS:
        add_time(ip, site, now - last_seen)


def mark_activity(ip: str, site: str):
    with usage_lock:
        last_activity.setdefault(ip, {})
        last_activity[ip][site] = time.time()


def record_activity(ip: str, site: str):
    """Call this for every plain HTTP request. Merges rapid successive
    requests to the same site into one continuous session instead of
    recording each one as a separate tiny slice."""
    bridge_gap_if_recent(ip, site)
    with usage_lock:
        had_prior = site in last_activity.get(ip, {})
    if not had_prior:
        add_time(ip, site, ASSUMED_VIEW_SECONDS)
    mark_activity(ip, site)


def get_domain_usage_today(ip: str, site: str) -> float:
    reset_if_new_day()
    with usage_lock:
        return usage.get(ip, {}).get(site, 0)


def is_over_site_limit(ip: str, host: str) -> bool:
    site = canonical_site(host)
    limit = allowed_domains.get(site)  # None = unlimited for the active profile
    if limit is None:
        return False
    return get_domain_usage_today(ip, site) >= limit


def log(decision: str, host: str, reason: str = ""):
    suffix = f"   ({reason})" if reason else ""
    print(f"[proxy] {decision:<8} {host}{suffix}")


BLOCKED_PAGE = b"""HTTP/1.1 403 Forbidden\r
Content-Type: text/html\r
Connection: close\r
\r
<html><body style="font-family:sans-serif;text-align:center;padding:60px">
<h1>Focus Mode Active</h1>
<p>This site isn't on your study allowlist right now.</p>
</body></html>"""

TIME_LIMIT_PAGE = b"""HTTP/1.1 403 Forbidden\r
Content-Type: text/html\r
Connection: close\r
\r
<html><body style="font-family:sans-serif;text-align:center;padding:60px">
<h1>Time Limit Reached</h1>
<p>You've used up today's time budget for this site.</p>
</body></html>"""


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def handle_generic(self):
        client_ip = self.client_address[0]
        parsed = urlparse(self.path)
        host = parsed.hostname or self.headers.get("Host", "").split(":")[0]

        if not is_allowed(host):
            log("BLOCKED", host, "not on allowlist")
            self.wfile.write(BLOCKED_PAGE)
            self.close_connection = True
            return

        if is_over_site_limit(client_ip, host):
            log("BLOCKED", host, "time limit reached")
            self.wfile.write(TIME_LIMIT_PAGE)
            self.close_connection = True
            return

        try:
            port = parsed.port or 80
            target_path = parsed.path or "/"
            if parsed.query:
                target_path += "?" + parsed.query

            start = time.time()
            with socket.create_connection((host, port), timeout=5) as upstream:
                request_line = f"{self.command} {target_path} HTTP/1.1\r\n"
                headers = f"Host: {host}\r\nConnection: close\r\n"
                for k, v in self.headers.items():
                    if k.lower() not in ("host", "connection", "proxy-connection"):
                        headers += f"{k}: {v}\r\n"
                upstream.sendall((request_line + headers + "\r\n").encode())

                response = b""
                while True:
                    chunk = upstream.recv(4096)
                    if not chunk:
                        break
                    response += chunk

                site = canonical_site(host)
                record_activity(client_ip, site)
                log("ALLOWED", host, f"tracked under '{site}'")
                self.wfile.write(response)

        except Exception as e:
            log("ERROR", host, str(e))
            self.send_error(502, "Bad Gateway")

    def do_GET(self):
        self.handle_generic()

    def do_POST(self):
        self.handle_generic()

    def do_CONNECT(self):
        client_ip = self.client_address[0]
        host, _, port = self.path.partition(":")
        port = int(port) if port else 443

        if not is_allowed(host):
            log("BLOCKED", host, "not on allowlist, HTTPS")
            self.send_response(403, "Forbidden - not on allowlist")
            self.end_headers()
            return

        if is_over_site_limit(client_ip, host):
            log("BLOCKED", host, "time limit reached, HTTPS")
            self.send_response(403, "Forbidden - time limit reached")
            self.end_headers()
            return

        try:
            upstream = socket.create_connection((host, port), timeout=5)
        except Exception as e:
            log("ERROR", host, str(e))
            self.send_error(502, "Bad Gateway")
            return

        self.send_response(200, "Connection Established")
        self.end_headers()
        log("ALLOWED", host, "HTTPS tunnel")

        site = canonical_site(host)
        bridge_gap_if_recent(client_ip, site)  # credit idle time since last activity, before this tunnel opens

        self.close_connection = True
        self._relay(self.connection, upstream, client_ip, host)

    def _relay(self, client_sock, upstream_sock, client_ip, host):
        start = time.time()

        def forward(src, dst):
            try:
                while True:
                    data = src.recv(4096)
                    if not data:
                        break
                    dst.sendall(data)
            except Exception:
                pass

        t1 = threading.Thread(target=forward, args=(client_sock, upstream_sock))
        t2 = threading.Thread(target=forward, args=(upstream_sock, client_sock))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        upstream_sock.close()

        elapsed = time.time() - start
        site = canonical_site(host)
        add_time(client_ip, site, elapsed)
        mark_activity(client_ip, site)


class ManagementHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        global current_age_profile, allowed_domains
        parsed = urlparse(self.path)

        if parsed.path == "/status.json":
            reset_if_new_day()
            with usage_lock:
                client_ip = self.client_address[0]
                sites = usage.get(client_ip, {})
                site_list = [
                    {"domain": d, "minutes": round(s / 60, 2)}
                    for d, s in sorted(sites.items(), key=lambda x: -x[1])
                ]
                total_minutes = round(sum(sites.values()) / 60, 2)
            payload = {
                "age_profile": current_age_profile,
                "age_profile_label": AGE_PROFILES[current_age_profile]["label"],
                "allowed_domains": sorted(allowed_domains.keys()),
                "allowed_domains_with_limits": [
                    {"domain": d, "limit_seconds": allowed_domains[d]}
                    for d in sorted(allowed_domains.keys())
                ],
                "available_profiles": {k: v["label"] for k, v in AGE_PROFILES.items()},
                "sites": site_list,
                "total_minutes": total_minutes,
                "session_uptime_minutes": round((time.time() - SESSION_START) / 60, 1),
            }
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        elif parsed.path == "/status":
            reset_if_new_day()
            with usage_lock:
                lines = [f"Age profile: {current_age_profile} ({AGE_PROFILES[current_age_profile]['label']})",
                         f"Allowed domains: {sorted(allowed_domains)}", ""]
                for ip, sites in usage.items():
                    lines.append(f"{ip}:")
                    total = 0
                    for domain, seconds in sorted(sites.items(), key=lambda x: -x[1]):
                        mins = seconds / 60
                        total += seconds
                        lines.append(f"  {domain}: {mins:.1f} min")
                    lines.append(f"  TOTAL: {total/60:.1f} min")
            body = "\n".join(lines).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(body)

        elif parsed.path == "/set-profile":
            from urllib.parse import parse_qs
            qs = parse_qs(parsed.query)
            profile = qs.get("profile", [None])[0]
            if profile in AGE_PROFILES:
                current_age_profile = profile
                allowed_domains = get_allowed_domains(profile)
                print(f"[admin] Age profile switched to {profile}")
                body = f"Switched to {profile}".encode()
            else:
                body = f"Invalid profile. Choose from: {list(AGE_PROFILES.keys())}".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


def run():
    proxy_server = ThreadingHTTPServer(("0.0.0.0", PROXY_PORT), ProxyHandler)
    mgmt_server = ThreadingHTTPServer(("0.0.0.0", MANAGEMENT_PORT), ManagementHandler)

    threading.Thread(target=mgmt_server.serve_forever, daemon=True).start()

    print(f"[proxy] StudyFocus proxy listening on 0.0.0.0:{PROXY_PORT}")
    print(f"[proxy] Management API on 0.0.0.0:{MANAGEMENT_PORT}  "
          f"(GET /status, GET /set-profile?profile=<6-12|13-18|18-25>)")
    print(f"[proxy] Active age profile: {current_age_profile} ({AGE_PROFILES[current_age_profile]['label']})")
    print(f"[proxy] Allowed domains: {sorted(allowed_domains)}\n")

    proxy_server.serve_forever()


if __name__ == "__main__":
    run()