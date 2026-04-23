import requests
from pathlib import Path


class ApiClient:
    def __init__(self, credentials_path: Path | None = None):
        if credentials_path is None:
            base = Path(__file__).resolve().parent.parent.parent.parent
            credentials_path = base / "config" / "credentials.json"

        with open(credentials_path) as f:
            import json
            creds = json.load(f)

        self.base_url = creds["base_url"]
        self.authorization = creds["authorization"]
        self.cookies = creds.get("cookies", "")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": self.authorization,
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Content-Language": "zh_CN",
            "Cookie": self.cookies,
        })

    def post(self, path: str, json: dict) -> dict:
        url = f"{self.base_url}{path}"
        resp = self.session.post(url, json=json, timeout=(60, 120))
        resp.raise_for_status()
        return resp.json()

    def get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params, timeout=(60, 120))
        resp.raise_for_status()
        return resp.json()
