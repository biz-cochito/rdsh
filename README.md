# rdsh

A lightweight CLI tool for interacting with the [Real-Debrid](https://real-debrid.com) API.

## Prerequisites

- Python 3.11+
- Real-Debrid API token (available from [Real-Debrid API Settings](https://real-debrid.com/apitoken))

## Setup & Installation

### 1. Set Your API Token

Export your Real-Debrid API token as an environment variable:

```bash
export REAL_DEBRID_API_TOKEN="your-api-token-here"
```

### 2. Install

#### Option A: Using `uv tool` (Recommended)

```bash
uv tool install .
```

Or install in editable mode (so local code updates take effect automatically):

```bash
uv tool install --editable .
```

_Note: Make sure `~/.local/bin` is in your `$PATH`. You can run `uv tool update-shell` to handle this._

#### Option B: Using `pipx`

```bash
pipx install .
```

#### Option C: Virtual Environment / `pip`

```bash
pip install -e .
```

---

## Usage

### Direct Inputs (Recommended)

When adding links or torrents, `rdsh` adds them to your Real-Debrid account and immediately prints a summary of your account's **in-progress downloads** and **failed downloads count**, without blocking or waiting for downloads to complete:

```bash
# Unrestrict a hosted link
rdsh "https://example.com/file"

# Add a magnet link to account
rdsh "magnet:?xt=urn:btih:..."

# Add a local .torrent file
rdsh "/path/to/file.torrent"

# Process multiple mixed inputs sequentially
rdsh "https://example.com/file1" "magnet:?xt=..." "/path/to/file2.torrent"
```

---

### Subcommands

#### List Account Torrents (`list-torrents`)

List torrents associated with your Real-Debrid account:

```bash
# Basic rich-formatted list
rdsh list-torrents

# Output raw JSON instead
rdsh list-torrents --json

# Paginate and filter
rdsh list-torrents --page 2 --limit 20 --status downloaded
```

#### Inspect Torrent Details (`torrent-info`)

Display detailed JSON metadata for Real-Debrid internal torrent ID(s):

```bash
rdsh torrent-info <TORRENT_ID>
```

#### Dedupe Account Torrents (`dedupe-torrents`)

Delete duplicate torrents grouped by filename, keeping a downloaded item when one exists:

```bash
rdsh dedupe-torrents
```

---

## Development & Testing

Run tests with `pytest` using `uv`:

```bash
uv run pytest
```
