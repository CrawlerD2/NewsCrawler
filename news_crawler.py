import os
import time
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# MongoDB配置
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://newscrrawler:qwe123@crrawlercluster.eencizs.mongodb.net/?retryWrites=true&w=majority&appName=CrrawlerCluster")
DB_NAME = "mydatabase"
COLLECTION_NAME = "read"

# 请求头伪装
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}


def init_db():
    """初始化MongoDB连接"""
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    return db[COLLECTION_NAME]


def fetch_baidu_hot():
    """抓取百度热榜"""
    url = "https://top.baidu.com/board?tab=realtime"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select('.category-wrap_iQLoo')
        results = []
        for item in items[:10]:  # 取前10条
            title = item.select_one('.c-single-text-ellipsis').text.strip()
            link = item.select_one('a')['href']
            results.append({"source": "百度", "title": title, "link": link})
        return results
    except Exception as e:
        print(f"百度热榜抓取失败: {str(e)}")
        return []


# def fetch_weibo_hot():
#     url = "https://s.weibo.com/top/summary"
#     try:
#         options = Options()
#         options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
#         # 如果需要代理，取消注释以下行
#         # options.add_argument("--proxy-server=http://your_proxy_server:port")
#
#         driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
#         driver.get(url)
#         time.sleep(15)  # 等待页面加载完成
#
#         soup = BeautifulSoup(driver.page_source, 'html.parser')
#         items = soup.select('tr[action-type="hover"]')
#         if not items:
#             print("未找到符合条件的元素，可能是网页结构发生变化或被反爬虫限制。")
#             driver.quit()
#             return []
#
#         results = []
#         for item in items[:10]:
#             title = item.select_one('a').text.strip()
#             link = "https://s.weibo.com" + item.select_one('a')['href']
#             results.append({"source": "微博", "title": title, "link": link})
#
#         driver.quit()
#         return results
#     except Exception as e:
#         print(f"微博热搜抓取失败: {str(e)}")
#         return []


def fetch_zhihu_hot():
    """抓取知乎热榜"""
    url = "https://www.zhihu.com/billboard"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select('.HotList-item')
        results = []
        for item in items[:10]:
            title = item.select_one('.HotList-itemTitle').text.strip()
            link = item.select_one('a')['href']
            results.append({"source": "知乎", "title": title, "link": link})
        return results
    except Exception as e:
        print(f"知乎热榜抓取失败: {str(e)}")
        return []


def save_to_mongo(data):
    """保存到数据库"""
    if not data:
        return
    collection = init_db()
    try:
        collection.insert_many(data)
        print(f"成功保存{len(data)}条数据")
    except Exception as e:
        print(f"数据库写入失败: {str(e)}")


def main():
    # 抓取所有平台数据
    all_data = []
    all_data.extend(fetch_baidu_hot())
    # all_data.extend(fetch_weibo_hot())
    all_data.extend(fetch_zhihu_hot())

    # 去重（避免同一新闻多次存储）
    unique_data = {item["title"]: item for item in all_data}.values()
    save_to_mongo(list(unique_data))


if __name__ == "__main__":
    main()