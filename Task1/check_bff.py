"""Проверка BFF: вход, cookie, отчёт без токена в браузере, выход."""
import html
import http.cookiejar
import json
import re
import urllib.error
import urllib.parse
import urllib.request

BFF = "http://localhost:8001"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def login(username, password):
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect)

    def get(url, data=None):
        try:
            r = opener.open(urllib.request.Request(url, data=data))
            return r.status, None, r.read().decode()
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307):
                return e.code, urllib.parse.urljoin(url, e.headers["Location"]), ""
            raise

    _, loc, _ = get(f"{BFF}/auth/login")
    print("редирект в Keycloak:", re.search(r"code_challenge_method=\w+", loc).group(0))
    _, _, page = get(loc)
    action = html.unescape(re.search(r'action="([^"]+)"', page).group(1))
    _, loc, _ = get(action, urllib.parse.urlencode({"username": username, "password": password}).encode())
    _, loc, _ = get(loc)  # callback в BFF, ставит cookie
    print("после входа редирект на:", loc)
    return opener, jar


def call(opener, path, method="GET"):
    req = urllib.request.Request(BFF + path, method=method, data=b"" if method == "POST" else None)
    try:
        with opener.open(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


if __name__ == "__main__":
    anon = urllib.request.build_opener()
    print("без сессии /auth/me:", call(anon, "/auth/me"))
    print("без сессии /reports:", call(anon, "/reports"))
    opener, jar = login("prothetic1", "prothetic123")
    c = [c for c in jar if c.name == "bff_session"][0]
    print("cookie httpOnly:", c.has_nonstandard_attr("HttpOnly"), "| samesite:", c.get_nonstandard_attr("SameSite"))
    print("/auth/me:", call(opener, "/auth/me"))
    status, body = call(opener, "/reports?date_from=2026-11-01&date_to=2026-11-30")
    print("/reports:", status, body.get("username"), "дней:", len(body.get("days", [])), "processed_through:", body.get("processed_through"))
    status, body = call(opener, "/reports?username=prothetic2")
    print("/reports?username=prothetic2:", status, body.get("username"))
    print("выход:", call(opener, "/auth/logout", "POST"))
    print("после выхода /reports:", call(opener, "/reports"))
