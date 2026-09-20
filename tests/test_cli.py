from unittest.mock import Mock

import pytest

from rdsh import cli


def test_require_api_token_exits_when_missing(monkeypatch, capsys):
    monkeypatch.setattr(cli, "get_api_token", lambda: None)

    with pytest.raises(SystemExit) as exc_info:
        cli.require_api_token()

    captured = capsys.readouterr()

    assert exc_info.value.code == 1
    assert "REAL_DEBRID_API_TOKEN" in captured.out


def test_build_client_uses_required_token(monkeypatch):
    fake_client = Mock()

    monkeypatch.setattr(cli, "require_api_token", lambda: "token-123")
    monkeypatch.setattr(cli, "RealDebridClient", lambda token: fake_client if token == "token-123" else None)

    assert cli.build_client() is fake_client


def test_run_routes_legacy_argument(monkeypatch):
    client = object()
    calls = []

    monkeypatch.setattr(cli, "build_client", lambda: client)
    monkeypatch.setattr(cli, "handle_input", lambda built_client, value, *args, **kwargs: calls.append((built_client, value)))
    monkeypatch.setattr(cli, "display_account_summary", lambda built_client: None)

    cli.run(["magnet:?xt=urn:btih:abc"])

    assert calls == [(client, "magnet:?xt=urn:btih:abc")]


def test_run_dispatches_unrestrict_subcommand(monkeypatch):
    client = object()
    calls = []

    monkeypatch.setattr(cli, "build_client", lambda: client)
    monkeypatch.setattr(cli, "handle_input", lambda built_client, value, *args, **kwargs: calls.append((built_client, value)))
    monkeypatch.setattr(cli, "display_account_summary", lambda built_client: None)

    cli.run(["unrestrict", "https://example.com/file"])

    assert calls == [(client, "https://example.com/file")]


def test_run_dispatches_torrent_info_subcommand(monkeypatch):
    client = object()
    calls = []

    monkeypatch.setattr(cli, "build_client", lambda: client)
    monkeypatch.setattr(
        cli,
        "show_torrent_info",
        lambda built_client, torrent_id, json_output=False: calls.append((built_client, torrent_id)),
    )

    cli.run(["torrent-info", "torrent-123"])

    assert calls == [(client, "torrent-123")]


def test_run_dispatches_list_torrents_subcommand(monkeypatch):
    client = object()
    calls = []

    monkeypatch.setattr(cli, "build_client", lambda: client)
    monkeypatch.setattr(
        cli,
        "list_torrents",
        lambda built_client, page, limit, status, json_output: calls.append(
            (built_client, page, limit, status, json_output)
        ),
    )

    cli.run(["list-torrents", "--page", "2", "--limit", "25", "--status", "downloaded"])
    cli.run(["list-torrents", "--json"])

    assert calls == [
        (client, 2, 25, "downloaded", False),
        (client, 1, None, None, True),
    ]


def test_run_dispatches_delete_subcommand(monkeypatch):
    client = object()
    calls = []

    monkeypatch.setattr(cli, "build_client", lambda: client)
    monkeypatch.setattr(
        cli,
        "delete_torrent",
        lambda built_client, torrent_id: calls.append((built_client, torrent_id)),
    )

    cli.run(["delete-torrent", "torrent-123", "torrent-456"])

    assert calls == [(client, "torrent-123"), (client, "torrent-456")]


def test_run_dispatches_dedupe_torrents_subcommand(monkeypatch):
    client = object()
    calls = []

    monkeypatch.setattr(cli, "build_client", lambda: client)
    monkeypatch.setattr(
        cli,
        "dedupe_torrents",
        lambda built_client: calls.append(built_client),
    )

    cli.run(["dedupe-torrents"])

    assert calls == [client]




def test_build_parser_supports_skip_existing_flags():
    parser = cli.build_parser()
    
    args, _ = parser.parse_known_args(["add-torrent", "-s", "file.torrent"])
    assert args.skip_existing is True

    args, _ = parser.parse_known_args(["add-magnet", "--skip-existing", "magnet:?xt=urn:btih:123"])
    assert args.skip_existing is True

    args, _ = parser.parse_known_args(["unrestrict", "--skip-duplicates", "https://example.com/file"])
    assert args.skip_existing is True


def test_dispatch_command_passes_skip_existing(monkeypatch):
    calls = []

    class FakeClient:
        pass

    monkeypatch.setattr(
        cli,
        "handle_input",
        lambda client, val, skip_existing=False, existing_filenames=None: calls.append((val, skip_existing)),
    )
    monkeypatch.setattr(cli, "display_account_summary", lambda client: None)
    monkeypatch.setattr(cli, "get_existing_filenames", lambda client: {"existing.mkv"})

    parser = cli.build_parser()
    args, _ = parser.parse_known_args(["add-magnet", "-s", "magnet:?xt=urn:btih:123"])
    cli.dispatch_command(FakeClient(), args)

    assert calls == [("magnet:?xt=urn:btih:123", True)]


def test_run_exits_with_usage_when_no_args(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.run([])

    captured = capsys.readouterr()

    assert exc_info.value.code == 1
    assert "usage:" in captured.out


def test_run_prints_error_and_exits(monkeypatch, capsys):
    monkeypatch.setattr(cli, "build_client", lambda: object())

    def raise_error(client, value, *args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "handle_input", raise_error)

    with pytest.raises(SystemExit) as exc_info:
        cli.run(["https://example.com/file"])

    captured = capsys.readouterr()

    assert exc_info.value.code == 1
    assert "Error: boom" in captured.out
