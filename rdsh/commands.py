import json
import time
from pathlib import Path

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


def handle_magnet_link(client, magnet_link):
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


def handle_torrent_file(client, file_path):
    torrent_path = Path(file_path)
    if not torrent_path.is_file():
        raise FileNotFoundError(f"Torrent file not found: {file_path}")

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


def handle_input(client, value):
    if value.startswith("magnet:"):
        handle_magnet_link(client, value)
        return

    if value.lower().endswith(".torrent"):
        handle_torrent_file(client, value)
        return

    unrestrict_link(client, value)


def show_torrent_info(client, torrent_id):
    print(json.dumps(client.get_torrent_info(torrent_id), indent=2, sort_keys=True))


def delete_torrent(client, torrent_id):
    torrent_info = client.get_torrent_info(torrent_id)
    torrent_name = torrent_info.get("filename") if torrent_info else None
    if torrent_info:
        confirm = input(f"Are you sure you want to delete {torrent_name}? (y/n): ")
        if confirm.lower() != 'y':
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
            status_color = {"downloaded": "green", "downloading": "yellow"}.get(
                item["status"], "red"
            )
            file_size = format_bytes(item["bytes"])
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
            print(f"  • {filename} [{status}] - {progress}%{speed_str}".replace("[", r"\[").replace("]", r"\]"))

    print(f"\nFailed downloads: {failed_count}")
