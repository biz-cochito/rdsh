from pathlib import Path

import requests

from rdsh.config import BASE_URL


class RealDebridClient:
    def __init__(self, api_token, base_url=BASE_URL, timeout=30):
        self.api_token = api_token
        self.base_url = base_url
        self.timeout = timeout

    def request(self, method, path, **kwargs):
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.api_token}"

        response = requests.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            timeout=self.timeout,
            **kwargs,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            try:
                error_data = response.json()
                if isinstance(error_data, dict) and "error" in error_data:
                    error_msg = error_data.get("error")
                    code = error_data.get("error_code")
                    raise RuntimeError(
                        f"Real-Debrid API error ({response.status_code}): {error_msg} (code {code})"
                    ) from exc
            except (ValueError, requests.exceptions.JSONDecodeError):
                pass
            raise exc

        if not response.content:
            return None

        return response.json()

    def unrestrict_link(self, link):
        return self.request("POST", "/unrestrict/link", data={"link": link})

    def add_magnet(self, magnet_link):
        return self.request("POST", "/torrents/addMagnet", data={"magnet": magnet_link})

    def add_torrent_file(self, file_path):
        torrent_path = Path(file_path)
        with torrent_path.open("rb") as torrent_file:
            return self.request(
                "PUT",
                "/torrents/addTorrent",
                data=torrent_file.read(),
                headers={"Content-Type": "application/x-bittorrent"},
            )

    def get_torrent_info(self, torrent_id):
        return self.request("GET", f"/torrents/info/{torrent_id}")

    def select_files(self, torrent_id, files="all"):
        return self.request(
            "POST", f"/torrents/selectFiles/{torrent_id}", data={"files": files}
        )

    def delete_torrent(self, torrent_id):
        return self.request("DELETE", f"/torrents/delete/{torrent_id}")

    def list_torrents(self, page=1, limit=None, status=None):
        params = {"page": page}
        if limit is not None:
            params["limit"] = limit
        if status is not None:
            params["status"] = status
        return self.request("GET", "/torrents", params=params)
