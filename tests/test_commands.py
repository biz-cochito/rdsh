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
        lambda current_client, torrent_id, status: {"status": "waiting_files_selection"},
    )
    monkeypatch.setattr(
        commands,
        "select_all_files",
        lambda current_client, torrent_id: calls.append(("select", torrent_id)),
    )

    commands.handle_magnet_link(client, "magnet:?xt=urn:btih:abc")

    assert calls == [
        ("add_magnet", "magnet:?xt=urn:btih:abc"),
        ("select", "torrent-123"),
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
        lambda current_client, torrent_id, status: {"status": "waiting_files_selection"},
    )
    monkeypatch.setattr(
        commands,
        "select_all_files",
        lambda current_client, torrent_id: calls.append(("select", torrent_id)),
    )

    commands.handle_torrent_file(client, str(torrent_file))

    assert calls == [
        ("add_torrent_file", str(torrent_file)),
        ("select", "torrent-456"),
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





def test_list_torrents_prints_json(capsys):
    class FakeClient:
        def list_torrents(self, page=1, limit=None, status=None):
            assert page == 2
            assert limit == 10
            assert status == "downloaded"
            return [{"id": "torrent-123"}]

    commands.list_torrents(FakeClient(), page=2, limit=10, status="downloaded", json_output=True)

    captured = capsys.readouterr()

    assert '"id": "torrent-123"' in captured.out


def test_list_torrents_prints_rich_format(capsys):
    class FakeClient:
        def list_torrents(self, page=1, limit=None, status=None):
            return [{"id": "torrent-123", "filename": "movie.mkv", "bytes": 1024, "status": "downloaded"}]

    commands.list_torrents(FakeClient())

    captured = capsys.readouterr()

    assert "torrent-123" in captured.out
    assert "movie.mkv" in captured.out
    assert "status: downloaded" in captured.out


def test_display_account_summary_prints_in_progress_and_failed_count(capsys):
    class FakeClient:
        def list_torrents(self, limit=100):
            return [
                {
                    "id": "t1",
                    "filename": "movie1.mkv",
                    "status": "downloading",
                    "progress": 45,
                    "speed": 2621440,
                },
                {
                    "id": "t2",
                    "filename": "movie2.mkv",
                    "status": "error",
                },
                {
                    "id": "t3",
                    "filename": "movie3.mkv",
                    "status": "downloaded",
                },
            ]

    commands.display_account_summary(FakeClient())

    captured = capsys.readouterr()

    assert "In-Progress Downloads:" in captured.out
    assert "• movie1.mkv [downloading\\] - 45% @ 2.5 MB/s" in captured.out
    assert "Failed downloads: 1" in captured.out


def test_dedupe_torrents_prefers_downloaded_duplicate(capsys):
    deleted_ids = []

    class FakeClient:
        def list_torrents(self, limit=100):
            return [
                {"id": "t1", "filename": "movie.mkv", "status": "downloading"},
                {"id": "t2", "filename": "movie.mkv", "status": "downloaded"},
                {"id": "t3", "filename": "other.mkv", "status": "downloaded"},
            ]

        def delete_torrent(self, torrent_id):
            deleted_ids.append(torrent_id)

    commands.dedupe_torrents(FakeClient())

    captured = capsys.readouterr()

    assert deleted_ids == ["t1"]
    assert "Keeping torrent: t2 [downloaded] movie.mkv" in captured.out
    assert "Deleted duplicate: t1 [downloading] movie.mkv" in captured.out


def test_dedupe_torrents_keeps_first_when_no_duplicate_is_downloaded(capsys):
    deleted_ids = []

    class FakeClient:
        def list_torrents(self, limit=100):
            return [
                {"id": "t1", "filename": "movie.mkv", "status": "queued"},
                {"id": "t2", "filename": "movie.mkv", "status": "downloading"},
            ]

        def delete_torrent(self, torrent_id):
            deleted_ids.append(torrent_id)

    commands.dedupe_torrents(FakeClient())

    captured = capsys.readouterr()

    assert deleted_ids == ["t2"]
    assert "Keeping torrent: t1 [queued] movie.mkv" in captured.out
    assert "Deleted duplicate: t2 [downloading] movie.mkv" in captured.out


def test_dedupe_torrents_prints_message_when_no_duplicates_exist(capsys):
    class FakeClient:
        def list_torrents(self, limit=100):
            return [
                {"id": "t1", "filename": "movie.mkv", "status": "downloaded"},
                {"id": "t2", "filename": "show.mkv", "status": "queued"},
            ]

        def delete_torrent(self, torrent_id):
            raise AssertionError(f"unexpected delete: {torrent_id}")

    commands.dedupe_torrents(FakeClient())

    captured = capsys.readouterr()

    assert "No duplicate torrents found." in captured.out
