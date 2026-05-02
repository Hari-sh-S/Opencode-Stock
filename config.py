"""
Dhan API Configuration
Uses official dhanhq SDK for authentication.
Supports TOTP-based access token generation via:
  POST https://auth.dhan.co/app/generateAccessToken?dhanClientId=...&pin=...&totp=...
"""

import os
import re
import requests
from pathlib import Path
from dotenv import load_dotenv, set_key, find_dotenv

# Load environment variables from .env file
load_dotenv()

# Dhan API Credentials (loaded from .env)
DHAN_CLIENT_ID   = os.getenv("DHAN_CLIENT_ID")
DHAN_PIN         = os.getenv("DHAN_PIN")           # Saved PIN (do not share)
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

# Dhan auth endpoint
DHAN_AUTH_URL = "https://auth.dhan.co/app/generateAccessToken"


# ─── Credential Persistence ───────────────────────────────────────────────────

def _get_env_file() -> str:
    """Return path to .env file (create if missing)."""
    env_path = find_dotenv()
    if not env_path:
        env_path = str(Path(".env"))
        Path(env_path).touch()
    return env_path


def save_credentials_to_env(client_id: str = None, pin: str = None, access_token: str = None):
    """
    Persist Dhan credentials to .env file.
    Only updates the fields that are provided (non-None).
    Reloads module-level globals after saving.
    """
    global DHAN_CLIENT_ID, DHAN_PIN, DHAN_ACCESS_TOKEN

    env_path = _get_env_file()

    if client_id is not None:
        set_key(env_path, "DHAN_CLIENT_ID", client_id)
        DHAN_CLIENT_ID = client_id
        os.environ["DHAN_CLIENT_ID"] = client_id

    if pin is not None:
        set_key(env_path, "DHAN_PIN", pin)
        DHAN_PIN = pin
        os.environ["DHAN_PIN"] = pin

    if access_token is not None:
        set_key(env_path, "DHAN_ACCESS_TOKEN", access_token)
        DHAN_ACCESS_TOKEN = access_token
        os.environ["DHAN_ACCESS_TOKEN"] = access_token


def get_saved_credentials() -> dict:
    """Return currently saved credentials (reload from env)."""
    load_dotenv(override=True)
    return {
        "client_id":    os.getenv("DHAN_CLIENT_ID", ""),
        "pin":          os.getenv("DHAN_PIN", ""),
        "access_token": os.getenv("DHAN_ACCESS_TOKEN", ""),
    }


# ─── TOTP Authentication ──────────────────────────────────────────────────────

def authenticate_dhan(totp: str, client_id: str = None, pin: str = None) -> dict:
    """
    Generate a new Dhan access token using TOTP.

    Calls:
        POST https://auth.dhan.co/app/generateAccessToken
             ?dhanClientId=<id>&pin=<pin>&totp=<totp>

    Args:
        totp:       6-digit TOTP from your authenticator app
        client_id:  Override CLIENT_ID (uses saved value if None)
        pin:        Override PIN (uses saved value if None)

    Returns:
        dict with keys: 'success' (bool), 'access_token' (str), 'message' (str)
    """
    creds = get_saved_credentials()
    cid = client_id or creds.get("client_id") or DHAN_CLIENT_ID
    p   = pin        or creds.get("pin")       or DHAN_PIN

    if not cid:
        return {"success": False, "access_token": "", "message": "CLIENT_ID not set. Enter it above and click Save."}
    if not p:
        return {"success": False, "access_token": "", "message": "PIN not set. Enter it above and click Save."}
    if not totp or len(totp.strip()) != 6 or not totp.strip().isdigit():
        return {"success": False, "access_token": "", "message": "TOTP must be exactly 6 digits."}

    try:
        resp = requests.post(
            DHAN_AUTH_URL,
            params={
                "dhanClientId": cid.strip(),
                "pin":          p.strip(),
                "totp":         totp.strip(),
            },
            timeout=15,
        )

        if resp.status_code == 200:
            data = resp.json()
            # Response may contain 'accessToken' or 'access_token'
            token = (
                data.get("accessToken")
                or data.get("access_token")
                or data.get("data", {}).get("accessToken")
                or data.get("data", {}).get("access_token")
            )
            if token:
                save_credentials_to_env(access_token=token)
                return {
                    "success":      True,
                    "access_token": token,
                    "message":      f"✅ Authenticated successfully! Token saved to .env ({len(token)} chars).",
                }
            else:
                return {
                    "success":      False,
                    "access_token": "",
                    "message":      f"Auth response OK but no token found. Response: {str(data)[:300]}",
                }
        else:
            return {
                "success":      False,
                "access_token": "",
                "message":      f"HTTP {resp.status_code}: {resp.text[:300]}",
            }

    except requests.exceptions.Timeout:
        return {"success": False, "access_token": "", "message": "Request timed out. Check your internet connection."}
    except Exception as e:
        return {"success": False, "access_token": "", "message": f"Error: {e}"}


# ─── Validate & Client ────────────────────────────────────────────────────────

def validate_credentials():
    """Check if credentials are configured."""
    creds = get_saved_credentials()
    cid   = creds.get("client_id") or DHAN_CLIENT_ID
    token = creds.get("access_token") or DHAN_ACCESS_TOKEN

    if not cid or cid == "your_client_id_here":
        raise ValueError("DHAN_CLIENT_ID not configured. Use the Dhan Auth tab to set credentials.")
    if not token or token == "your_access_token_here":
        raise ValueError("DHAN_ACCESS_TOKEN not configured. Use the Dhan Auth tab to authenticate.")
    return True


def get_dhan_client():
    """Get authenticated Dhan client using official SDK.

    Handles different SDK versions:
    - Older versions: use DhanContext + dhanhq(context)
    - Newer versions: use dhanhq(client_id, access_token) directly
    """
    validate_credentials()
    creds = get_saved_credentials()
    cid   = creds.get("client_id")   or DHAN_CLIENT_ID
    token = creds.get("access_token") or DHAN_ACCESS_TOKEN

    try:
        from dhanhq import dhanhq
        import inspect
        sig    = inspect.signature(dhanhq.__init__)
        params = list(sig.parameters.keys())

        if 'dhan_context' in params:
            from dhanhq import DhanContext
            context = DhanContext(cid, token)
            return dhanhq(context)
        else:
            return dhanhq(cid, token)
    except Exception:
        try:
            from dhanhq import DhanContext, dhanhq
            context = DhanContext(cid, token)
            return dhanhq(context)
        except Exception:
            from dhanhq import dhanhq
            return dhanhq(cid, token)
