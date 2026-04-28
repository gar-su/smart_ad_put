import requests
from pathlib import Path


DEFAULT_CREDENTIALS_PATH = Path("/Users/gar/projects/auto_delivery/config/credentials.json")


class ApiClient:
    def __init__(self, credentials_path: Path | None = None):
        cred_path = credentials_path or DEFAULT_CREDENTIALS_PATH
        with open(cred_path) as f:
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
