import argparse
import sys

import requests

from rdsh.client import RealDebridClient
from rdsh.commands import (
    dedupe_torrents,
    delete_torrent,
    display_account_summary,
    get_existing_filenames,
    handle_input,
    list_torrents,
    show_torrent_info,
)
from rdsh.config import API_TOKEN_ENV_VAR, get_api_token


def require_api_token():
    api_token = get_api_token()
    if api_token:
        return api_token

    print(f"Error: {API_TOKEN_ENV_VAR} environment variable not set.")
    raise SystemExit(1)


def build_client():
    return RealDebridClient(require_api_token())


def build_parser():
    parser = argparse.ArgumentParser(prog="rdsh")
    parser.add_argument(
        "-s",
        "--skip-existing",
        "--skip-duplicates",
        dest="skip_existing",
        action="store_true",
        help="Skip items that already exist in account",
    )
    subparsers = parser.add_subparsers(dest="command")

    unrestrict_parser = subparsers.add_parser(
        "unrestrict", help="Unrestrict a hosted link"
    )
    unrestrict_parser.add_argument(
        "values", nargs="+", help="Hosted links, magnet links, or .torrent paths"
    )
    unrestrict_parser.add_argument(
        "-s",
        "--skip-existing",
        "--skip-duplicates",
        dest="skip_existing",
        action="store_true",
        help="Skip items that already exist in account",
    )

    magnet_parser = subparsers.add_parser("add-magnet", help="Add a magnet link")
    magnet_parser.add_argument("magnet_links", nargs="+", help="Magnet URIs to add")
    magnet_parser.add_argument(
        "-s",
        "--skip-existing",
        "--skip-duplicates",
        dest="skip_existing",
        action="store_true",
        help="Skip items that already exist in account",
    )

    torrent_parser = subparsers.add_parser("add-torrent", help="Add a .torrent file")
    torrent_parser.add_argument("file_paths", nargs="+", help="Paths to .torrent files")
    torrent_parser.add_argument(
        "-s",
        "--skip-existing",
        "--skip-duplicates",
        dest="skip_existing",
        action="store_true",
        help="Skip items that already exist in account",
    )

    info_parser = subparsers.add_parser(
        "torrent-info", help="Show info for a torrent id"
    )
    info_parser.add_argument("torrent_ids", nargs="+", help="Real-Debrid torrent ids")
    info_parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    list_parser = subparsers.add_parser("list-torrents", help="List available torrents")
    list_parser.add_argument(
        "--page", type=int, default=1, help="Results page to fetch"
    )
    list_parser.add_argument("--limit", type=int, help="Maximum results per page")
    list_parser.add_argument("--status", help="Filter by torrent status")
    list_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    delete_parser = subparsers.add_parser(
        "delete-torrent", aliases=["delete"], help="Delete one or more torrents by their ids"
    )
    delete_parser.add_argument("torrent_ids", nargs="+", help="Real-Debrid torrent ids to delete")

    subparsers.add_parser(
        "dedupe-torrents",
        help="Delete duplicate torrents by filename, preferring downloaded items",
    )

    return parser


def dispatch_command(client, args):
    skip_existing = getattr(args, "skip_existing", False)
    existing_filenames = get_existing_filenames(client) if skip_existing else None

    if args.command == "unrestrict":
        for val in args.values:
            handle_input(client, val, skip_existing=skip_existing, existing_filenames=existing_filenames)
        display_account_summary(client)
        return

    if args.command == "add-magnet":
        for link in args.magnet_links:
            handle_input(client, link, skip_existing=skip_existing, existing_filenames=existing_filenames)
        display_account_summary(client)
        return

    if args.command == "add-torrent":
        for path in args.file_paths:
            handle_input(client, path, skip_existing=skip_existing, existing_filenames=existing_filenames)
        display_account_summary(client)
        return

    if args.command == "torrent-info":
        for torrent_id in args.torrent_ids:
            show_torrent_info(client, torrent_id, json_output=args.json)
        return

    if args.command == "list-torrents":
        list_torrents(client, page=args.page, limit=args.limit, status=args.status, json_output=args.json)
        return

    if args.command in ("delete-torrent", "delete"):
        for torrent_id in args.torrent_ids:
            delete_torrent(client, torrent_id)
        return

    if args.command == "dedupe-torrents":
        dedupe_torrents(client)
        return

    raise ValueError(f"Unsupported command: {args.command}")


def run(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()

    if not argv:
        parser.print_help()
        raise SystemExit(1)

    try:
        raw_flags = {"-s", "--skip-existing", "--skip-duplicates"}
        skip_existing = any(arg in raw_flags for arg in argv)
        positional_args = [arg for arg in argv if arg not in raw_flags]

        if positional_args and (
            positional_args[0].startswith("magnet:")
            or positional_args[0].lower().endswith(".torrent")
            or "://" in positional_args[0]
        ):
            client = build_client()
            existing_filenames = get_existing_filenames(client) if skip_existing else None
            for arg in positional_args:
                handle_input(client, arg, skip_existing=skip_existing, existing_filenames=existing_filenames)
            display_account_summary(client)
            return

        args = parser.parse_args(argv)
        if args.command is None:
            parser.print_help()
            raise SystemExit(1)

        dispatch_command(build_client(), args)
    except (
        requests.exceptions.RequestException,
        RuntimeError,
        TimeoutError,
        OSError,
    ) as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)
