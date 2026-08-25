# rdsh

A lightweight CLI tool for interacting with the [Real-Debrid](https://real-debrid.com) API.

## Features

- **Direct Link Resolution**: Unrestrict hosted URLs, magnet links, and local `.torrent` files directly.
- **Automated Torrent Flow**: Waits for file selection, selects all files, polls until download completes, and returns unrestricted direct links.
- **Account & Torrent Management**: List account torrents and inspect torrent details in JSON format.
- **Media Player Integration**: Stream magnet links directly in `mpv`.

## Prerequisites

- Python 3.11+
- Real-Debrid API token (available from [Real-Debrid API Settings](https://real-debrid.com/apitoken))
- Optional: `mpv` (for streaming media directly)

## Setup & Installation

### 1. Set Your API Token

Export your Real-Debrid API token as an environment variable:

```bash
export REAL_DEBRID_API_TOKEN="your-api-token-here"
```

To make this persistent across terminal sessions, add the export to your shell configuration (e.g., `~/.bashrc` or `~/.zshrc`).

### 2. Install the Package

#### Using `uv` (recommended)

```bash
uv pip install -e .
```

#### Using `pip`

```bash
pip install -e .
```

Once installed, the `rdsh` CLI tool will be available globally in your Python environment.

---

## Usage

### Positional Inputs (Quick Usage)

Pass URLs, magnet links, or `.torrent` file paths directly to `rdsh`:

```bash
# Unrestrict a hosted link
rdsh "https://example.com/file"

# Add a magnet link and output direct links
rdsh "magnet:?xt=urn:btih:..."

# Add a local .torrent file
rdsh "/path/to/file.torrent"

# Process multiple inputs sequentially
rdsh "https://example.com/file1" "magnet:?xt=..." "/path/to/file2.torrent"
```

### Subcommands

#### `unrestrict`
Unrestrict hosted links, magnet URIs, or `.torrent` files:
```bash
rdsh unrestrict "https://example.com/file1" "https://example.com/file2"
```

#### `add-magnet`
Add magnet link(s) to Real-Debrid and resolve direct download URLs:
```bash
rdsh add-magnet "magnet:?xt=urn:btih:..."
```

#### `add-torrent`
Upload `.torrent` file(s) and resolve direct download URLs:
```bash
rdsh add-torrent /path/to/file1.torrent /path/to/file2.torrent
```

#### `mpv`
Add a magnet link and stream the unrestricted direct link directly in `mpv`:
```bash
rdsh mpv "magnet:?xt=urn:btih:..."
```

#### `torrent-info`
Display detailed JSON metadata for Real-Debrid torrent ID(s):
```bash
rdsh torrent-info <TORRENT_ID>
```

#### `list-torrents`
List torrents on your Real-Debrid account:
```bash
# Basic list
rdsh list-torrents

# Paginate and filter
rdsh list-torrents --page 2 --limit 20 --status downloaded
```

---

## Development & Testing

Run tests with `pytest` using `uv`:

```bash
uv run pytest
```
