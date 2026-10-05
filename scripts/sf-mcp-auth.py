#!/usr/bin/env python3
"""
sf-mcp-auth.py — Rafraîchit le token Bearer du serveur MCP Salesforce
dans claude_desktop_config.json via OAuth PKCE (aucune copie manuelle).

Usage (depuis la racine du projet) :
    python3 scripts/sf-mcp-auth.py
"""

import http.server, webbrowser, urllib.parse, urllib.request
import json, threading, secrets, hashlib, base64, ssl, sys, shutil, os
from pathlib import Path

# ---------------------------------------------------------------------------
# Config — lue depuis .env à la racine du projet (jamais hardcodée)
# ---------------------------------------------------------------------------
def _load_env():
    env_file = Path(__file__).parent.parent / ".env"
    env = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env

_env = _load_env()

def _require(key):
    val = _env.get(key) or os.environ.get(key, "")
    if not val or val.startswith("<"):
        print(f"ERREUR : {key} non configuré — copier .env.example en .env et renseigner la valeur.")
        sys.exit(1)
    return val

CLIENT_ID    = _require("SF_CLIENT_ID")
INSTANCE_URL = _require("SF_INSTANCE_URL")
MCP_SERVER_KEY = _env.get("SF_MCP_SERVER_KEY") or os.environ.get("SF_MCP_SERVER_KEY", "salesforce-hxl-cvermcp")

REDIRECT_URI   = "http://localhost:8085/callback"
DESKTOP_CONFIG = Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"

# ---------------------------------------------------------------------------
# OAuth PKCE
# ---------------------------------------------------------------------------
def pkce_pair():
    verifier  = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def fetch_token(code, verifier):
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode    = ssl.CERT_NONE

    req = urllib.request.Request(
        f"{INSTANCE_URL}/services/oauth2/token",
        data=urllib.parse.urlencode({
            "grant_type":    "authorization_code",
            "code":          code,
            "client_id":     CLIENT_ID,
            "redirect_uri":  REDIRECT_URI,
            "code_verifier": verifier,
        }).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_ctx))
    with opener.open(req) as r:
        return json.loads(r.read())


def oauth_flow():
    verifier, challenge = pkce_pair()
    auth_code  = None
    auth_event = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in params:
                auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body><h2>OK, vous pouvez fermer cet onglet.</h2></body></html>")
                auth_event.set()
            else:
                self.send_response(400)
                self.end_headers()
        def log_message(self, *_): pass

    server = http.server.HTTPServer(("localhost", 8085), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    auth_url = f"{INSTANCE_URL}/services/oauth2/authorize?" + urllib.parse.urlencode({
        "response_type":         "code",
        "client_id":             CLIENT_ID,
        "redirect_uri":          REDIRECT_URI,
        "scope":                 "mcp_api refresh_token",
        "code_challenge":        challenge,
        "code_challenge_method": "S256",
    })
    print("Ouverture du navigateur…", flush=True)
    webbrowser.open(auth_url)
    print("En attente du callback OAuth (120s)…", flush=True)
    auth_event.wait(timeout=120)
    server.shutdown()

    if not auth_code:
        print("ERREUR : timeout — aucun code OAuth reçu.")
        sys.exit(1)

    return fetch_token(auth_code, verifier)


# ---------------------------------------------------------------------------
# Mise à jour de claude_desktop_config.json
# ---------------------------------------------------------------------------
def update_config(access_token):
    if not DESKTOP_CONFIG.exists():
        print(f"ERREUR : fichier introuvable :\n  {DESKTOP_CONFIG}")
        sys.exit(1)

    config = json.loads(DESKTOP_CONFIG.read_text(encoding="utf-8"))

    server = config.get("mcpServers", {}).get(MCP_SERVER_KEY)
    if not server:
        print(f"ERREUR : serveur «{MCP_SERVER_KEY}» introuvable dans claude_desktop_config.json")
        sys.exit(1)

    args = server.get("args", [])
    # Remplace l'argument "Authorization:Bearer <ancien token>"
    updated = False
    for i, arg in enumerate(args):
        if arg.startswith("Authorization:Bearer ") or arg.startswith("Authorization: Bearer "):
            args[i] = f"Authorization:Bearer {access_token}"
            updated = True
            break

    if not updated:
        print(f"ERREUR : argument Authorization:Bearer non trouvé dans args de «{MCP_SERVER_KEY}»")
        sys.exit(1)

    # Sauvegarde avant écrasement
    backup = DESKTOP_CONFIG.with_suffix(".json.bak")
    shutil.copy2(DESKTOP_CONFIG, backup)

    DESKTOP_CONFIG.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  ✓  claude_desktop_config.json mis à jour (backup : {backup.name})")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------
def main():
    print(f"\n=== Authentification Salesforce MCP — {INSTANCE_URL} ===\n")

    tokens = oauth_flow()
    access_token = tokens.get("access_token", "")
    if not access_token:
        print(f"ERREUR : pas d'access_token dans la réponse : {tokens}")
        sys.exit(1)

    print(f"Token obtenu (…{access_token[-8:]})\n")
    update_config(access_token)
    print("\nTerminé. Relance Claude Desktop pour que le nouveau token soit pris en compte.\n")


if __name__ == "__main__":
    main()
