import json
import os
import subprocess
import urllib3
import argparse

from requests_html import *
from copy import deepcopy

urllib3.disable_warnings()

# 连接session
session = requests.Session()

# 请求头
HEADERS = {
    # 用户代理
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/"
}

session.headers = HEADERS


def get(url: str) -> HTML:
    """
    进行请求并渲染结果，这个函数主要是用来获取动态页面，例如使用JavaScript动态加载的页面
    :param url: 请求地址
    :return: 渲染后的HTML
    """
    # HTMLSession Object
    request = HTMLSession()
    # 创建请求
    response = request.get(url)
    # 获取请求后的HTMl
    html: HTML = response.html
    # 进行chromium渲染页面，超时时间1小时，并执行JavaScript脚本
    html.render(timeout=3600.0)
    return html


def process_dynamic_page(html: HTML) -> list:
    """
    处理动态HTML页面，提取所有的视频链接
    :param html: HTML页面
    :return: 处理后的结果
    """
    # 保存结果
    result = []
    links = html.absolute_links
    for link in links:
        if link.startswith("https://www.bilibili.com/video/"):
            result.append(link)
    return result


def get_video_info(url: str) -> tuple[str, str, str]:
    """
    获取视频，音频链接，视频名称信息
    :param url: 视频链接
    """
    # 获取视频信息
    res = session.get(url=url, verify=False)
    _element = etree.HTML(res.content)
    # 提取视频json字符串
    video_play_info = str(_element.xpath('/html/head/script[4]/text()')[0].encode('utf-8').decode('utf-8'))[20:]
    # 获取视频名称
    name = _element.xpath('//*[@id="viewbox_report"]/h1')[0].attrib["title"].replace(" ", "")
    # 视频链接信息
    video_json = json.loads(video_play_info)
    try:
        # 2018年以后的b站视频由.audio和.video组成 flag=0表示分为音频与视频
        video_url = video_json['data']['dash']['video'][0]['baseUrl']
        flag = 0
    except Exception as e:
        # 2018年以前的b站视频音频视频结合在一起,后缀为.flv flag=1表示只有视频
        print(e)
        video_url = video_json['data']['durl'][0]['url']
        flag = 1
    if not os.path.exists(name):
        os.mkdir(name)
    # 下载视频文件
    video_path = f"{name}/{name}_Video.mp4"
    fileDownload(video_url, video_path)
    audio_path = ""
    # 下载音频文件
    if flag == 0:
        audio_url = video_json['data']['dash']['audio'][0]['baseUrl']
        audio_path = f"{name}/{name}_Audio.mp3"
        fileDownload(audio_url, audio_path)
    return video_path, audio_path, name


def fileDownload(url, name):
    """
    进行文件下载
    """
    # 添加请求头键值对,写上 refered:请求来源
    # 发送option请求服务器分配资源
    session.options(url=url, verify=False)
    # 指定每次下载1M的数据
    begin = 0
    end = 1024 * 10 * 512 - 1
    # 拷贝请求头
    headers = deepcopy(HEADERS)
    while True:
        # 添加请求头键值对,写上 range:请求字节范围
        headers.update({'Range': 'bytes=' + str(begin) + '-' + str(end)})
        # 获取视频分片
        res = session.get(url=url, headers=headers, verify=False)
        code = res.status_code
        if code == 206:
            # 响应码为206时更新状态，对视频信息进行拼接
            begin = end + 1
            end = end + 1024 * 512
            with open(name.encode("utf-8").decode("utf-8"), 'ab') as fp:
                fp.write(res.content)
        else:
            break


def merge(video_path: str, audio_path: str, name):
    subprocess.call(("ffmpeg -i " + video_path + " -i " + audio_path + " -c copy " + f"{name}.mp4").encode("utf-8").decode("utf-8"), shell=True)
    os.remove(video_path)
    os.remove(audio_path)
    os.removedirs(name)


def download(url: str):
    """
    下载视频，
    """
    print(f"current url : {url}")
    merge(*get_video_info(url))


def multi_download(urls: list, pool_size: int = 10):
    """
    开启10个线程同时下载10个视频资源
    """
    print(f"总共有{len(urls)}个视频")
    with ThreadPoolExecutor(max_workers=pool_size) as pool:
        pool.map(download, urls)
    print("done")


def parse_args():
    parser = argparse.ArgumentParser(description="B站下载工具")
    parser.add_argument("-u", "--url", metavar="https://www.bilibili.com/videos/BVXXXXX", type=str, help="需要下载的URL")
    parser.add_argument("-s", "--urls", metavar="https://www.bilibili.com/videos/BVXXXXX1 https://www.bilibili.com/videos/BVXXXXX2", type=str, nargs="*", help="需要下载的URL")
    parser.add_argument("-p", "--page", metavar="https://www.bilibili.com/", type=str, help="需要下载的一页数据")
    parser.add_argument("-m", "--pages", metavar="https://www.bilibili.com/1 https://www.bilibili.com/2", type=str, nargs="*", help="需要下载的多页数据")
    parser.add_argument("-z", "--size", metavar="N", type=int, default=10, help="线程池大小")
    return parser.parse_args().__dict__


def main():
    """
    注释可以获取一页的数据
    """
    args = parse_args()
    if args["url"]:
        download(args["url"])
    if args["urls"]:
        multi_download(args["urls"])
    if args["page"]:
        multi_download(process_dynamic_page(get(args["page"])), args["size"])
    if args["pages"]:
        for page in args["pages"]:
            multi_download(process_dynamic_page(get(page)), args["size"])


if __name__ == '__main__':
    main()
