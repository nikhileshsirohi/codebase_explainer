from app.services.ingestion.github_client import GitHubClient


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.headers = {}

    def json(self):
        return self._payload


def test_detects_bad_credentials_response():
    resp = FakeResponse(401, {"message": "Bad credentials"})
    assert GitHubClient._is_bad_credentials(resp) is True


def test_ignores_other_401_messages():
    resp = FakeResponse(401, {"message": "Requires authentication"})
    assert GitHubClient._is_bad_credentials(resp) is False
