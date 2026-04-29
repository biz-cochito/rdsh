from pathlib import Path
from unittest.mock import Mock

from rdsh.client import RealDebridClient


def test_request_adds_authorization_header(monkeypatch):
    response = Mock()
    response.content = b'{"ok": true}'
    response.json.return_value = {"ok": True}
    response.raise_for_status.return_value = None

    request = Mock(return_value=response)
    monkeypatch.setattr("rdsh.client.requests.request", request)

    client = RealDebridClient("token-123")
    result = client.request("POST", "/path", data={"link": "value"})

    assert result == {"ok": True}
    request.assert_called_once_with(
        "POST",
        "https://api.real-debrid.com/rest/1.0/path",
        headers={"Authorization": "Bearer token-123"},
        timeout=30,
        data={"link": "value"},
    )


def test_add_torrent_file_uploads_expected_payload(monkeypatch, tmp_path):
    torrent_file = tmp_path / "sample.torrent"
    torrent_file.write_bytes(b"torrent-data")
    calls = []

    def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"id": "torrent-456"}

    client = RealDebridClient("token-123")
    monkeypatch.setattr(client, "request", fake_request)

    result = client.add_torrent_file(torrent_file)

    upload_call = calls[0]
    uploaded_name, uploaded_file, content_type = upload_call[2]["files"]["file"]

    assert result == {"id": "torrent-456"}
    assert upload_call[0] == "PUT"
    assert upload_call[1] == "/torrents/addTorrent"
    assert uploaded_name == "sample.torrent"
    assert Path(uploaded_file.name) == torrent_file
    assert content_type == "application/x-bittorrent"


def test_list_torrents_passes_optional_params(monkeypatch):
    calls = []

    def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return []

    client = RealDebridClient("token-123")
    monkeypatch.setattr(client, "request", fake_request)

    result = client.list_torrents(page=2, limit=25, status="downloaded")

    assert result == []
    assert calls == [
        ("GET", "/torrents", {"params": {"page": 2, "limit": 25, "status": "downloaded"}})
    ]
