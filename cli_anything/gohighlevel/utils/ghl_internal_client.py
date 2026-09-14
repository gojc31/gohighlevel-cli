"""GoHighLevel internal API client for workflow creation.

Uses Firebase JWT auth against backend.leadconnectorhq.com.
Adapted from ghl-superspeed-v3-main/lib/engine.py (2026-03-25).

EXPERIMENTAL: Gated behind --experimental flag in CLI.
"""
from __future__ import annotations

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Optional

BASE_URL = "https://backend.leadconnectorhq.com"
FIREBASE_API_KEY = "AIzaSyB_w3vXmsI7WeQtrIOkjR6xTRVN5uOieiE"
CTX = ssl.create_default_context()

CHROME_UA = (
    "Mozilla/5.0 (Linux; Android 15; Pixel 9) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Mobile Safari/537.36"
)

# Keys to strip from GET responses before PUT (avoids validation errors)
STRIP_KEYS = frozenset([
    "_id", "id", "__v", "createdAt", "updatedAt", "companyId", "locationId",
    "companyAge", "creationSource", "originType", "deleted",
    "isTriggerBucketMigrated", "permissionMeta",
])


class TokenManager:
    """Firebase refresh token management with auto-refresh.

    Token sources (in priority order):
    1. Cached token (if < 50 minutes old)
    2. Firebase refresh token (from GHL_FIREBASE_REFRESH_TOKEN env var)
    3. Direct Firebase token (from GHL_FIREBASE_TOKEN env var)
    """

    def __init__(self):
        self._token: Optional[str] = None
        self._token_time: float = 0

    def get_token(self) -> str:
        """Get a valid backend bearer (GHL-native JWT) or Firebase token."""
        # 0. Backend bearer (GHL-native "LeadConnector" JWT) captured from the
        #    browser via Copy-as-cURL. Since ~2026-07 the workflow API rejects the
        #    Firebase id-token and requires this Authorization: Bearer token.
        bearer = self._load_backend_bearer()
        if bearer:
            return bearer

        # 1. Check if current token is still fresh (< 50 min)
        if self._token and (time.time() - self._token_time) < 3000:
            return self._token

        # 2. Try Firebase refresh token
        refresh_token = os.environ.get("GHL_FIREBASE_REFRESH_TOKEN", "").strip()
        if refresh_token:
            token = self._refresh_firebase(refresh_token)
            if token:
                self._token = token
                self._token_time = time.time()
                return token
            print(
                "Error: Firebase refresh token is set but token refresh failed.\n"
                "The refresh token may be revoked or expired.\n"
                "Get a new one from the GHL Chrome extension.",
                file=sys.stderr,
            )
            sys.exit(1)

        # 3. Try direct Firebase token from env
        token = os.environ.get("GHL_FIREBASE_TOKEN", "").strip()
        if token:
            self._token = token
            self._token_time = time.time()
            return token

        print(
            "Error: No Firebase token available for internal API.\n"
            "Set GHL_FIREBASE_REFRESH_TOKEN (preferred) or GHL_FIREBASE_TOKEN.\n"
            "Get the refresh token from the GHL Chrome extension.",
            file=sys.stderr,
        )
        sys.exit(1)

    def force_refresh(self) -> str:
        """Force token refresh (called on 401)."""
        self._token = None
        self._token_time = 0
        return self.get_token()

    def is_backend_bearer(self) -> bool:
        """True when the active token is a GHL-native bearer (Authorization: Bearer)
        rather than a Firebase id-token (token-id header)."""
        return bool(self._load_backend_bearer())

    def _load_backend_bearer(self) -> Optional[str]:
        """Load a GHL-native backend bearer from env or a _ghl_bearer.txt file,
        returning it only if unexpired. Env GHL_BACKEND_BEARER wins; otherwise
        walk up from this module to find _ghl_bearer.txt (repo cli root)."""
        tok = os.environ.get("GHL_BACKEND_BEARER", "").strip()
        if not tok:
            here = os.path.dirname(os.path.abspath(__file__))
            for _ in range(6):
                candidate = os.path.join(here, "_ghl_bearer.txt")
                if os.path.isfile(candidate):
                    try:
                        tok = open(candidate, encoding="utf-8").read().strip()
                    except OSError:
                        tok = ""
                    break
                here = os.path.dirname(here)
        if not tok or tok.count(".") != 2:
            return None
        # Reject if expired (JWT exp claim). Malformed -> treat as usable.
        try:
            import base64
            payload = tok.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            exp = json.loads(base64.urlsafe_b64decode(payload)).get("exp", 0)
            if exp and float(exp) <= time.time():
                print(
                    "Backend bearer in _ghl_bearer.txt has expired — paste a fresh "
                    "Copy-as-cURL token.",
                    file=sys.stderr,
                )
                return None
        except Exception:
            pass
        return tok

    def _refresh_firebase(self, refresh_token: str) -> Optional[str]:
        """Exchange Firebase refresh token for a fresh ID token."""
        try:
            body = f"grant_type=refresh_token&refresh_token={refresh_token}"
            req = urllib.request.Request(
                f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}",
                data=body.encode(),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            with urllib.request.urlopen(req, context=CTX, timeout=10) as r:
                data = json.loads(r.read())
                return data.get("id_token", "")
        except Exception:
            return None


class InternalGHLClient:
    """GHL internal API client (backend.leadconnectorhq.com).

    Uses Firebase JWT auth with token-id header (NOT Authorization: Bearer).
    """

    def __init__(self, token_mgr: TokenManager, location_id: str):
        self.token_mgr = token_mgr
        self.location_id = location_id
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Optional[dict]:
        """Make an API request with auto-retry on 401."""
        token = self.token_mgr.get_token()
        result = self._do_request(method, path, body, token)

        # Retry on auth failure
        if result is None:
            token = self.token_mgr.force_refresh()
            result = self._do_request(method, path, body, token)

        return result

    def _do_request(
        self, method: str, path: str, body: dict | None, token: str
    ) -> Optional[dict]:
        self._call_count += 1
        safe_token = token.encode("ascii", "ignore").decode("ascii").strip()
        headers = {
            "channel": "APP",
            "source": "WEB_USER",
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": CHROME_UA,
        }
        if self.token_mgr.is_backend_bearer():
            # GHL-native bearer path (current auth contract for the workflow API)
            headers["Authorization"] = f"Bearer {safe_token}"
            headers["origin"] = "https://client-app-automation-workflows.leadconnectorhq.com"
            headers["referer"] = "https://client-app-automation-workflows.leadconnectorhq.com/"
        else:
            # Legacy Firebase id-token path (rejected by GHL since ~2026-07)
            headers["token-id"] = safe_token
        url = f"{BASE_URL}{path}"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, context=CTX, timeout=30) as resp:
                text = resp.read().decode()
                return json.loads(text) if text else {}
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return None  # Signal retry
            error_body = e.read().decode() if e.fp else ""
            return {"_error": True, "code": e.code, "message": error_body[:200]}
        except Exception as ex:
            return {"_error": True, "message": str(ex)}

    def create_location_tag(self, tag: str) -> bool:
        """Create a tag at location level (required before using in triggers)."""
        result = self.request(
            "POST", f"/workflow/{self.location_id}/tags/create", {"tag": tag}
        )
        return bool(result and not result.get("_error"))
