"""
Dhan API Configuration

Supports two credential sources (in priority order):
  1. Streamlit Secrets  — st.secrets (Streamlit Cloud deployment)
  2. .env file          — python-dotenv  (local development)

Access Token lifecycle:
  - Local:            saved to .env, persists across restarts (~24h)
  - Streamlit Cloud:  saved to st.session_state + os.environ for current session.
                      Must re-authenticate after each app restart (enter TOTP once
                      per session). CLIENT_ID and PIN come from Streamlit Secrets.
"""

import os
import requests
from pathlib import Path
from dotenv import load_dotenv, set_key, find_dotenv

# Load .env for local development (no-op on Streamlit Cloud where file won't exist)
load_dotenv()

# Dhan auth endpoint
DHAN_AUTH_URL = "https://auth.dhan.co/app/generateAccessToken"

# ─── Convenience: lazy module-level vars (updated by save functions) ──────────
DHAN_CLIENT_ID    = os.getenv("DHAN_CLIENT_ID", "")
DHAN_PIN          = os.getenv("DHAN_PIN", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")


# ─── Detect Streamlit Cloud ───────────────────────────────────────────────────

def _is_streamlit_cloud() -> bool:
    """Return True when running on Streamlit Cloud (env var set by platform)."""
    return bool(
        os.getenv("STREAMLIT_SHARING_MODE")
        or os.getenv("IS_STREAMLIT_CLOUD")
        # Streamlit Cloud sets this in newer versions
        or os.getenv("HOME", "").startswith("/home/appuser")
    )


def _st_secrets_get(key: str, default: str = "") -> str:
    """Safely read a key from st.secrets (returns default if not available)."""
    try:
        import streamlit as st
        val = st.secrets.get(key, default)
        return str(val) if val else default
    except Exception:
        return default


def _st_session_get(key: str, default: str = "") -> str:
    """Safely read a key from st.session_state."""
    try:
        import streamlit as st
        return str(st.session_state.get(key, default) or default)
    except Exception:
        return default


def _st_session_set(key: str, value: str):
    """Safely write a key to st.session_state."""
    try:
        import streamlit as st
        st.session_state[key] = value
    except Exception:
        pass


# ─── Credential Resolution ────────────────────────────────────────────────────

def get_saved_credentials() -> dict:
    """
    Read Dhan credentials from the best available source.

    Priority:
      CLIENT_ID / PIN:
        1. st.secrets   (Streamlit Cloud — permanent)
        2. os.environ / .env  (local — permanent)

      ACCESS_TOKEN:
        1. st.session_state["dhan_access_token"]  (set after TOTP auth, current session)
        2. st.secrets   (if manually set in Streamlit Secrets dashboard)
        3. os.environ / .env  (local)
    """
    load_dotenv(override=False)   # Refresh .env without clobbering existing env vars

    client_id = (
        _st_secrets_get("DHAN_CLIENT_ID")
        or os.getenv("DHAN_CLIENT_ID", "")
    )
    pin = (
        _st_secrets_get("DHAN_PIN")
        or os.getenv("DHAN_PIN", "")
    )
    access_token = (
        _st_session_get("dhan_access_token")         # Current session (Streamlit Cloud)
        or _st_secrets_get("DHAN_ACCESS_TOKEN")      # Streamlit Secrets
        or os.getenv("DHAN_ACCESS_TOKEN", "")        # .env / local
    )

    return {
        "client_id":    client_id.strip(),
        "pin":          pin.strip(),
        "access_token": access_token.strip(),
    }


def bootstrap_env_from_secrets():
    """
    Copy st.secrets into os.environ at app startup.
    Call this once at the top of app.py so all modules can use os.getenv().
    Also syncs session_state token into os.environ for the current request cycle.
    """
    for key in ("DHAN_CLIENT_ID", "DHAN_PIN", "DHAN_ACCESS_TOKEN"):
        val = _st_secrets_get(key)
        if val and not os.getenv(key):
            os.environ[key] = val

    # Also pull session-state token into os.environ for current cycle
    token = _st_session_get("dhan_access_token")
    if token:
        os.environ["DHAN_ACCESS_TOKEN"] = token

    # Update module globals
    global DHAN_CLIENT_ID, DHAN_PIN, DHAN_ACCESS_TOKEN
    DHAN_CLIENT_ID    = os.getenv("DHAN_CLIENT_ID", "")
    DHAN_PIN          = os.getenv("DHAN_PIN", "")
    DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")


# ─── Credential Persistence ───────────────────────────────────────────────────

def _get_env_file() -> str:
    """Return path to .env file (create if missing)."""
    env_path = find_dotenv()
    if not env_path:
        env_path = str(Path(".env"))
        Path(env_path).touch()
    return env_path


def save_credentials_to_env(
    client_id: str = None,
    pin: str = None,
    access_token: str = None,
):
    """
    Persist credentials for the current environment:

    - Always:         writes to os.environ (in-memory, for this process)
    - Always:         writes to st.session_state (for Streamlit session)
    - Local only:     writes to .env file (survives restarts)
    - Streamlit Cloud: .env write silently skipped (no persistent filesystem)
    """
    global DHAN_CLIENT_ID, DHAN_PIN, DHAN_ACCESS_TOKEN

    updates = {
        k: v for k, v in [
            ("DHAN_CLIENT_ID",    client_id),
            ("DHAN_PIN",          pin),
            ("DHAN_ACCESS_TOKEN", access_token),
        ] if v is not None
    }

    for env_key, value in updates.items():
        os.environ[env_key] = value

    # Session state (all environments)
    if access_token is not None:
        _st_session_set("dhan_access_token", access_token)
    if client_id is not None:
        _st_session_set("dhan_client_id_display", client_id)

    # .env file (local only — skip on Streamlit Cloud)
    try:
        env_path = _get_env_file()
        for env_key, value in updates.items():
            set_key(env_path, env_key, value)
    except Exception:
        pass   # Silently skip on read-only filesystems (Streamlit Cloud)

    # Refresh module globals
    DHAN_CLIENT_ID    = os.getenv("DHAN_CLIENT_ID", "")
    DHAN_PIN          = os.getenv("DHAN_PIN", "")
    DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")


def get_saved_credentials_display() -> dict:
    """Return credentials with PIN masked for display."""
    c = get_saved_credentials()
    pin = c.get("pin", "")
    c["pin_masked"] = "*" * len(pin) if pin else ""
    return c


# ─── TOTP Authentication ──────────────────────────────────────────────────────

def authenticate_dhan(totp: str, client_id: str = None, pin: str = None) -> dict:
    """
    Generate a new Dhan access token using TOTP.

    POST https://auth.dhan.co/app/generateAccessToken
         ?dhanClientId=<id>&pin=<pin>&totp=<totp>

    On success, saves token to os.environ + st.session_state (all environments)
    and also to .env file if on local (not Streamlit Cloud).

    Returns:
        dict: {'success': bool, 'access_token': str, 'message': str}
    """
    creds = get_saved_credentials()
    cid   = client_id or creds.get("client_id") or os.getenv("DHAN_CLIENT_ID", "")
    p     = pin        or creds.get("pin")       or os.getenv("DHAN_PIN", "")

    if not cid:
        return {
            "success": False, "access_token": "",
            "message": "❌ Client ID not set. Add DHAN_CLIENT_ID to Streamlit Secrets or .env.",
        }
    if not p:
        return {
            "success": False, "access_token": "",
            "message": "❌ PIN not set. Add DHAN_PIN to Streamlit Secrets or .env.",
        }
    if not totp or len(totp.strip()) != 6 or not totp.strip().isdigit():
        return {
            "success": False, "access_token": "",
            "message": "❌ TOTP must be exactly 6 digits.",
        }

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
            data  = resp.json()
            token = (
                data.get("accessToken")
                or data.get("access_token")
                or (data.get("data") or {}).get("accessToken")
                or (data.get("data") or {}).get("access_token")
            )
            if token:
                save_credentials_to_env(access_token=token)
                cloud = _is_streamlit_cloud()
                note  = (
                    " Token stored in session (re-auth needed after restart)."
                    if cloud else
                    " Token saved to .env (persists until tomorrow)."
                )
                return {
                    "success":      True,
                    "access_token": token,
                    "message":      f"✅ Authenticated! {note}",
                }
            else:
                return {
                    "success": False, "access_token": "",
                    "message": f"Auth OK but no token in response: {str(data)[:300]}",
                }

        else:
            return {
                "success": False, "access_token": "",
                "message": f"HTTP {resp.status_code}: {resp.text[:300]}",
            }

    except requests.exceptions.Timeout:
        return {"success": False, "access_token": "", "message": "⏱️ Request timed out."}
    except Exception as e:
        return {"success": False, "access_token": "", "message": f"Error: {e}"}


# ─── Validate & Client ────────────────────────────────────────────────────────

def validate_credentials():
    """Raise ValueError if required credentials are missing."""
    creds = get_saved_credentials()
    if not creds.get("client_id"):
        raise ValueError(
            "DHAN_CLIENT_ID not configured.\n"
            "→ Streamlit Cloud: add to app Secrets\n"
            "→ Local: add to .env or use the 🔐 Dhan Auth tab"
        )
    if not creds.get("access_token"):
        raise ValueError(
            "DHAN_ACCESS_TOKEN not set.\n"
            "→ Go to 🔐 Dhan Auth tab and enter your TOTP to authenticate."
        )
    return True


def get_dhan_client():
    """Return an authenticated dhanhq client using best available credentials."""
    validate_credentials()
    creds = get_saved_credentials()
    cid   = creds["client_id"]
    token = creds["access_token"]

    try:
        from dhanhq import dhanhq
        import inspect
        params = list(inspect.signature(dhanhq.__init__).parameters.keys())
        if "dhan_context" in params:
            from dhanhq import DhanContext
            return dhanhq(DhanContext(cid, token))
        return dhanhq(cid, token)
    except Exception:
        try:
            from dhanhq import DhanContext, dhanhq
            return dhanhq(DhanContext(cid, token))
        except Exception:
            from dhanhq import dhanhq
            return dhanhq(cid, token)
