import os
import sys
import time
from pathlib import Path

import requests

API_TOKEN = os.getenv("REAL_DEBRID_API_TOKEN")
BASE_URL = "https://api.real-debrid.com/rest/1.0"
POLL_INTERVAL_SECONDS = 2
POLL_TIMEOUT_SECONDS = 120


def require_api_token():
    if API_TOKEN:
        return

    print("Error: REAL_DEBRID_API_TOKEN environment variable not set.")
    sys.exit(1)


def api_request(method, path, **kwargs):
    require_api_token()

    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {API_TOKEN}"

    response = requests.request(
        method,
        f"{BASE_URL}{path}",
        headers=headers,
        timeout=30,
        **kwargs,
    )
    response.raise_for_status()

    if not response.content:
        return None

    return response.json()


def unrestrict_link(host_link):
    result = api_request("POST", "/unrestrict/link", data={"link": host_link})
    print(f"Direct Link: {result.get('download')}")


def get_torrent_info(torrent_id):
    return api_request("GET", f"/torrents/info/{torrent_id}")


def wait_for_status(torrent_id, expected_status):
    deadline = time.time() + POLL_TIMEOUT_SECONDS

    while time.time() < deadline:
        info = get_torrent_info(torrent_id)
        status = info.get("status")

        if status == expected_status:
            return info

        if status in {"error", "virus", "dead"}:
            raise RuntimeError(f"Torrent failed with status '{status}'.")

        time.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError(
        f"Timed out waiting for torrent status '{expected_status}'. Last status: '{status}'."
    )


def select_all_files(torrent_id):
    api_request("POST", f"/torrents/selectFiles/{torrent_id}", data={"files": "all"})


def print_unrestricted_torrent_links(torrent_id):
    info = wait_for_status(torrent_id, "downloaded")
    links = info.get("links", [])

    if not links:
        raise RuntimeError("Torrent completed but no downloadable links were returned.")

    for link in links:
        result = api_request("POST", "/unrestrict/link", data={"link": link})
        print(f"Direct Link: {result.get('download')}")


def handle_magnet_link(magnet_link):
    result = api_request("POST", "/torrents/addMagnet", data={"magnet": magnet_link})
    torrent_id = result.get("id")

    if not torrent_id:
        raise RuntimeError("Real-Debrid did not return a torrent id for the magnet link.")

    wait_for_status(torrent_id, "waiting_files_selection")
    select_all_files(torrent_id)
    print_unrestricted_torrent_links(torrent_id)


def handle_torrent_file(file_path):
    torrent_path = Path(file_path)
    if not torrent_path.is_file():
        raise FileNotFoundError(f"Torrent file not found: {file_path}")

    with torrent_path.open("rb") as torrent_file:
        result = api_request(
            "PUT",
            "/torrents/addTorrent",
            files={"file": (torrent_path.name, torrent_file, "application/x-bittorrent")},
        )

    torrent_id = result.get("id")
    if not torrent_id:
        raise RuntimeError("Real-Debrid did not return a torrent id for the .torrent file.")

    wait_for_status(torrent_id, "waiting_files_selection")
    select_all_files(torrent_id)
    print_unrestricted_torrent_links(torrent_id)


def handle_input(value):
    if value.startswith("magnet:"):
        handle_magnet_link(value)
        return

    if value.lower().endswith(".torrent"):
        handle_torrent_file(value)
        return

    unrestrict_link(value)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <host-link|magnet-link|path-to.torrent>")
        sys.exit(1)

    try:
        handle_input(sys.argv[1])
    except (requests.exceptions.RequestException, RuntimeError, TimeoutError, OSError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)
