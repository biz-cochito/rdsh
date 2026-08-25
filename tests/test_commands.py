import pytest

from rdsh import commands


def test_wait_for_status_returns_when_expected(monkeypatch):
    responses = iter([
        {"status": "queued"},
        {"status": "downloaded", "links": ["https://rd/link"]},
    ])

    monkeypatch.setattr(commands, "get_torrent_info", lambda client, torrent_id: next(responses))
    monkeypatch.setattr(commands.time, "sleep", lambda _: None)

    info = commands.wait_for_status(object(), "torrent-id", "downloaded")

    assert info == {"status": "downloaded", "links": ["https://rd/link"]}


def test_wait_for_status_raises_for_failed_status(monkeypatch):
    monkeypatch.setattr(commands, "get_torrent_info", lambda client, torrent_id: {"status": "dead"})

    with pytest.raises(RuntimeError, match="dead"):
        commands.wait_for_status(object(), "torrent-id", "downloaded")


def test_print_unrestricted_torrent_links_prints_each_link(capsys):
    class FakeClient:
        def unrestrict_link(self, link):
            return {"download": f"https://direct/{link}"}

    client = FakeClient()

    def fake_wait_for_status(current_client, torrent_id, status):
        assert current_client is client
        assert status == "downloaded"
        return {"links": ["rd-link-1", "rd-link-2"]}

    original = commands.wait_for_status
    commands.wait_for_status = fake_wait_for_status
    try:
        commands.print_unrestricted_torrent_links(client, "torrent-id")
    finally:
        commands.wait_for_status = original

    captured = capsys.readouterr()

    assert "https://direct/rd-link-1" in captured.out
    assert "https://direct/rd-link-2" in captured.out


def test_handle_magnet_link_runs_expected_flow(monkeypatch):
    calls = []

    class FakeClient:
        def add_magnet(self, magnet_link):
            calls.append(("add_magnet", magnet_link))
            return {"id": "torrent-123"}

    client = FakeClient()

    monkeypatch.setattr(
        commands,
        "wait_for_status",
        lambda current_client, torrent_id, status: calls.append(("wait", torrent_id, status)),
    )
    monkeypatch.setattr(
        commands,
        "select_all_files",
        lambda current_client, torrent_id: calls.append(("select", torrent_id)),
    )
    monkeypatch.setattr(
        commands,
        "print_unrestricted_torrent_links",
        lambda current_client, torrent_id: calls.append(("print", torrent_id)),
    )

    commands.handle_magnet_link(client, "magnet:?xt=urn:btih:abc")

    assert calls == [
        ("add_magnet", "magnet:?xt=urn:btih:abc"),
        ("wait", "torrent-123", "waiting_files_selection"),
        ("select", "torrent-123"),
        ("print", "torrent-123"),
    ]


def test_handle_torrent_file_runs_expected_flow(monkeypatch, tmp_path):
    torrent_file = tmp_path / "sample.torrent"
    torrent_file.write_bytes(b"torrent-data")
    calls = []

    class FakeClient:
        def add_torrent_file(self, file_path):
            calls.append(("add_torrent_file", file_path))
            return {"id": "torrent-456"}

    client = FakeClient()

    monkeypatch.setattr(
        commands,
        "wait_for_status",
        lambda current_client, torrent_id, status: calls.append(("wait", torrent_id, status)),
    )
    monkeypatch.setattr(
        commands,
        "select_all_files",
        lambda current_client, torrent_id: calls.append(("select", torrent_id)),
    )
    monkeypatch.setattr(
        commands,
        "print_unrestricted_torrent_links",
        lambda current_client, torrent_id: calls.append(("print", torrent_id)),
    )

    commands.handle_torrent_file(client, str(torrent_file))

    assert calls == [
        ("add_torrent_file", str(torrent_file)),
        ("wait", "torrent-456", "waiting_files_selection"),
        ("select", "torrent-456"),
        ("print", "torrent-456"),
    ]


def test_handle_input_routes_by_input_type(monkeypatch):
    calls = []
    client = object()

    monkeypatch.setattr(
        commands, "handle_magnet_link", lambda current_client, value: calls.append(("magnet", current_client, value))
    )
    monkeypatch.setattr(
        commands, "handle_torrent_file", lambda current_client, value: calls.append(("torrent", current_client, value))
    )
    monkeypatch.setattr(
        commands, "unrestrict_link", lambda current_client, value: calls.append(("link", current_client, value))
    )

    commands.handle_input(client, "magnet:?xt=urn:btih:abc")
    commands.handle_input(client, "movie.torrent")
    commands.handle_input(client, "https://example.com/file")

    assert calls == [
        ("magnet", client, "magnet:?xt=urn:btih:abc"),
        ("torrent", client, "movie.torrent"),
        ("link", client, "https://example.com/file"),
    ]


def test_show_torrent_info_prints_json(capsys):
    class FakeClient:
        def get_torrent_info(self, torrent_id):
            return {"id": torrent_id, "status": "downloaded"}

    commands.show_torrent_info(FakeClient(), "torrent-123")

    captured = capsys.readouterr()

    assert '"id": "torrent-123"' in captured.out
    assert '"status": "downloaded"' in captured.out


def test_play_magnet_in_mpv(monkeypatch):
    calls = []

    class FakeClient:
        def add_magnet(self, magnet_link):
            calls.append(("add_magnet", magnet_link))
            return {"id": "torrent-789"}

    client = FakeClient()

    monkeypatch.setattr(
        commands,
        "wait_for_status",
        lambda current_client, torrent_id, status: calls.append(
            ("wait", torrent_id, status)
        ),
    )
    monkeypatch.setattr(
        commands,
        "select_all_files",
        lambda current_client, torrent_id: calls.append(("select", torrent_id)),
    )
    monkeypatch.setattr(
        commands,
        "print_unrestricted_torrent_links",
        lambda current_client, torrent_id: ["https://direct.stream/link.mkv"],
    )
    monkeypatch.setattr(
        commands.subprocess,
        "run",
        lambda cmd: calls.append(("subprocess", cmd)),
    )

    commands.play_magnet_in_mpv(client, "magnet:?xt=urn:btih:xyz")

    assert calls == [
        ("add_magnet", "magnet:?xt=urn:btih:xyz"),
        ("wait", "torrent-789", "waiting_files_selection"),
        ("select", "torrent-789"),
        ("subprocess", ["mpv", "https://direct.stream/link.mkv"]),
    ]


def test_list_torrents_prints_json(capsys):
    class FakeClient:
        def list_torrents(self, page=1, limit=None, status=None):
            assert page == 2
            assert limit == 10
            assert status == "downloaded"
            return [{"id": "torrent-123"}]

    commands.list_torrents(FakeClient(), page=2, limit=10, status="downloaded")

    captured = capsys.readouterr()

    assert '"id": "torrent-123"' in captured.out
