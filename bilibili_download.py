import json
import os
from copy import deepcopy
import subprocess

from requests_html import *
import urllib3

urllib3.disable_warnings()

# 请求头
HEADERS = {
    # 用户代理
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/"
}


def get(url: str, script: str = None, proxies: dict = None) -> tuple[HTML, any]:
    """
    进行请求并渲染结果
    :param url: 请求地址
    :param script: 是否执行JavaScript脚本
    :param proxies: 是否使用代理
    :return: 渲染后的HTML，以及JavaScript执行结果
    """
    # HTMLSession Object
    request = HTMLSession()
    # 创建请求
    response = request.get(url, proxies=proxies)
    # 获取请求后的HTMl
    html: HTML = response.html
    # 进行chromium渲染页面，超时时间1小时，并执行JavaScript脚本
    result = html.render(timeout=3600.0, script=script)
    return html, result


def process_html(html: HTML) -> list:
    """
    处理HTML页面
    :param html: HTML页面
    :return: 处理后的结果
    """
    # 获取视频div
    l_items = html.find("div.l-item")
    # 保存结果
    result = []
    for item in l_items:
        # 对标签进行搜索，获取需要的数据
        a = item.find("a.title", first=True).attrs
        link = f"https:{a['href']}"
        title = a["title"]
        desc = item.find("div.v-desc", first=True).text
        up_info = item.find("div.up-info", first=True).find("a", first=True).attrs
        # 封装结果
        obj = {
            "视频链接": link,
            "标题": title,
            "描述": desc,
            "up": up_info["title"],
            "up链接": f"http:{up_info['href']}"
        }
        # 添加结果
        result.append(obj)
    # 返回结果
    return result


def downloadVideo(url: str, bv: str) -> tuple[str, str, int]:
    """
    获取视频，音频链接
    :param url: 视频链接
    :param bv: 视频名称
    """
    session = requests.session()
    # 获取视频信息
    res = session.get(url=url, headers=HEADERS, verify=False)
    _element = etree.HTML(res.content)
    # 提取视频json字符串
    video_play_info = str(_element.xpath('/html/head/script[4]/text()')[0].encode('utf-8').decode('utf-8'))[20:]
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
    if not os.path.exists(bv):
        os.mkdir(bv)
    # 下载视频文件
    video_path = f"{bv}/{bv}_Video.mp4"
    fileDownload(video_url, video_path, session)
    audio_path = ""
    # 下载音频文件
    if flag == 0:
        audio_url = video_json['data']['dash']['audio'][0]['baseUrl']
        audio_path = f"{bv}/{bv}_Audio.mp3"
        fileDownload(audio_url, audio_path, session)
    return video_path, audio_path, flag


def fileDownload(url, name, session):
    # 添加请求头键值对,写上 refered:请求来源
    # 发送option请求服务器分配资源
    session.options(url=url, verify=False)
    # 指定每次下载1M的数据
    begin = 0
    end = 1024 * 10 * 512 - 1
    flag = 0
    # 深拷贝请求头
    headers = deepcopy(HEADERS)
    while True:
        # 添加请求头键值对,写上 range:请求字节范围
        headers.update({'Range': 'bytes=' + str(begin) + '-' + str(end)})
        # 获取视频分片
        res = session.get(url=url, headers=headers, verify=False)
        if res.status_code != 416:
            # 响应码不为为416时有数据
            begin = end + 1
            end = end + 1024 * 512
        else:
            headers.update({'Range': str(end + 1) + '-'})
            res = session.get(url=url, headers=headers, verify=False)
            flag = 1
        with open(name.encode("utf-8").decode("utf-8"), 'ab') as fp:
            fp.write(res.content)
            fp.flush()
        if flag == 1:
            fp.close()
            break


def merge(video_path: str, audio_path: str, name):
    subprocess.call(("ffmpeg -i " + video_path + " -i " + audio_path + " -c copy " + f"{name}.mp4").encode("utf-8").decode("utf-8"), shell=True)
    os.remove(video_path)
    os.remove(audio_path)
    os.removedirs(name)


def main():
    try:
        """
        注释可以获取一页的数据
        """
        # 爬取页面信息
        html, result = get(f"https://www.bilibili.com/v/kichiku/guide/?spm_id_from=333.5.b_6b696368696b755f6775696465.3#/all/click/0/1/2022-01-28,2022-02-04")
        # 处理第一个页面
        data = process_html(html)
        print(data)
        # # 获取视频链接，并且下载第二个视频
        # url = data[1]["视频链接"]
        # 获取BV号
        # url = "https://www.bilibili.com/video/BV1p3411E7bi?spm_id_from=333.6.0.0"
        # bv = url[url.rfind("/") + 1:]
        # video, audio, flag = downloadVideo(url, bv)
        # if flag == 0:
        #     merge(video, audio, bv)
    except Exception as e:
        print(f"request error : {e}")


if __name__ == '__main__':
    main()
