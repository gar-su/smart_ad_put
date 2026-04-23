import json
from pathlib import Path
import httpx


class ApiClient:
    def __init__(self, credentials_path: Path | None = None):
        if credentials_path is None:
            # Try to find credentials.json relative to this file's parent directories
            base = Path(__file__).resolve().parent.parent.parent.parent
            credentials_path = base / "config" / "credentials.json"

        with open(credentials_path) as f:
            creds = json.load(f)

        self.base_url = creds["base_url"]
        self.authorization = creds["authorization"]
        self.cookies = creds.get("cookies", "")

    def _build_headers(self) -> dict:
        return {
            "Authorization": self.authorization,
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Content-Language": "zh_CN",
            "Cookie": self.cookies,
        }

    def post(self, path: str, json: dict) -> dict:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=json, headers=self._build_headers())
            resp.raise_for_status()
            return resp.json()

    def get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, params=params, headers=self._build_headers())
            resp.raise_for_status()
            return resp.json()
