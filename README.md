# CoomerDownloader:

A CLI downloader for coomer.

## Requirement:

requests, tqdm
```
pip install requests tqdm
```

## How To Use
1. Before running script, remember to setup proxies if you cannot access coomer, I use Clash so the port is 7897, if you are using different ports, just modify below codes.
```
        self.session.proxies = {
            'http': 'http://127.0.0.1:7897',  # 设置 HTTP 代理
            'https': 'http://127.0.0.1:7897'  # 设置 HTTPS 代理
        }
```

2. launch script in terminal and input URL of artist (eg: https://coomer.su/onlyfans/user/xxx), it only has been tested on onlyfans service, maybe it does not work well on fansly🤣.
```
python3 CoomerDownloader.py 
请输入Coomer主页链接: https://coomer.su/onlyfans/user/xxx
```