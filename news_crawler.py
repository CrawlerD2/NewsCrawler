import requests
import pandas as pd
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.options import Options
import time
from bs4 import BeautifulSoup
import os
import re
from pymongo import MongoClient
from datetime import datetime
import logging
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# MongoDB配置
MONGO_URI = os.getenv("MONGO_URI",
                      "mongodb+srv://newscrrawler:qwe123@crrawlercluster.eencizs.mongodb.net/?retryWrites=true&w=majority&appName=CrrawlerCluster")
DB_NAME = "mydatabase"
COLLECTION_NAME = "read"

def connect_to_mongodb():
    """连接MongoDB数据库并返回集合对象"""
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        logging.info("成功连接到MongoDB")
        return collection
    except Exception as e:
        logging.error(f"连接MongoDB失败: {e}")
        return None

def save_to_mongodb(data, collection):
    """保存数据到MongoDB"""
    if collection is None:
        logging.error("无法保存到MongoDB: 连接无效")
        return False

    try:
        # 添加时间戳
        for item in data:
            item['created_at'] = datetime.now()
            item['updated_at'] = datetime.now()

        # 插入数据
        result = collection.insert_many(data)
        logging.info(f"成功插入 {len(result.inserted_ids)} 条数据到MongoDB")
        return True
    except Exception as e:
        logging.error(f"保存到MongoDB失败: {e}")
        return False

def get_baidu_hotsearch_data():
    """获取百度热搜数据"""
    api_url = "https://top.baidu.com/api/board?tab=realtime"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://top.baidu.com/board?tab=realtime'
    }
    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"获取热搜数据失败: {e}")
        return None

def setup_driver():
    """设置并返回WebDriver"""
    edge_options = Options()
    edge_options.add_argument("--headless")
    edge_options.add_argument("--disable-gpu")
    edge_options.add_argument("--no-sandbox")  # 重要：在Linux环境中需要
    edge_options.add_argument("--disable-dev-shm-usage")  # 重要：在Docker/CI环境中需要
    edge_options.add_argument("--remote-debugging-port=9222")
    edge_options.add_argument("--disable-blink-features=AutomationControlled")
    edge_options.add_argument("--disable-extensions")
    edge_options.add_argument("--disable-popup-blocking")
    edge_options.add_argument("--disable-notifications")
    edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    edge_options.add_experimental_option('useAutomationExtension', False)

    # 在GitHub Actions中使用特定路径
    if os.getenv('GITHUB_ACTIONS') == 'true':
        driver_path = "/usr/bin/msedgedriver"
    else:
        driver_path = find_edge_driver()
    
    if not driver_path:
        raise Exception("未找到Edge浏览器驱动")

    service = Service(executable_path=driver_path)
    try:
        driver = webdriver.Edge(service=service, options=edge_options)
        
        # 反检测设置
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.navigator.chrome = {runtime: {}, etc: {}};
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            """
        })
        
        logging.info("WebDriver初始化成功")
        return driver
    except Exception as e:
        logging.error(f"WebDriver初始化失败: {e}")
        raise

def find_edge_driver():
    """尝试在常见位置查找Edge驱动"""
    possible_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedgedriver.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedgedriver.exe",
        r"/usr/bin/msedgedriver",  # Linux路径
        r"/usr/local/bin/msedgedriver",  # Linux路径
        r"C:\edgedriver\msedgedriver.exe",
        os.path.expanduser(r"~\AppData\Local\Microsoft\Edge SxS\Application\msedgedriver.exe"),
        os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\Application\msedgedriver.exe")
    ]

    for path in possible_paths:
        if os.path.exists(path):
            logging.info(f"找到Edge驱动: {path}")
            return path
    logging.warning("未找到Edge驱动")
    return None

def extract_text_from_element(element):
    """从HTML元素中提取文本（包括图片alt文本）"""
    if not element:
        return ""

    try:
        # 创建元素的副本，避免修改原始元素
        element_copy = BeautifulSoup(str(element), 'html.parser')

        # 处理图片的alt文本
        for img in element_copy.find_all('img'):
            if img.get('alt'):
                img.insert_after(f"[图片: {img['alt']}]")

        # 处理视频
        for video in element_copy.find_all('video'):
            if video.get('title'):
                video.insert_after(f"[视频: {video['title']}]")
            else:
                video.insert_after("[视频内容]")

        # 处理iframe嵌入内容
        for iframe in element_copy.find_all('iframe'):
            if iframe.get('title'):
                iframe.insert_after(f"[嵌入内容: {iframe['title']}]")
            else:
                iframe.insert_after("[嵌入内容]")

        # 获取处理后的文本
        text = element_copy.get_text(separator='\n', strip=True)

        # 清理多余的空白和换行
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()
    except Exception as e:
        logging.error(f"提取文本失败: {e}")
        return ""

def get_news_detail(search_url):
    """获取新闻详情（标题和内容）"""
    driver = None
    try:
        logging.info(f"开始获取新闻详情: {search_url}")
        driver = setup_driver()
        
        # 设置页面加载超时
        driver.set_page_load_timeout(30)
        
        driver.get(search_url)
        logging.info("已加载搜索页面")

        # 等待页面加载
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        time.sleep(2)

        # 处理可能的弹窗
        try:
            driver.execute_script('window.scrollBy(0, 100)')
            close_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.close-btn, span.c-icon-close, button.close"))
            )
            close_btn.click()
            time.sleep(1)
            logging.info("已关闭弹窗")
        except:
            pass

        # 点击第一个搜索结果
        first_result = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h3.c-title a"))
        )
        first_result_url = first_result.get_attribute('href')
        logging.info(f"找到第一条结果: {first_result_url}")
        
        # 访问新闻页面
        driver.get(first_result_url)
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        time.sleep(3)

        # 滚动页面以加载懒加载内容
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2)")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, 0)")
        time.sleep(1)

        # 获取页面源码
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # 获取新闻标题
        news_title = get_news_title(soup)
        
        # 获取新闻内容
        news_content = get_news_content(soup)
        
        # 清理内容
        news_content = clean_text(news_content)

        logging.info(f"成功获取新闻: {news_title[:50]}...")
        return news_title, news_content

    except Exception as e:
        logging.error(f"获取新闻详情失败: {str(e)}")
        return "获取失败", "获取失败"
    finally:
        if driver:
            driver.quit()

def get_news_title(soup):
    """从BeautifulSoup对象中提取新闻标题"""
    title_selectors = [
        'h1', 'div.article-title', 'div.title', 'h1.title',
        'div.article-header h1', 'div.content-title', 'div.article h1',
        'div._2oTsX > div.sKHSJ', 'div.article-head h1',
        'header h1', 'article h1', 'main h1', 'h1.headline',
        'title', 'meta[property="og:title"]', 'meta[name="title"]'
    ]

    for selector in title_selectors:
        try:
            if selector.startswith('meta'):
                title_element = soup.select_one(selector)
                if title_element and title_element.get('content', '').strip():
                    return title_element['content'].strip()
            else:
                title_element = soup.select_one(selector)
                if title_element and title_element.text.strip():
                    return title_element.text.strip()
        except:
            continue
    
    # 如果以上选择器都失败，尝试从URL提取
    return "未获取到新闻标题"

def get_news_content(soup):
    """从BeautifulSoup对象中提取新闻内容"""
    content_containers = [
        'article', 'div.article-content', 'div.content',
        'div.article-text', 'div.article-body', 'div.article-main',
        'div.article', 'div._18p7x', 'div.content-article',
        'div.article-detail', 'main', 'div.post-content',
        'div.entry-content', 'div.text', 'div.story-content',
        'div.news-content', 'div.content-wrapper'
    ]

    best_content = ""
    max_length = 0

    for container in content_containers:
        try:
            content_element = soup.select_one(container)
            if content_element:
                content_text = extract_text_from_element(content_element)
                if len(content_text) > max_length:
                    max_length = len(content_text)
                    best_content = content_text
        except:
            continue

    if not best_content or len(best_content) < 200:
        body_text = extract_text_from_element(soup.body)
        if len(body_text) > len(best_content):
            best_content = body_text

    return best_content if best_content else "未获取到新闻内容"

def clean_text(text):
    """清理文本内容"""
    if not text:
        return text

    # 移除多余的空白字符
    text = re.sub(r'\s+', ' ', text)

    # 移除常见的版权声明、免责声明等
    patterns = [
        r'版权声明.*$', r'免责声明.*$', r'本文来源.*$',
        r'编辑.*$', r'记者.*$', r'点击进入专题.*$',
        r'相关报道.*$', r'责任编辑.*$', r'作者.*$',
        r'声明：.*$', r'【.*】$'
    ]

    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # 移除开头和结尾的非文字内容
    text = text.strip()
    text = re.sub(r'^[^a-zA-Z0-9\u4e00-\u9fa5]+', '', text)
    text = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]+$', '', text)

    return text.strip()

def parse_hotsearch_data(data):
    """解析热搜数据"""
    if not data or "data" not in data or "cards" not in data["data"]:
        logging.warning("热搜数据格式不正确")
        return []

    try:
        hotsearch_list = data["data"]["cards"][0].get("content", [])
        top_content = data["data"]["cards"][0].get("topContent", [])
        parsed_data = []
        
        for idx, item in enumerate((top_content + hotsearch_list)[:3], 1):
            search_url = item.get("url", "")
            if not search_url.startswith('http'):
                search_url = f"https://www.baidu.com/s?wd={item.get('word', '')}"

            logging.info(f"处理第 {idx} 条热搜: {item.get('word', '')}")
            news_title, news_content = get_news_detail(search_url)

            parsed_data.append({
                "hotsearch_title": item.get("word", ""),
                "hotsearch_url": search_url,
                "hot_index": item.get("hotScore", ""),
                "hotsearch_desc": item.get("desc", ""),
                "image_url": item.get("img", ""),
                "is_top": "是" if item in top_content else "否",
                "news_title": news_title,
                "news_content": news_content[:10000],  # 限制内容长度
                "source": "百度热搜",
                "crawl_time": datetime.now()
            })

            time.sleep(3)  # 增加间隔避免被封

        return parsed_data
    except Exception as e:
        logging.error(f"解析热搜数据失败: {e}")
        return []

if __name__ == "__main__":
    try:
        logging.info("爬虫程序启动")
        
        # 连接MongoDB
        collection = connect_to_mongodb()

        # 获取并处理数据
        logging.info("开始获取百度热搜数据...")
        hotsearch_data = get_baidu_hotsearch_data()

        if hotsearch_data:
            logging.info("开始解析热搜数据...")
            parsed_data = parse_hotsearch_data(hotsearch_data)

            if parsed_data:
                logging.info(f"成功解析 {len(parsed_data)} 条数据")
                
                # 保存到MongoDB
                if collection is not None:
                    save_to_mongodb(parsed_data, collection)
                else:
                    logging.error("MongoDB连接失败，仅打印数据")
                    for item in parsed_data:
                        logging.info(f"热搜标题: {item['hotsearch_title']}")
            else:
                logging.warning("未解析到有效数据")
        else:
            logging.error("未获取到百度热搜数据")
            
    except Exception as e:
        logging.error(f"程序运行出错: {e}")
    finally:
        logging.info("爬虫程序结束")
