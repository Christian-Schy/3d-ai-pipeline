"""Run once to get your Bambu Lab access token and save it to config/bambu.json.

Usage:  uv run get_bambu_token.py
"""
import getpass, json, pathlib, sys
import urllib.request, urllib.error

LOGIN_URL = "https://api.bambulab.com/v1/user-service/user/login"
CONFIG_PATH = pathlib.Path("config/bambu.json")


_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "bambu_network_agent/01.09.07.00",
    "App-Language": "en",
    "App-Version": "01.09.07.00",
    "App-Os": "linux",
    "Accept": "application/json",
}


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=_HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def main():
    print("=== Bambu Lab Token Setup ===\n")
    email = input("E-Mail: ").strip()
    password = getpass.getpass("Passwort: ")

    print("\n→ Anmelden …")
    try:
        resp = post_json(LOGIN_URL, {"account": email, "password": password})
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP {e.code}: {body}")
        sys.exit(1)

    # Bambu may require a verification code (2-FA / email code)
    if resp.get("loginType") == "verifyCode" or not resp.get("token"):
        print("→ 2-FA aktiv — bitte den Code aus deiner E-Mail eingeben:")
        code = input("Verification code: ").strip()
        resp = post_json(LOGIN_URL, {"account": email, "password": password, "code": code})

    token = resp.get("token") or resp.get("accessToken")
    if not token:
        print(f"Fehler: kein Token in Antwort: {resp}")
        sys.exit(1)

    # Fetch user ID from profile endpoint
    user_id = ""
    try:
        profile_req = urllib.request.Request(
            "https://api.bambulab.com/v1/user-service/my/profile",
            headers={**_HEADERS, "Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(profile_req, timeout=10) as r:
            profile = json.loads(r.read())
        user_id = str(profile.get("uidStr") or profile.get("uid", ""))
        print(f"   Benutzer: {profile.get('name', '')} ({profile.get('account', '')})")
    except Exception as e:
        print(f"⚠ User-ID konnte nicht geladen werden: {e}")

    CONFIG_PATH.parent.mkdir(exist_ok=True)
    config = {
        "token": token,
        "user_id": user_id,
        "serial": "01P00C542401440",
        "region": "us",   # change to "cn" if you're in China
    }

    # Keep existing values if already present
    if CONFIG_PATH.exists():
        existing = json.loads(CONFIG_PATH.read_text())
        existing.update(config)
        config = existing

    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    print(f"\n✅ Token gespeichert in {CONFIG_PATH}")
    print(f"   User-ID : {user_id or '(nicht erkannt)'}")
    print(f"   Serial  : {config['serial']}")


if __name__ == "__main__":
    main()
