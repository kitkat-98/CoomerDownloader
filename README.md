# Coomer Downloader

A powerful and efficient command-line tool to download all videos from a Coomer user's page.

## Features

- **Concurrent Operations**: Utilizes threading to both fetch post details and download files simultaneously, significantly speeding up the entire process.
- **Robust & Resilient**: Automatically retries failed downloads and resumes partially downloaded files.
- **Highly Configurable**: Use command-line arguments to specify:
  - Output directory (supports `~` for home directory).
  - HTTP/HTTPS proxy.
  - Number of concurrent workers.
- **User-Friendly Interface**: Provides clear, multi-level progress bars for a great user experience.
- **Smart Filename Generation**: Creates organized and readable filenames from the post's date, ID, and a truncated title.

## Requirements

Install the required Python packages using pip:

```bash
python3 -m pip install requests tqdm
```

## Usage

To see all available options, run:
```bash
python3 CoomerDownloader.py -h
```

Which will display:
```
usage: CoomerDownloader.py [-h] [-o OUTPUT] [-p PROXY] [-w WORKERS] url

A CLI downloader for coomer.

Example:
  python3 CoomerDownloader.py "https://coomer.su/onlyfans/user/npxvip" -o "~/Downloads/coomer" -p "http://127.0.0.1:7897" -w 10

positional arguments:
  url                   The Coomer user page URL. e.g.
                        https://coomer.su/onlyfans/user/npxvip

options:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        Directory to save downloads to. Defaults to
                        ./Download/<user_name>
  -p PROXY, --proxy PROXY
                        Proxy to use for requests. e.g.
                        http://127.0.0.1:7897
  -w WORKERS, --workers WORKERS
                        Number of concurrent workers. Default: 5
```

### Full Example

Download all content from a user into a specific folder with 10 concurrent threads, using a proxy:

```bash
python3 CoomerDownloader.py "https://coomer.su/onlyfans/user/npxvip" --output "~/Downloads/MyCoomer" --proxy "http://127.0.0.1:7897" --workers 10
```
