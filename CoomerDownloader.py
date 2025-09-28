import requests
import logging
import os, re, sys, json, argparse
from tqdm import tqdm
import time
from concurrent.futures import ThreadPoolExecutor

def get_logger():
    # 初始化 logger
    logger = logging.getLogger(__name__)  # 使用当前模块名称作为 logger 名称
    logger.setLevel(logging.DEBUG)  # 设置日志级别

    # 创建一个控制台处理器
    console_handler = logging.StreamHandler()

    # 创建一个格式化器，并将其应用到处理器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)

    # 将控制台处理器添加到 logger
    logger.addHandler(console_handler)

    return logger

class CoomerDownloader(object):
    """A CLI downloader for coomer"""

    def __init__(self, host, service, user_name, download_folder='', proxy=None, workers=5):
        self.host = f'https://{host}'
        self.service = service
        self.user_name = user_name
        self.workers = workers
        self.post_list = []
        self.logger = get_logger()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/css'
        })

        if proxy:
            self.logger.info(f"Using proxy: {proxy}")
            self.session.proxies = {
                'http': proxy,
                'https': proxy
            }
        
        self.page_url = f'{self.host}/{self.service}/user/{self.user_name}'
        self.profile_url = f'{self.host}/api/v1/{self.service}/user/{self.user_name}/profile'
        self.fetch_post_url = f'{self.host}/api/v1/{self.service}/user/{self.user_name}/posts'

        # Determine the base download folder, expanding the user-provided path
        if download_folder:
            base_folder = os.path.expanduser(download_folder)
        else:
            base_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Download')

        # Create the final user-specific folder
        self.download_folder = os.path.join(base_folder, self.user_name)
        os.makedirs(self.download_folder, exist_ok=True)

    def common_request(self, url, params=''):
        try:
            # 发送 GET 请求
            response = self.session.get(url, params=params)
            
            self.logger.debug(f'url: {url}, params: {params}, response code: {response.status_code}')

            if response.status_code != 200 or not response.content:
                self.logger.error(f'url: {url}, params: {params}, request error, code: {response.status_code}, body: {response.text}')
                return {}, False

            try:
                return response.json(), True
            except json.JSONDecodeError:
                cleaned = response.text.strip()
                try:
                    return json.loads(cleaned), True
                except json.JSONDecodeError:
                    self.logger.error(f'JSON decode failed after cleaning: {cleaned[:200]}...')
                    return {}, False

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed for url: {url}, params: {params}, error: {str(e)}")
            return {}, False

    def download_video_with_retry_and_resume(
        self, task, chunk_size=1 * 1024 * 1024, max_retries=5, retry_delay=2
    ):
        url = task['url']
        save_path = task['save_path']
        position = task['position']
        title = task['title']

        retries = 0
        while retries < max_retries:
            try:
                response = self.session.head(url, timeout=10)
                response.raise_for_status()
                total_size = int(response.headers.get("content-length", 0))

                downloaded_size = 0
                if os.path.exists(save_path):
                    downloaded_size = os.path.getsize(save_path)

                if downloaded_size == total_size and total_size != 0:
                    return

                headers = {"Range": f"bytes={downloaded_size}-"}
                with tqdm(
                    total=total_size,
                    unit="B",
                    unit_scale=True,
                    desc=title,
                    initial=downloaded_size,
                    position=position,
                    leave=False
                ) as pbar:
                    with open(save_path, "ab") as file:
                        response = self.session.get(url, headers=headers, stream=True, timeout=30)
                        response.raise_for_status()

                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                file.write(chunk)
                                pbar.update(len(chunk))
                return

            except requests.exceptions.RequestException as e:
                retries += 1
                self.logger.error(f"\n下载失败: {e}. 第 {retries} 次重试...")
                time.sleep(retry_delay)

        self.logger.error(f"\n{title} 下载失败，已达到最大重试次数。")

    def _fetch_post_details(self, post):
        """Helper function to fetch details for a single post."""
        post_id = post.get('id')
        post_page_url = f'{self.host}/api/v1/{self.service}/user/{self.user_name}/post/{post_id}'
        post_page, is_pass = self.common_request(post_page_url)
        if not is_pass:
            return None
        return post_page

    def get_post_list(self):
        page_res, is_pass = self.common_request(self.profile_url)
        post_count = page_res.get('post_count', 0)
        self.logger.info(f'Artist: {self.user_name}, service: {self.service}')
        self.logger.info(f'Post count: {post_count}')

        for i in range(0, post_count//50 + 1):
            self.logger.info(f'Fetching page {i+1}')
            res, is_pass = self.common_request(self.fetch_post_url, params={'o': 50*i})
            self.post_list += res
            time.sleep(0.3)

        # assert len(self.post_list) == post_count, "post list length is not equal to expected video count"

        self.logger.info('Concurrently fetching post details...')
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            post_details_list = list(executor.map(self._fetch_post_details, self.post_list))

        self.logger.info('\nCollecting video tasks from fetched details...')
        tasks = []
        for post_page in post_details_list:
            if not post_page:
                continue

            title = post_page.get('post', {}).get('title', 'untitled')
            published_date = post_page.get('post', {}).get('published', 'nodate')
            post_id = post_page.get('post', {}).get('id', 'no-id')

            videos = post_page.get('videos')
            if not videos:
                continue
            
            videos = [f'{v.get("server")}/data{v.get("path")}' for v in videos if v.get('path')]
            for v_url in videos:
                clean_title = re.sub(r'[\\/*?:"<>|]', "", title).replace('\n', ' ').strip()
                file_name_suffix = v_url.split('/')[-1]

                date_only = published_date.split('T')[0]
                truncated_title = clean_title[:50]
                final_filename = f'{date_only}_{post_id}_{truncated_title}_{file_name_suffix}'
                
                task = {
                    'url': v_url,
                    'save_path': os.path.join(self.download_folder, final_filename),
                    'title': final_filename[:40] + '...' if len(final_filename) > 40 else final_filename,
                    'position': 0
                }
                tasks.append(task)

        self.logger.info(f'\nFound {len(tasks)} videos to download. Starting concurrent download...')

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            for i, task in enumerate(tasks):
                task['position'] = i
            
            list(tqdm(executor.map(self.download_video_with_retry_and_resume, tasks), total=len(tasks), desc="Overall Progress"))

        self.logger.info('全部下载完成！！！')

def main():
    description = '''A CLI downloader for coomer.

Example:
  python3 CoomerDownloader.py "https://coomer.su/onlyfans/user/npxvip" -o "~/Downloads/coomer" -p "http://127.0.0.1:7897" -w 10
'''
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("url", help="The Coomer user page URL. e.g. https://coomer.su/onlyfans/user/npxvip")
    parser.add_argument("-o", "--output", default=None, help="Directory to save downloads to. Defaults to ./Download/<user_name>")
    parser.add_argument("-p", "--proxy", default=None, help="Proxy to use for requests. e.g. http://127.0.0.1:7897")
    parser.add_argument("-w", "--workers", type=int, default=5, help="Number of concurrent workers. Default: 5")
    args = parser.parse_args()

    # 使用正则表达式匹配 URL 中的 service 和 user_name
    match = re.match(r'https://(coomer\.[a-z.]+)/([a-zA-Z0-9]+)/user/([a-zA-Z0-9]+)', args.url)
    
    if not match:
        print(f"URL 格式不正确: {args.url}")
        print("示例: https://coomer.su/onlyfans/user/npxvip")
        sys.exit(1)

    host = match.group(1)      # 提取 host 部分
    service = match.group(2)   # 提取 service 部分
    user_name = match.group(3)   # 提取 user_name 部分

    downloader = CoomerDownloader(
        host=host, 
        service=service, 
        user_name=user_name,
        download_folder=args.output,
        proxy=args.proxy,
        workers=args.workers
    )
    downloader.get_post_list()

if __name__ == '__main__':
    main()












