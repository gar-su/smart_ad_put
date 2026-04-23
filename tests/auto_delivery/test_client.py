import pytest
from pathlib import Path
from src.auto_delivery.api.client import ApiClient


def test_client_loads_credentials(tmp_path):
    # Create a temporary credentials file
    creds_file = tmp_path / "credentials.json"
    creds_file.write_text('{"base_url":"https://test.com","authorization":"Bearer test","cookies":"x=y"}')

    client = ApiClient(credentials_path=creds_file)
    assert client.base_url == "https://test.com"
    assert client.authorization == "Bearer test"
    assert client.cookies == "x=y"
