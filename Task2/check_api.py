import base64
import hashlib
import html
import http.cookiejar
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

KC = "http://localhost:8080/realms/reports-realm/protocol/openid-connect"
API = "http://localhost:8000"
REDIRECT = "http://localhost:3000/"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def get_token(username, password):
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect)
    verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    query = urllib.parse.urlencode({
        "client_id": "reports-frontend", "response_type": "code", "scope": "openid",
        "redirect_uri": REDIRECT, "code_challenge": challenge, "code_challenge_method": "S256",
    })
    page = opener.open(f"{KC}/auth?{query}").read().decode()
    action = html.unescape(re.search(r'action="([^"]+)"', page).group(1))
    data = urllib.parse.urlencode({"username": username, "password": password}).encode()
    try:
        opener.open(urllib.request.Request(action, data=data))
        raise RuntimeError("нет редиректа после входа")
    except urllib.error.HTTPError as e:
        location = e.headers["Location"]
    code = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)["code"][0]
    body = urllib.parse.urlencode({
        "client_id": "reports-frontend", "grant_type": "authorization_code", "code": code,
        "redirect_uri": REDIRECT, "code_verifier": verifier,
    }).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request(f"{KC}/token", data=body)))["access_token"]


def call(token, query=""):
    req = urllib.request.Request(f"{API}/reports{query}")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def summary(result):
    status, body = result
    if status != 200:
        return f"{status} {body}"
    days = body["days"]
    return f"{status} user={body['username']} дней={len(days)} processed_through={body['processed_through']} имя={days[0]['full_name'] if days else '-'}"


if __name__ == "__main__":
    print("без токена:", summary(call(None)))
    print("мусорный токен:", summary(call("abc.def.ghi")))
    t1 = get_token("prothetic1", "prothetic123")
    t2 = get_token("prothetic2", "prothetic123")
    print("prothetic1:", summary(call(t1, "?date_from=2026-11-01&date_to=2026-11-30")))
    print("prothetic2:", summary(call(t2, "?date_from=2026-11-01&date_to=2026-11-30")))
    tu = get_token("user1", "password123")
    print("user1 (без роли):", summary(call(tu)))
    sys.exit(0)
