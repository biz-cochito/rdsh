import json
import time
import urllib.parse
from datetime import datetime
from pathlib import Path


def extract_magnet_dn(magnet_link: str) -> str | None:
    parsed = urllib.parse.urlparse(magnet_link)
    query_params = urllib.parse.parse_qs(parsed.query)
    dn_list = query_params.get("dn")
    if dn_list and dn_list[0]:
        return dn_list[0]
    return None


def get_existing_filenames(client) -> set[str]:
    torrents = client.list_torrents(limit=100)
    filenames = set()
    if isinstance(torrents, list):
        for item in torrents:
            if isinstance(item, dict) and item.get("filename"):
                filenames.add(str(item["filename"]).lower())
    return filenames


from rich import print
from rich.markup import escape

from rdsh.config import POLL_INTERVAL_SECONDS, POLL_TIMEOUT_SECONDS
from rdsh.utils import format_bytes


def unrestrict_link(client, host_link):
    result = client.unrestrict_link(host_link)
    download = result.get("download") if isinstance(result, dict) else None
    print(download)
    return download


def get_torrent_info(client, torrent_id):
    return client.get_torrent_info(torrent_id)


def wait_for_status(client, torrent_id: str, expected_status: str):
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    status = None

    while time.time() < deadline:
        info = get_torrent_info(client, torrent_id)
        if isinstance(info, dict):
            status = info.get("status")

            if status == expected_status:
                return info

            if expected_status == "waiting_files_selection" and status in {
                "downloading",
                "downloaded",
                "queued",
                "compressing",
                "uploading",
            }:
                return info

            if status in {"error", "virus", "dead", "magnet_error"}:
                raise RuntimeError(f"Torrent failed with status '{status}'.")

        time.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError(
        f"Timed out waiting for torrent status '{expected_status}'. Last status: '{status}'."
    )


def select_all_files(client, torrent_id):
    client.select_files(torrent_id, files="all")


def print_unrestricted_torrent_links(client, torrent_id):
    info = wait_for_status(client, torrent_id, "downloaded")
    links = info.get("links", []) if isinstance(info, dict) else []

    if not links:
        raise RuntimeError("Torrent completed but no downloadable links were returned.")

    unrestricted_links = []
    for link in links:
        result = client.unrestrict_link(link)
        download = result.get("download") if isinstance(result, dict) else None
        print(download)
        if download:
            unrestricted_links.append(download)

    return unrestricted_links


def handle_magnet_link(client, magnet_link, skip_existing=False, existing_filenames=None):
    if skip_existing:
        if existing_filenames is None:
            existing_filenames = get_existing_filenames(client)
        dn = extract_magnet_dn(magnet_link)
        if dn and dn.lower() in existing_filenames:
            print(f"Skipped (already exists): {dn}")
            return

    result = client.add_magnet(magnet_link)
    torrent_id = result.get("id") if isinstance(result, dict) else None

    if not torrent_id:
        raise RuntimeError(
            "Real-Debrid did not return a torrent id for the magnet link."
        )

    info = wait_for_status(client, torrent_id, "waiting_files_selection")
    if isinstance(info, dict) and info.get("status") == "waiting_files_selection":
        select_all_files(client, torrent_id)
    print(f"Added magnet (ID: {torrent_id})")


def handle_torrent_file(client, file_path, skip_existing=False, existing_filenames=None):
    torrent_path = Path(file_path)
    if not torrent_path.is_file():
        raise FileNotFoundError(f"Torrent file not found: {file_path}")

    if skip_existing:
        if existing_filenames is None:
            existing_filenames = get_existing_filenames(client)
        name_lower = torrent_path.name.lower()
        stem_lower = torrent_path.stem.lower()
        if name_lower in existing_filenames or stem_lower in existing_filenames:
            print(f"Skipped (already exists): {torrent_path.name}")
            return

    result = client.add_torrent_file(file_path)
    torrent_id = result.get("id") if isinstance(result, dict) else None

    if not torrent_id:
        raise RuntimeError(
            "Real-Debrid did not return a torrent id for the .torrent file."
        )

    info = wait_for_status(client, torrent_id, "waiting_files_selection")
    if isinstance(info, dict) and info.get("status") == "waiting_files_selection":
        select_all_files(client, torrent_id)
    print(f"Added torrent file: {torrent_path.name} (ID: {torrent_id})")


def handle_input(client, value, skip_existing=False, existing_filenames=None):
    if value.startswith("magnet:"):
        handle_magnet_link(client, value, skip_existing=skip_existing, existing_filenames=existing_filenames)
        return

    if value.lower().endswith(".torrent"):
        handle_torrent_file(client, value, skip_existing=skip_existing, existing_filenames=existing_filenames)
        return

    unrestrict_link(client, value)


def show_torrent_info(client, torrent_id, json_output=False):
    info = client.get_torrent_info(torrent_id)
    if json_output:
        print(json.dumps(info, indent=2, sort_keys=True))
    else:
        status_color = {"downloaded": "cyan", "downloading": "yellow"}.get(
            info.get("status"), "red"
        )
        file_size = str(format_bytes(info.get("bytes", 0)))
        dt = (
            datetime.fromisoformat(info.get("added", 0))
            if isinstance(info.get("added", 0), str)
            else datetime.fromtimestamp(info.get("added", 0))
        )

        print(f"Name: [{status_color}]{info.get('filename')}[/{status_color}]")
        print(f"Torrent ID: {torrent_id}")
        print(f"Size: {file_size}")
        print(f"Added: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Status: {info.get('status')}")
        print(f"Progress: {info.get('progress', 0)}%")
        print("\nFiles:")
        for file in info.get("files", []):
            print(f'  "{file.get("path", "Unknown")}"')
        print("\nLinks:")
        for link in info.get("links", []):
            print(f"  {link}")


def delete_torrent(client, torrent_id):
    torrent_info = client.get_torrent_info(torrent_id)
    torrent_name = torrent_info.get("filename") if torrent_info else None
    if torrent_info:
        confirm = input(f"Are you sure you want to delete {torrent_name}? (y/n): ")
        if confirm.lower() != "y":
            print("Deletion cancelled.")
            return
        print(f"Deleting item: {torrent_name}")
    else:
        print(f"Item not found: {torrent_id}")
        return
    client.delete_torrent(torrent_id)
    print(f"Deleted item: {torrent_name if torrent_name else torrent_id}")


def list_torrents(client, page=1, limit=None, status=None, json_output=False):
    torrents = client.list_torrents(page=page, limit=limit, status=status)
    if json_output:
        print(json.dumps(torrents, indent=2, sort_keys=True))
    else:
        for i, item in enumerate(torrents):
            status_color = {"downloaded": "cyan", "downloading": "yellow"}.get(
                item["status"], "red"
            )
            file_size = str(format_bytes(item["bytes"]))
            print(
                f"{item['id']} - [{status_color}]{item['filename']}[/{status_color}] - {file_size} - status: {item['status']}"
            )


def dedupe_torrents(client):
    torrents = client.list_torrents(limit=100)
    grouped = {}

    for torrent in torrents:
        if not isinstance(torrent, dict):
            continue

        filename = torrent.get("filename")
        if not filename:
            continue

        grouped.setdefault(filename, []).append(torrent)

    duplicate_groups = [group for group in grouped.values() if len(group) > 1]

    if not duplicate_groups:
        print("No duplicate torrents found.")
        return

    for group in duplicate_groups:
        keeper = next(
            (item for item in group if item.get("status") == "downloaded"), group[0]
        )
        print(
            escape(
                f"Keeping torrent: {keeper.get('id')} [{keeper.get('status', 'unknown')}] {keeper.get('filename')}"
            )
        )

        for torrent in group:
            if torrent is keeper:
                continue

            client.delete_torrent(torrent["id"])
            print(
                escape(
                    f"Deleted duplicate: {torrent.get('id')} [{torrent.get('status', 'unknown')}] {torrent.get('filename')}"
                )
            )


def display_account_summary(client):
    torrents = client.list_torrents(limit=100)
    if not isinstance(torrents, list):
        print("Failed downloads: 0")
        return

    in_progress_statuses = {
        "magnet_conversion",
        "waiting_files_selection",
        "queued",
        "downloading",
        "compressing",
        "uploading",
    }
    failed_statuses = {"error", "virus", "dead", "magnet_error"}

    in_progress = [
        t
        for t in torrents
        if isinstance(t, dict) and t.get("status") in in_progress_statuses
    ]
    failed_count = sum(
        1
        for t in torrents
        if isinstance(t, dict) and t.get("status") in failed_statuses
    )

    print("\nIn-Progress Downloads:")
    if not in_progress:
        print("  None")
    else:
        for t in in_progress:
            filename = t.get("filename") or t.get("id") or "Unknown"
            status = t.get("status", "unknown")
            progress = t.get("progress", 0)
            speed = t.get("speed")
            speed_str = f" @ {format_bytes(speed)}/s" if speed else ""
            print(
                f"  • {filename} [{status}] - {progress}%{speed_str}".replace(
                    "[", r"\["
                ).replace("]", r"\]")
            )

    print(f"\nFailed downloads: {failed_count}")
