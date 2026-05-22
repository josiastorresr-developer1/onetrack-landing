#!/usr/bin/env python3
"""
One-time OAuth authorization for Google Indexing API.
Run this locally once to generate agent/token.json with a refresh_token.
"""

import json
import os
import tempfile
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/indexing"]
HERE   = Path(__file__).parent

def main():
    client_creds_json = os.environ.get("GOOGLE_CLIENT_CREDENTIALS")
    if not client_creds_json:
        print(
            "ERROR: variable de entorno GOOGLE_CLIENT_CREDENTIALS no definida.\n"
            "Úsalo así:\n\n"
            "  GOOGLE_CLIENT_CREDENTIALS='$(cat client_secret.json)' python agent/authorize.py"
        )
        return

    # InstalledAppFlow requiere un archivo — escribimos uno temporal
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        tmp.write(client_creds_json)
        tmp_path = tmp.name

    try:
        flow = InstalledAppFlow.from_client_secrets_file(tmp_path, SCOPES)
    finally:
        os.unlink(tmp_path)

    # Opens the browser automatically; listens on localhost for the callback
    creds = flow.run_local_server(port=8080, prompt="consent", access_type="offline")

    token_data = {
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "refresh_token": creds.refresh_token,
    }

    token_file = HERE / "token.json"
    token_file.write_text(json.dumps(token_data, indent=2), encoding="utf-8")
    print(f"\n✓ Autorización completada. Token guardado en {token_file}")
    print("\nCopia el contenido de ese archivo y pégalo como el secret")
    print("GOOGLE_OAUTH_CREDENTIALS en GitHub → Settings → Secrets and variables → Actions")
    print("\nContenido del token:\n")
    print(token_file.read_text())

if __name__ == "__main__":
    main()
