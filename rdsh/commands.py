import time
from pathlib import Path
import json

from rdsh.config import POLL_INTERVAL_SECONDS, POLL_TIMEOUT_SECONDS


def unrestrict_link(client, host_link):
    result = client.unrestrict_link(host_link)
    print(f"Direct Link: {result.get('download')}")


def get_torrent_info(client, torrent_id):
    return client.get_torrent_info(torrent_id)


def wait_for_status(client, torrent_id, expected_status):
    deadline = time.time() + POLL_TIMEOUT_SECONDS

    while time.time() < deadline:
        info = get_torrent_info(client, torrent_id)
        status = info.get("status")

        if status == expected_status:
            return info

        if status in {"error", "virus", "dead"}:
            raise RuntimeError(f"Torrent failed with status '{status}'.")

        time.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError(
        f"Timed out waiting for torrent status '{expected_status}'. Last status: '{status}'."
    )


def select_all_files(client, torrent_id):
    client.select_files(torrent_id, files="all")


def print_unrestricted_torrent_links(client, torrent_id):
    info = wait_for_status(client, torrent_id, "downloaded")
    links = info.get("links", [])

    if not links:
        raise RuntimeError("Torrent completed but no downloadable links were returned.")

    for link in links:
        result = client.unrestrict_link(link)
        print(f"Direct Link: {result.get('download')}")


def handle_magnet_link(client, magnet_link):
    result = client.add_magnet(magnet_link)
    torrent_id = result.get("id")

    if not torrent_id:
        raise RuntimeError(
            "Real-Debrid did not return a torrent id for the magnet link."
        )

    wait_for_status(client, torrent_id, "waiting_files_selection")
    select_all_files(client, torrent_id)
    print_unrestricted_torrent_links(client, torrent_id)


def handle_torrent_file(client, file_path):
    torrent_path = Path(file_path)
    if not torrent_path.is_file():
        raise FileNotFoundError(f"Torrent file not found: {file_path}")

    result = client.add_torrent_file(file_path)
    torrent_id = result.get("id")

    if not torrent_id:
        raise RuntimeError(
            "Real-Debrid did not return a torrent id for the .torrent file."
        )

    wait_for_status(client, torrent_id, "waiting_files_selection")
    select_all_files(client, torrent_id)
    print_unrestricted_torrent_links(client, torrent_id)


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


def list_torrents(client, page=1, limit=None, status=None):
    torrents = client.list_torrents(page=page, limit=limit, status=status)
    print(json.dumps(torrents, indent=2, sort_keys=True))
