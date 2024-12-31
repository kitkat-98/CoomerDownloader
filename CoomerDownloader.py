import requests
import logging
import os, re
from tqdm import tqdm
import time

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
    HOST = 'https://coomer.su'

    def __init__(self, service, user_name, download_folder=''):
        self.service = service
        self.user_name = user_name
        self.logger = get_logger()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        })

        self.session.proxies = {
            'http': 'http://127.0.0.1:7897',  # 设置 HTTP 代理
            'https': 'http://127.0.0.1:7897'  # 设置 HTTPS 代理
        }
        self.page_url = f'{self.HOST}/{service}/user/{user_name}'
        self.post_url = f'{self.HOST}/api/v1/{service}/user/{user_name}/posts-legacy'
        self.download_folder = download_folder or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Download')
        self.download_folder = os.path.join(self.download_folder, self.user_name)
        os.makedirs(self.download_folder, exist_ok=True)

    def common_request(self, url, params=''):
        try:
            # 发送 GET 请求
            response = self.session.get(url, params=params)
            
            # 日志记录请求信息
            # self.logger.debug(f'url: {url}, params: {params}, response code: {response.status_code}, body: {response.text}')
            self.logger.debug(f'url: {url}, params: {params}, response code: {response.status_code}')

            # 如果状态码不是 200 或返回的内容为空，记录错误日志
            if response.status_code != 200 or not response.content:
                self.logger.error(f'url: {url}, params: {params}, request error, code: {response.status_code}, body: {response.text}')
                return {}, False

            # 返回解析后的 JSON 数据和成功状态
            return response.json(), True

        except requests.exceptions.RequestException as e:
            # 捕获请求异常并记录错误日志
            self.logger.error(f"Request failed for url: {url}, params: {params}, error: {str(e)}")
            return {}, False

    def download_video_with_retry_and_resume(
        self, url, save_path, chunk_size=1 * 1024 * 1024, max_retries=5, retry_delay=2
    ):
        retries = 0
        while retries < max_retries:
            try:
                # 获取总文件大小
                response = self.session.head(url, timeout=10)
                response.raise_for_status()
                total_size = int(response.headers.get("content-length", 0))

                # 每次重试时重新计算已下载文件大小
                downloaded_size = 0
                if os.path.exists(save_path):
                    downloaded_size = os.path.getsize(save_path)

                # 检查是否已经下载完成
                if downloaded_size == total_size:
                    self.logger.info(f"文件 '{save_path}' 已经完整下载，跳过下载。")
                    return

                # 设置 HTTP Range 请求头，支持断点续传
                headers = {"Range": f"bytes={downloaded_size}-"}
                with tqdm(
                    total=total_size,
                    unit="B",
                    unit_scale=True,
                    desc="下载进度",
                    initial=downloaded_size,
                ) as pbar:
                    with open(save_path, "ab") as file:  # 使用 'ab' 模式追加写入
                        response = self.session.get(url, headers=headers, stream=True, timeout=30)
                        response.raise_for_status()

                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                file.write(chunk)
                                pbar.update(len(chunk))  # 更新进度条

                self.logger.info("\n下载完成!")
                return  # 下载成功后退出函数

            except requests.exceptions.RequestException as e:
                retries += 1
                self.logger.error(f"\n下载失败: {e}. 第 {retries} 次重试...")
                time.sleep(retry_delay)

        self.logger.error(f"\n{url} 下载失败，已达到最大重试次数。")

    def get_video_post(self):
        post_combination = {'results': [], 'result_attachments': [], 'result_is_image': []}

        page_res, is_pass = self.common_request(self.post_url)
        video_count = page_res.get('props').get('count')
        self.logger.info(f'Artist: {self.user_name}, service: {self.service}')
        self.logger.info(f'Post count: {video_count}')
        # self.logger.info(page_res)

        for i in range(0, video_count//50 + 1):
            res, is_pass = self.common_request(self.post_url, params={'o': 50*i})
            post_combination['results'] += res.get('results')
            post_combination['result_attachments'] += res.get('result_attachments')
            post_combination['result_is_image'] += res.get('result_is_image')

        assert len(post_combination['results']) == video_count, "list length is not equal to expected video count"

        skip_post = 0
        for i in range(video_count):
            is_image = post_combination.get('result_is_image')[i]
            # self.logger.info(f'video {i} is image: {is_image}')
            self.logger.info('\n' + '-*-'*50)
            if not is_image: 
                title = post_combination.get('results')[i].get('title') or post_combination.get('results')[i].get('substring')
                self.logger.info(f'video title: {title}')
                url = post_combination.get('result_attachments')[i][0].get('server') + '/data' + post_combination.get('result_attachments')[i][0].get('path')
                self.logger.info(f'video url: {url}')
                self.download_video_with_retry_and_resume(url, os.path.join(self.download_folder, f'{title}.mp4'))
            else:
                self.logger.info(f'Image, skip {i}')
                skip_post += 1
        self.logger.info('下载完成！！！')

def parse_url():

    url = input('请输入Coomer主页链接: ')
    # 使用正则表达式匹配 URL 中的 service 和 user_name
    match = re.match(r'https://coomer\.su/([a-zA-Z0-9]+)/user/([a-zA-Z0-9]+)', url)
    
    if match:
        service = match.group(1)  # 提取 service 部分
        user_name = match.group(2)  # 提取 user_name 部分
        return service, user_name
    else:
        print("URL 格式不正确")
        return None, None

if __name__ == '__main__':
    service, user_name = parse_url()
    downloader = CoomerDownloader(service=service, user_name=user_name)
    downloader.get_video_post()












