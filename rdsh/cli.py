import argparse
import sys

import requests

from rdsh.client import RealDebridClient
from rdsh.commands import handle_input, list_torrents, show_torrent_info
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
    subparsers = parser.add_subparsers(dest="command")

    unrestrict_parser = subparsers.add_parser("unrestrict", help="Unrestrict a hosted link")
    unrestrict_parser.add_argument("values", nargs="+", help="Hosted links, magnet links, or .torrent paths")

    magnet_parser = subparsers.add_parser("add-magnet", help="Add a magnet link")
    magnet_parser.add_argument("magnet_links", nargs="+", help="Magnet URIs to add")

    torrent_parser = subparsers.add_parser("add-torrent", help="Add a .torrent file")
    torrent_parser.add_argument("file_paths", nargs="+", help="Paths to .torrent files")

    info_parser = subparsers.add_parser("torrent-info", help="Show info for a torrent id")
    info_parser.add_argument("torrent_ids", nargs="+", help="Real-Debrid torrent ids")

    list_parser = subparsers.add_parser("list-torrents", help="List available torrents")
    list_parser.add_argument("--page", type=int, default=1, help="Results page to fetch")
    list_parser.add_argument("--limit", type=int, help="Maximum results per page")
    list_parser.add_argument("--status", help="Filter by torrent status")

    return parser


def dispatch_command(client, args):
    if args.command == "unrestrict":
        for val in args.values:
            handle_input(client, val)
        return

    if args.command == "add-magnet":
        for link in args.magnet_links:
            handle_input(client, link)
        return

    if args.command == "add-torrent":
        for path in args.file_paths:
            handle_input(client, path)
        return

    if args.command == "torrent-info":
        for torrent_id in args.torrent_ids:
            show_torrent_info(client, torrent_id)
        return

    if args.command == "list-torrents":
        list_torrents(client, page=args.page, limit=args.limit, status=args.status)
        return

    raise ValueError(f"Unsupported command: {args.command}")


def run(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()

    if not argv:
        parser.print_help()
        raise SystemExit(1)

    try:
        if argv[0].startswith("magnet:") or argv[0].lower().endswith(".torrent") or "://" in argv[0]:
            client = build_client()
            for arg in argv:
                handle_input(client, arg)
            return

        args = parser.parse_args(argv)
        if args.command is None:
            parser.print_help()
            raise SystemExit(1)

        dispatch_command(build_client(), args)
    except (requests.exceptions.RequestException, RuntimeError, TimeoutError, OSError) as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)
