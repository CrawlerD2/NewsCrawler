# import os
# import re
# import time
# import logging
# from datetime import datetime
# from typing import Optional, Tuple, List, Dict

# import requests
# from bs4 import BeautifulSoup
# from pymongo import MongoClient
# from selenium import webdriver
# from selenium.webdriver.common.by import By
# from selenium.webdriver.edge.options import Options
# from selenium.webdriver.edge.service import Service
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.support.ui import WebDriverWait
# from readability import Document
# from webdriver_manager.microsoft import EdgeChromiumDriverManager

# # Configuration
# MONGO_URI = os.getenv("MONGO_URI",
#                       "mongodb+srv://newscrrawler:qwe123@crrawlercluster.eencizs.mongodb.net/?retryWrites=true&w=majority&appName=CrrawlerCluster")
# DB_NAME = "mydatabase"
# COLLECTION_READ = "read"
# COLLECTION_SUCC = "analyzed_succ"
# COLLECTION_FAIL = "analyzed_fail"

# HEADERS = {
#     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
#     'Referer': 'https://top.baidu.com/board?tab=realtime'
# }

# # Configure logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# def get_baidu_hotsearch_data() -> Optional[Dict]:
#     """Fetch Baidu hot search data"""
#     api_url = "https://top.baidu.com/api/board?tab=realtime"
#     try:
#         response = requests.get(api_url, headers=HEADERS)
#         response.raise_for_status()
#         return response.json()
#     except Exception as e:
#         logging.error(f"Failed to fetch hot search data: {e}")
#         return None


# def setup_driver() -> webdriver.Edge:
#     """Setup and return WebDriver instance"""
#     options = Options()
#     options.add_argument("--headless")
#     options.add_argument("--disable-gpu")
#     options.add_argument("--no-sandbox")
#     options.add_argument("--disable-dev-shm-usage")
#     options.add_argument(
#         "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

#     driver_path = EdgeChromiumDriverManager().install()
#     service = Service(driver_path)
#     driver = webdriver.Edge(service=service, options=options)

#     # Anti-detection
#     driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
#         "source": """
#             Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
#             Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
#         """
#     })
#     return driver


# def is_valid_webpage_link(href: str) -> bool:
#     """Check if a link is a valid external webpage"""
#     if not href:
#         return False
#     invalid_prefixes = [
#         "https://tieba.baidu.com",
#         "https://zhidao.baidu.com",
#         "https://baike.baidu.com",
#         "https://v.baidu.com",
#         "https://sp.baidu.com",
#         "https://image.baidu.com",
#         "https://video.baidu.com",
#         "https://wenku.baidu.com",
#         "https://map.baidu.com",
#         "https://events.baidu.com",
#         "https://new.baidu.com",
#         "https://voice.baidu.com",
#     ]
#     return not any(href.startswith(prefix) for prefix in invalid_prefixes)


# def wait_for_page_load(driver: webdriver.Edge, timeout: int = 10) -> None:
#     """Wait for page to load"""
#     try:
#         WebDriverWait(driver, timeout).until(
#             EC.presence_of_element_located((By.TAG_NAME, "body"))
#         )
#     except Exception as e:
#         logging.warning(f"Page load timeout: {e}")


# def scroll_to_bottom(driver: webdriver.Edge, scroll_pause_time: float = 1.0, max_scrolls: int = 10) -> None:
#     """Scroll to bottom of page to load lazy content"""
#     last_height = driver.execute_script("return document.body.scrollHeight")
#     for _ in range(max_scrolls):
#         driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
#         time.sleep(scroll_pause_time)
#         new_height = driver.execute_script("return document.body.scrollHeight")
#         if new_height == last_height:
#             break
#         last_height = new_height


# def extract_content_from_html(html: str) -> Tuple[str, str]:
#     """Extract title and content from HTML using readability"""
#     doc = Document(html)
#     title = doc.title()
#     summary_html = doc.summary()

#     soup = BeautifulSoup(summary_html, "html.parser")
#     content = soup.get_text(separator="\n", strip=True)

#     return title, content


# def get_first_valid_url(driver: webdriver.Edge, search_url: str) -> Optional[str]:
#     """Find first valid URL from search results"""
#     driver.get(search_url)
#     wait_for_page_load(driver)
#     time.sleep(3)

#     try:
#         web_tab = WebDriverWait(driver, 5).until(
#             EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[data-index="0"]')))
#         web_tab.click()
#         time.sleep(3)
#     except Exception:
#         pass

#     containers = driver.find_elements(By.CSS_SELECTOR, 'div.c-container, div.result')
#     for container in containers:
#         try:
#             a = container.find_element(By.CSS_SELECTOR, 'a[href]')
#             href = a.get_attribute('href')
#             if is_valid_webpage_link(href):
#                 return href
#         except Exception:
#             continue
#     return None


# def get_news_detail(search_url: str) -> Tuple[str, str]:
#     """Get news details (title and content) from a search URL"""
#     driver = None
#     try:
#         driver = setup_driver()
#         first_valid_url = get_first_valid_url(driver, search_url)

#         if not first_valid_url:
#             return "No valid link found", "No valid link found"

#         driver.get(first_valid_url)
#         wait_for_page_load(driver)
#         scroll_to_bottom(driver)

#         html = driver.page_source
#         return extract_content_from_html(html)
#     except Exception as e:
#         logging.error(f"Failed to get news details: {str(e)[:200]}")
#         return "Failed to fetch", "Failed to fetch"
#     finally:
#         if driver:
#             driver.quit()


# def parse_hotsearch_data(data: Dict) -> List[Dict]:
#     """Parse hot search data with ranking information"""
#     if not data or "data" not in data or "cards" not in data["data"]:
#         return []

#     hotsearch_list = data["data"]["cards"][0].get("content", [])
#     top_content = data["data"]["cards"][0].get("topContent", [])

#     parsed_data = []

#     # 处理置顶内容（标记为"置顶"）
#     for item in top_content:
#         search_url = item.get("url", "")
#         if not search_url.startswith('http'):
#             search_url = f"https://www.baidu.com/s?wd={item.get('word', '')}"

#         logging.info(f"Processing top hot search: {item.get('word', '')}")
#         news_title, news_content = get_news_detail(search_url)

#         parsed_data.append({
#             "ranking": "置顶",  # 特殊标记置顶内容
#             "hotsearch_title": item.get("word", ""),
#             "hotsearch_url": search_url,
#             "hot_index": item.get("hotScore", ""),
#             "hotsearch_desc": item.get("desc", ""),
#             "image_url": item.get("img", ""),
#             "is_top": "是",
#             "news_title": news_title,
#             "news_content": news_content[:100000],
#             "source": "百度热搜",
#             "crawl_time": datetime.now(),
#             "created_at": datetime.now(),
#             "updated_at": datetime.now(),
#             "tts": None  # 新增的tts字段，boolean类型，内容为空
#         })

#     # 处理普通热搜内容（数字排名）
#     for idx, item in enumerate(hotsearch_list[:2], 1):
#         search_url = item.get("url", "")
#         if not search_url.startswith('http'):
#             search_url = f"https://www.baidu.com/s?wd={item.get('word', '')}"

#         logging.info(f"Processing hot search #{idx}: {item.get('word', '')}")
#         news_title, news_content = get_news_detail(search_url)

#         parsed_data.append({
#             "ranking": str(idx),  # 数字排名（从1开始）
#             "hotsearch_title": item.get("word", ""),
#             "hotsearch_url": search_url,
#             "hot_index": item.get("hotScore", ""),
#             "hotsearch_desc": item.get("desc", ""),
#             "image_url": item.get("img", ""),
#             "is_top": "否",
#             "news_title": news_title,
#             "news_content": news_content[:100000],
#             "source": "百度热搜",
#             "crawl_time": datetime.now(),
#             "created_at": datetime.now(),
#             "updated_at": datetime.now(),
#             "tts": None  # 新增的tts字段，boolean类型，内容为空
#         })

#         time.sleep(2)

#     return parsed_data


# def connect_to_mongodb():
#     """Connect to MongoDB and return client and collections"""
#     try:
#         client = MongoClient(MONGO_URI)
#         db = client[DB_NAME]
#         collection_read = db[COLLECTION_READ]
#         collection_succ = db[COLLECTION_SUCC]
#         collection_fail = db[COLLECTION_FAIL]
#         client.server_info()
#         logging.info("Connected to MongoDB successfully")
#         return client, collection_read, collection_succ, collection_fail
#     except Exception as e:
#         logging.error(f"Failed to connect to MongoDB: {e}")
#         return None, None, None, None


# def filter_new_data(data: List[Dict], collections: List) -> List[Dict]:
#     """
#     过滤出 hotsearch_url 不存在于任一指定集合的数据，避免重复插入
#     """
#     existing_urls = set()
#     for col in collections:
#         try:
#             urls = col.distinct("hotsearch_url")
#             existing_urls.update(urls)
#         except Exception as e:
#             logging.error(f"Error fetching URLs from collection {col.name}: {e}")

#     filtered = [item for item in data if item.get("hotsearch_url") not in existing_urls]
#     logging.info(f"Filtered {len(data) - len(filtered)} duplicate entries; {len(filtered)} new entries remain")
#     return filtered


# def save_to_mongodb(data: List[Dict], collection) -> bool:
#     """Save data to MongoDB"""
#     if collection is None:
#         logging.error("Cannot save to MongoDB: Invalid connection")
#         return False

#     try:
#         if not data:
#             logging.info("No new data to insert")
#             return True
#         result = collection.insert_many(data)
#         logging.info(f"Successfully inserted {len(result.inserted_ids)} documents")
#         return True
#     except Exception as e:
#         logging.error(f"Failed to save to MongoDB: {e}")
#         return False


# def main():
#     """Main execution function"""
#     client, collection_read, collection_succ, collection_fail = connect_to_mongodb()
#     if not client:
#         logging.error("No MongoDB connection, exiting")
#         return

#     logging.info("Fetching Baidu hot search data...")
#     hotsearch_data = get_baidu_hotsearch_data()

#     if not hotsearch_data:
#         logging.error("Failed to fetch hot search data")
#         return

#     logging.info("Parsing hot search data...")
#     parsed_data = parse_hotsearch_data(hotsearch_data)

#     if not parsed_data:
#         logging.warning("No valid data to save")
#         return

#     # 过滤重复数据
#     collections = [collection_read, collection_succ, collection_fail]
#     new_data = filter_new_data(parsed_data, collections)

#     if not new_data:
#         logging.info("No new data to insert after filtering duplicates")
#         return

#     logging.info("Saving data to MongoDB...")
#     save_to_mongodb(new_data, collection_read)

#     # 关闭 MongoDB 连接
#     client.close()


# if __name__ == "__main__":
#     main()



# import os
# import re
# import time
# import logging
# from datetime import datetime
# from typing import Optional, Tuple, List, Dict

# import requests
# from bs4 import BeautifulSoup
# from pymongo import MongoClient
# from selenium import webdriver
# from selenium.webdriver.common.by import By
# from selenium.webdriver.edge.options import Options
# from selenium.webdriver.edge.service import Service
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.support.ui import WebDriverWait
# from readability import Document
# from webdriver_manager.microsoft import EdgeChromiumDriverManager

# # Configuration
# MONGO_URI = os.getenv("MONGO_URI",
#                       "mongodb+srv://newscrrawler:qwe123@crrawlercluster.eencizs.mongodb.net/?retryWrites=true&w=majority&appName=CrrawlerCluster")
# DB_NAME = "mydatabase"
# COLLECTION_READ = "read"
# COLLECTION_SUCC = "analyzed_succ"
# COLLECTION_FAIL = "analyzed_fail"

# HEADERS = {
#     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
#     'Referer': 'https://top.baidu.com/board?tab=realtime'
# }

# # Configure logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# def get_baidu_hotsearch_data() -> Optional[Dict]:
#     """Fetch Baidu hot search data"""
#     api_url = "https://top.baidu.com/api/board?tab=realtime"
#     try:
#         response = requests.get(api_url, headers=HEADERS)
#         response.raise_for_status()
#         return response.json()
#     except Exception as e:
#         logging.error(f"Failed to fetch hot search data: {e}")
#         return None


# def setup_driver() -> webdriver.Edge:
#     """Setup and return WebDriver instance"""
#     options = Options()
#     options.add_argument("--headless")
#     options.add_argument("--disable-gpu")
#     options.add_argument("--no-sandbox")
#     options.add_argument("--disable-dev-shm-usage")
#     options.add_argument(
#         "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

#     driver_path = EdgeChromiumDriverManager().install()
#     service = Service(driver_path)
#     driver = webdriver.Edge(service=service, options=options)

#     # Anti-detection
#     driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
#         "source": """
#             Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
#             Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
#         """
#     })
#     return driver


# def is_valid_webpage_link(href: str) -> bool:
#     """Check if a link is a valid external webpage"""
#     if not href:
#         return False
#     invalid_prefixes = [
#         "https://tieba.baidu.com",
#         "https://zhidao.baidu.com",
#         "https://baike.baidu.com",
#         "https://v.baidu.com",
#         "https://sp.baidu.com",
#         "https://image.baidu.com",
#         "https://video.baidu.com",
#         "https://wenku.baidu.com",
#         "https://map.baidu.com",
#         "https://events.baidu.com",
#         "https://new.baidu.com",
#         "https://voice.baidu.com",
#     ]
#     return not any(href.startswith(prefix) for prefix in invalid_prefixes)


# def wait_for_page_load(driver: webdriver.Edge, timeout: int = 10) -> None:
#     """Wait for page to load"""
#     try:
#         WebDriverWait(driver, timeout).until(
#             EC.presence_of_element_located((By.TAG_NAME, "body"))
#         )
#     except Exception as e:
#         logging.warning(f"Page load timeout: {e}")


# def scroll_to_bottom(driver: webdriver.Edge, scroll_pause_time: float = 1.0, max_scrolls: int = 10) -> None:
#     """Scroll to bottom of page to load lazy content"""
#     last_height = driver.execute_script("return document.body.scrollHeight")
#     for _ in range(max_scrolls):
#         driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
#         time.sleep(scroll_pause_time)
#         new_height = driver.execute_script("return document.body.scrollHeight")
#         if new_height == last_height:
#             break
#         last_height = new_height


# def extract_content_from_html(html: str) -> Tuple[str, str]:
#     """Extract title and content from HTML using readability"""
#     doc = Document(html)
#     title = doc.title()
#     summary_html = doc.summary()

#     soup = BeautifulSoup(summary_html, "html.parser")
#     content = soup.get_text(separator="\n", strip=True)

#     return title, content


# def get_first_valid_url(driver: webdriver.Edge, search_url: str) -> Optional[str]:
#     """Find first valid URL from search results"""
#     driver.get(search_url)
#     wait_for_page_load(driver)
#     time.sleep(3)

#     try:
#         web_tab = WebDriverWait(driver, 5).until(
#             EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[data-index="0"]')))
#         web_tab.click()
#         time.sleep(3)
#     except Exception:
#         pass

#     containers = driver.find_elements(By.CSS_SELECTOR, 'div.c-container, div.result')
#     for container in containers:
#         try:
#             a = container.find_element(By.CSS_SELECTOR, 'a[href]')
#             href = a.get_attribute('href')
#             if is_valid_webpage_link(href):
#                 return href
#         except Exception:
#             continue
#     return None


# def get_news_detail(search_url: str) -> Tuple[str, str]:
#     """Get news details (title and content) from a search URL"""
#     driver = None
#     try:
#         driver = setup_driver()
#         first_valid_url = get_first_valid_url(driver, search_url)

#         if not first_valid_url:
#             return "No valid link found", "No valid link found"

#         driver.get(first_valid_url)
#         wait_for_page_load(driver)
#         scroll_to_bottom(driver)

#         html = driver.page_source
#         return extract_content_from_html(html)
#     except Exception as e:
#         logging.error(f"Failed to get news details: {str(e)[:200]}")
#         return "Failed to fetch", "Failed to fetch"
#     finally:
#         if driver:
#             driver.quit()


# def parse_hotsearch_data(data: Dict) -> List[Dict]:
#     """Parse hot search data with ranking information"""
#     if not data or "data" not in data or "cards" not in data["data"]:
#         return []

#     hotsearch_list = data["data"]["cards"][0].get("content", [])
#     top_content = data["data"]["cards"][0].get("topContent", [])

#     parsed_data = []

#     # 处理置顶内容（标记为"置顶"）
#     for item in top_content:
#         search_url = item.get("url", "")
#         if not search_url.startswith('http'):
#             search_url = f"https://www.baidu.com/s?wd={item.get('word', '')}"

#         logging.info(f"Processing top hot search: {item.get('word', '')}")
#         news_title, news_content = get_news_detail(search_url)

#         parsed_data.append({
#             "ranking": "置顶",  # 特殊标记置顶内容
#             "hotsearch_title": item.get("word", ""),
#             "hotsearch_url": search_url,
#             "hot_index": item.get("hotScore", ""),
#             "hotsearch_desc": item.get("desc", ""),
#             "image_url": item.get("img", ""),
#             "is_top": "是",
#             "news_title": news_title,
#             "news_content": news_content[:100000],
#             "source": "百度热搜",
#             "created_at": datetime.now(),
#             "updated_at": datetime.now(),
#             "tts": None, # 新增的tts字段，boolean类型，内容为空
#             "status": "processed",
#             "broadcasted": False,
#             "processed_at": datetime.now(),
#         })

#     # 处理普通热搜内容（数字排名）
#     for idx, item in enumerate(hotsearch_list[:20], 1):
#         search_url = item.get("url", "")
#         if not search_url.startswith('http'):
#             search_url = f"https://www.baidu.com/s?wd={item.get('word', '')}"

#         logging.info(f"Processing hot search #{idx}: {item.get('word', '')}")
#         news_title, news_content = get_news_detail(search_url)

#         parsed_data.append({
#             "ranking": str(idx),  # 数字排名（从1开始）
#             "hotsearch_title": item.get("word", ""),
#             "hotsearch_url": search_url,
#             "hot_index": item.get("hotScore", ""),
#             "hotsearch_desc": item.get("desc", ""),
#             "image_url": item.get("img", ""),
#             "is_top": "否",
#             "news_title": news_title,
#             "news_content": news_content[:100000],
#             "source": "百度热搜",
#             "created_at": datetime.now(),
#             "updated_at": datetime.now(),
#             "tts": None,  # 新增的tts字段，boolean类型，内容为空
#             "status": "processed",
#             "broadcasted": False,
#             "processed_at": datetime.now()
#         })

#         time.sleep(2)

#     return parsed_data


# def connect_to_mongodb():
#     """Connect to MongoDB and return client and collections"""
#     try:
#         client = MongoClient(MONGO_URI)
#         db = client[DB_NAME]
#         collection_read = db[COLLECTION_READ]
#         collection_succ = db[COLLECTION_SUCC]
#         collection_fail = db[COLLECTION_FAIL]
#         client.server_info()
#         logging.info("Connected to MongoDB successfully")
#         return client, collection_read, collection_succ, collection_fail
#     except Exception as e:
#         logging.error(f"Failed to connect to MongoDB: {e}")
#         return None, None, None, None


# def filter_new_data(data: List[Dict], collections: List) -> List[Dict]:
#     """
#     过滤出 hotsearch_url 不存在于任一指定集合的数据，避免重复插入
#     """
#     existing_urls = set()
#     for col in collections:
#         try:
#             urls = col.distinct("hotsearch_url")
#             existing_urls.update(urls)
#         except Exception as e:
#             logging.error(f"Error fetching URLs from collection {col.name}: {e}")

#     filtered = [item for item in data if item.get("hotsearch_url") not in existing_urls]
#     logging.info(f"Filtered {len(data) - len(filtered)} duplicate entries; {len(filtered)} new entries remain")
#     return filtered


# def save_to_mongodb(data: List[Dict], collection) -> bool:
#     """Save data to MongoDB"""
#     if collection is None:
#         logging.error("Cannot save to MongoDB: Invalid connection")
#         return False

#     try:
#         if not data:
#             logging.info("No new data to insert")
#             return True
#         result = collection.insert_many(data)
#         logging.info(f"Successfully inserted {len(result.inserted_ids)} documents")
#         return True
#     except Exception as e:
#         logging.error(f"Failed to save to MongoDB: {e}")
#         return False


# def main():
#     """Main execution function"""
#     client, collection_read, collection_succ, collection_fail = connect_to_mongodb()
#     if not client:
#         logging.error("No MongoDB connection, exiting")
#         return

#     logging.info("Fetching Baidu hot search data...")
#     hotsearch_data = get_baidu_hotsearch_data()

#     if not hotsearch_data:
#         logging.error("Failed to fetch hot search data")
#         return

#     logging.info("Parsing hot search data...")
#     parsed_data = parse_hotsearch_data(hotsearch_data)

#     if not parsed_data:
#         logging.warning("No valid data to save")
#         return

#     # 过滤重复数据
#     collections = [collection_read, collection_succ, collection_fail]
#     new_data = filter_new_data(parsed_data, collections)

#     if not new_data:
#         logging.info("No new data to insert after filtering duplicates")
#         return

#     logging.info("Saving data to MongoDB...")
#     save_to_mongodb(new_data, collection_read)

#     # 关闭 MongoDB 连接
#     client.close()


# if __name__ == "__main__":
#     main()

import os
import re
import time
import logging
import winreg
from datetime import datetime
from typing import Optional, Tuple, List, Dict

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from readability import Document
from tenacity import retry, stop_after_attempt, wait_exponential

# 配置项
MONGO_URI = os.getenv("MONGO_URI",
                      "mongodb+srv://newscrrawler:qwe123@crrawlercluster.eencizs.mongodb.net/?retryWrites=true&w=majority&appName=CrrawlerCluster")
DB_NAME = "mydatabase"
COLLECTION_READ = "read"
COLLECTION_SUCC = "analyzed_succ"
COLLECTION_FAIL = "analyzed_fail"

# WebDriver路径
EDGE_DRIVER_PATH = os.path.normpath(r"D:\Project\NewsCrawler\news_crawler\msedgedriver.exe")

# 请求头配置
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    'Referer': 'https://top.baidu.com/board?tab=realtime'
}

# 日志配置
log_path = os.path.join(os.path.dirname(__file__), 'baidu_hotsearch.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path, encoding='utf-8'),
        logging.StreamHandler()
    ]
)


def get_edge_version() -> str:
    """从注册表获取Edge浏览器版本"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Edge\BLBeacon") as key:
            version = winreg.QueryValueEx(key, "version")[0]
            logging.info(f"检测到Edge浏览器版本: {version}")
            return version
    except Exception as e:
        logging.warning(f"获取Edge版本失败: {e}")
        return ""


def check_internet() -> bool:
    """检查网络连接"""
    try:
        requests.get("http://www.baidu.com", timeout=5)
        return True
    except Exception:
        logging.error("网络连接检查失败")
        return False


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def get_baidu_hotsearch_data() -> Optional[Dict]:
    """获取百度热搜数据（带重试机制）"""
    api_url = "https://top.baidu.com/api/board?tab=realtime"
    try:
        response = requests.get(api_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"获取热搜数据失败: {e}")
        raise


def setup_driver() -> webdriver.Edge:
    """初始化Edge浏览器驱动"""
    if not os.path.exists(EDGE_DRIVER_PATH):
        raise FileNotFoundError(f"未找到EdgeDriver: {EDGE_DRIVER_PATH}")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"user-agent={HEADERS['User-Agent']}")

    try:
        service = Service(executable_path=EDGE_DRIVER_PATH)
        driver = webdriver.Edge(service=service, options=options)

        driver.execute_cdp_cmd("Network.setUserAgentOverride", {
            "userAgent": HEADERS['User-Agent']
        })
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh']});
                window.chrome = {runtime: {}};
            """
        })
        logging.info("Edge浏览器驱动初始化成功")
        return driver
    except Exception as e:
        logging.error(f"浏览器驱动初始化失败: {e}")
        raise


def is_valid_webpage_link(href: str) -> bool:
    """检查是否为有效的外部网页链接"""
    if not href:
        return False
    invalid_prefixes = [
        "https://tieba.baidu.com",
        "https://zhidao.baidu.com",
        "https://baike.baidu.com",
        "https://v.baidu.com",
        "https://sp.baidu.com",
        "https://image.baidu.com",
        "https://video.baidu.com",
        "https://wenku.baidu.com",
        "https://map.baidu.com",
        "https://events.baidu.com",
        "https://new.baidu.com",
        "https://voice.baidu.com",
    ]
    return not any(href.startswith(prefix) for prefix in invalid_prefixes)


def wait_for_page_load(driver: webdriver.Edge, timeout: int = 10) -> None:
    """等待页面加载完成"""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except TimeoutException as e:
        logging.warning(f"页面加载超时: {e}")


def scroll_to_bottom(driver: webdriver.Edge, scroll_pause_time: float = 1.0, max_scrolls: int = 5) -> None:
    """滚动到页面底部加载延迟内容"""
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(max_scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_pause_time)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


def extract_content_from_html(html: str) -> Tuple[str, str]:
    """从HTML中提取标题和正文内容"""
    try:
        doc = Document(html)
        title = doc.title()
        summary_html = doc.summary()

        soup = BeautifulSoup(summary_html, "html.parser")
        for script in soup(["script", "style", "iframe", "noscript"]):
            script.decompose()

        content = soup.get_text(separator="\n", strip=True)
        content = re.sub(r'\n{3,}', '\n\n', content)
        return title, content
    except Exception as e:
        logging.error(f"内容提取失败: {e}")
        return "提取标题失败", "提取内容失败"


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
def get_first_valid_url(driver: webdriver.Edge, search_url: str) -> Optional[str]:
    """从搜索结果中获取第一个有效URL"""
    try:
        driver.get(search_url)
        wait_for_page_load(driver)

        selectors = ['div.c-container a', 'div.result a', 'h3 a']
        for selector in selectors:
            try:
                links = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))

                for link in links:
                    try:
                        href = link.get_attribute('href')
                        if href and is_valid_webpage_link(href):
                            logging.info(f"找到有效链接: {href[:50]}...")
                            return href
                    except Exception as e:
                        logging.debug(f"处理链接失败: {e}")
                        continue
            except TimeoutException:
                logging.debug(f"选择器 '{selector}' 超时未找到元素")
                continue
            except Exception as e:
                logging.debug(f"选择器 '{selector}' 执行异常: {e}")
                continue

        logging.warning("所有选择器均未找到有效链接")
        return None
    except Exception as e:
        logging.error(f"获取有效URL失败: {str(e)}")
        raise


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
def get_news_detail(search_url: str, driver: webdriver.Edge) -> Tuple[str, str]:
    """获取新闻详情（带重试机制）"""
    try:
        first_valid_url = get_first_valid_url(driver, search_url)
        if not first_valid_url:
            logging.warning(f"未找到有效链接: {search_url}")
            return "未找到有效链接", "未找到有效链接"

        driver.get(first_valid_url)
        wait_for_page_load(driver)
        scroll_to_bottom(driver)
        return extract_content_from_html(driver.page_source)
    except Exception as e:
        logging.error(f"获取新闻详情失败: {str(e)[:200]}")
        raise


def parse_hotsearch_data(data: Dict, driver: webdriver.Edge) -> List[Dict]:
    """解析热搜数据"""
    if not data or "data" not in data or "cards" not in data["data"]:
        return []

    parsed_data = []
    hot_items = data["data"]["cards"][0].get("content", [])[:10]
    top_items = data["data"]["cards"][0].get("topContent", [])

    for item in top_items + hot_items:
        try:
            search_url = item.get("url", f"https://www.baidu.com/s?wd={item.get('word', '')}")
            is_top = "是" if item in top_items else "否"
            ranking = "置顶" if is_top == "是" else str(hot_items.index(item) + 1 if item in hot_items else "N/A")

            logging.info(f"正在处理热搜 {ranking}: {item.get('word', '')}")
            news_title, news_content = get_news_detail(search_url, driver)

            parsed_data.append({
                "ranking": ranking,
                "hotsearch_title": item.get("word", ""),
                "hotsearch_url": search_url,
                "hot_index": item.get("hotScore", ""),
                "hotsearch_desc": item.get("desc", ""),
                "image_url": item.get("img", ""),
                "is_top": is_top,
                "news_title": news_title,
                "news_content": news_content[:100000],
                "source": "百度热搜",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "tts": None,
                "status": "processed",
                "broadcasted": False,
                "processed_at": datetime.now()
            })
            time.sleep(1)
        except Exception as e:
            logging.error(f"处理热搜失败: {e}")
            continue

    return parsed_data


def connect_to_mongodb():
    """连接MongoDB数据库"""
    try:
        client = MongoClient(
            MONGO_URI,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
            serverSelectionTimeoutMS=5000
        )
        client.admin.command('ping')
        db = client[DB_NAME]
        return client, db[COLLECTION_READ], db[COLLECTION_SUCC], db[COLLECTION_FAIL]
    except Exception as e:
        logging.error(f"MongoDB连接失败: {e}")
        return None, None, None, None


def filter_new_data(data: List[Dict], collections: List) -> List[Dict]:
    """过滤已存在的数据"""
    existing_urls = set()
    for col in collections:
        if col is not None:
            try:
                existing_urls.update(item.get("hotsearch_url") for item in col.find({}, {"hotsearch_url": 1, "_id": 0}))
            except Exception as e:
                logging.error(f"从集合获取URL失败: {e}")

    filtered = [item for item in data if item.get("hotsearch_url") not in existing_urls]
    logging.info(f"过滤结果: 原始数据 {len(data)} 条，去重后 {len(filtered)} 条")
    return filtered


def save_to_mongodb(data: List[Dict], collection) -> bool:
    """保存数据到MongoDB"""
    if collection is None or not data:
        logging.error("无效的集合或空数据")
        return False

    try:
        result = collection.insert_many(data, ordered=False)
        logging.info(f"成功插入 {len(result.inserted_ids)} 条文档")
        return True
    except Exception as e:
        logging.error(f"保存到MongoDB失败: {e}")
        return False


def main():
    """主函数"""
    if not check_internet():
        return

    driver, client = None, None
    try:
        logging.info(f"当前Edge版本: {get_edge_version() or '未知'}")

        if not os.path.exists(EDGE_DRIVER_PATH):
            logging.error(f"未找到Edge驱动: {EDGE_DRIVER_PATH}")
            return

        driver = setup_driver()
        client, read_col, succ_col, fail_col = connect_to_mongodb()
        if not client:
            return

        logging.info("获取百度热搜数据...")
        if hotsearch_data := get_baidu_hotsearch_data():
            parsed_data = parse_hotsearch_data(hotsearch_data, driver)
            new_data = filter_new_data(parsed_data, [read_col, succ_col, fail_col])
            if new_data and save_to_mongodb(new_data, read_col):
                logging.info("数据保存成功")
    except Exception as e:
        logging.error(f"主程序错误: {e}")
    finally:
        if driver:
            driver.quit()
            logging.info("浏览器已关闭")
        if client:
            client.close()
            logging.info("数据库连接已关闭")


if __name__ == "__main__":
    main()

