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
# from selenium.common.exceptions import TimeoutException, WebDriverException
# from readability import Document
# from webdriver_manager.microsoft import EdgeChromiumDriverManager

# # Configuration
# MONGO_URI = os.getenv("MONGO_URI",
#                      "mongodb+srv://newscrrawler:qwe123@crrawlercluster.eencizs.mongodb.net/?retryWrites=true&w=majority&appName=CrrawlerCluster")
# DB_NAME = "mydatabase"
# COLLECTION_READ = "read"
# COLLECTION_SUCC = "analyzed_succ"
# COLLECTION_FAIL = "analyzed_fail"

# HEADERS = {
#     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
#     'Referer': 'https://top.baidu.com/board?tab=realtime'
# }

# # Configure logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.StreamHandler()
#     ]
# )

# def setup_driver() -> Optional[webdriver.Edge]:
#     """Setup and return WebDriver instance with GitHub Actions compatibility"""
#     try:
#         options = Options()
        
#         # GitHub Actions specific settings
#         if os.getenv('GITHUB_ACTIONS') == 'true':
#             options.add_argument("--headless=new")
#             options.add_argument("--disable-gpu")
#             options.add_argument("--no-sandbox")
#             options.add_argument("--disable-dev-shm-usage")
#             options.add_argument("--remote-debugging-port=9222")
#         else:
#             options.add_argument("--headless")
        
#         options.add_argument(f"user-agent={HEADERS['User-Agent']}")
        
#         # Anti-detection
#         options.add_argument("--disable-blink-features=AutomationControlled")
#         options.add_experimental_option("excludeSwitches", ["enable-automation"])
#         options.add_experimental_option("useAutomationExtension", False)

#         # Use webdriver_manager to handle driver installation
#         driver_path = EdgeChromiumDriverManager().install()
#         service = Service(driver_path)
#         driver = webdriver.Edge(service=service, options=options)

#         # Additional anti-detection measures
#         driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
#             "source": """
#                 Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
#                 Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh']});
#                 window.chrome = {runtime: {}};
#             """
#         })
        
#         return driver
#     except Exception as e:
#         logging.error(f"Failed to initialize WebDriver: {e}")
#         return None

# def get_baidu_hotsearch_data() -> Optional[Dict]:
#     """Fetch Baidu hot search data with retry mechanism"""
#     api_url = "https://top.baidu.com/api/board?tab=realtime"
#     max_retries = 3
    
#     for attempt in range(max_retries):
#         try:
#             response = requests.get(api_url, headers=HEADERS, timeout=10)
#             response.raise_for_status()
#             return response.json()
#         except Exception as e:
#             if attempt == max_retries - 1:
#                 logging.error(f"Failed to fetch hot search data after {max_retries} attempts: {e}")
#                 return None
#             time.sleep(2 ** attempt)  # Exponential backoff

# def is_valid_webpage_link(href: str) -> bool:
#     """Check if a link is a valid external webpage"""
#     if not href or not href.startswith('http'):
#         return False
        
#     invalid_domains = [
#         "tieba.baidu.com",
#         "zhidao.baidu.com",
#         "baike.baidu.com",
#         "v.baidu.com",
#         "sp.baidu.com",
#         "image.baidu.com",
#         "video.baidu.com",
#         "wenku.baidu.com",
#         "map.baidu.com",
#         "events.baidu.com",
#         "new.baidu.com",
#         "voice.baidu.com",
#     ]
    
#     return not any(domain in href for domain in invalid_domains)

# def wait_for_page_load(driver: webdriver.Edge, timeout: int = 15) -> bool:
#     """Wait for page to load completely"""
#     try:
#         WebDriverWait(driver, timeout).until(
#             lambda d: d.execute_script("return document.readyState") == "complete"
#         )
#         return True
#     except TimeoutException:
#         logging.warning("Page load timed out")
#         return False

# def scroll_to_bottom(driver: webdriver.Edge, scroll_pause_time: float = 1.0, max_scrolls: int = 3) -> None:
#     """Scroll to bottom of page to load lazy content"""
#     last_height = driver.execute_script("return document.body.scrollHeight")
#     for _ in range(max_scrolls):
#         driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
#         time.sleep(scroll_pause_time)
#         new_height = driver.execute_script("return document.body.scrollHeight")
#         if new_height == last_height:
#             break
#         last_height = new_height

# def clean_content(text: str) -> str:
#     """Clean extracted content"""
#     if not text:
#         return ""
    
#     # Remove excessive whitespace and newlines
#     text = re.sub(r'\s+', ' ', text).strip()
#     text = re.sub(r'\n{3,}', '\n\n', text)
    
#     return text

# def extract_content_from_html(html: str) -> Tuple[str, str]:
#     """Extract title and content from HTML with improved cleaning"""
#     try:
#         doc = Document(html)
#         title = doc.title() or "No title found"
        
#         # Get summary and clean it
#         summary_html = doc.summary()
#         soup = BeautifulSoup(summary_html, "html.parser")
        
#         # Remove unwanted elements
#         for element in soup(["script", "style", "iframe", "noscript", "nav", "footer", "aside"]):
#             element.decompose()
            
#         # Get text and clean it
#         content = soup.get_text(separator="\n", strip=True)
#         content = clean_content(content)
        
#         return title, content
#     except Exception as e:
#         logging.error(f"Content extraction failed: {e}")
#         return "Failed to extract title", "Failed to extract content"

# def get_first_valid_url(driver: webdriver.Edge, search_url: str) -> Optional[str]:
#     """Find first valid URL from search results with multiple strategies"""
#     try:
#         driver.get(search_url)
#         if not wait_for_page_load(driver):
#             return None
            
#         # Try multiple selectors to find valid links
#         selectors = [
#             'div.c-container a[href]',  # Baidu desktop results
#             'div.result a[href]',       # Alternative Baidu results
#             'h3 a[href]',               # Common heading links
#             'a[href]'                   # Fallback to any link
#         ]
        
#         for selector in selectors:
#             try:
#                 links = driver.find_elements(By.CSS_SELECTOR, selector)
#                 for link in links:
#                     try:
#                         href = link.get_attribute('href')
#                         if href and is_valid_webpage_link(href):
#                             logging.info(f"Found valid link: {href[:80]}...")
#                             return href
#                     except Exception:
#                         continue
#             except Exception:
#                 continue
                
#         logging.warning("No valid links found with any selector")
#         return None
#     except Exception as e:
#         logging.error(f"Failed to get valid URL: {e}")
#         return None

# def get_news_detail(driver: webdriver.Edge, search_url: str) -> Tuple[str, str]:
#     """Get news details with improved error handling"""
#     try:
#         first_valid_url = get_first_valid_url(driver, search_url)
#         if not first_valid_url:
#             return "No valid link found", "No valid link found"

#         driver.get(first_valid_url)
#         if not wait_for_page_load(driver):
#             return "Page load failed", "Page load failed"
            
#         scroll_to_bottom(driver)
#         return extract_content_from_html(driver.page_source)
#     except Exception as e:
#         logging.error(f"Failed to get news details: {e}")
#         return "Failed to fetch", "Failed to fetch"

# def parse_hotsearch_data(data: Dict, driver: webdriver.Edge) -> List[Dict]:
#     """Parse hot search data with ranking information"""
#     if not data or "data" not in data or "cards" not in data["data"]:
#         return []

#     try:
#         hotsearch_list = data["data"]["cards"][0].get("content", [])[:20]  # Limit to top 20
#         top_content = data["data"]["cards"][0].get("topContent", [])
#         parsed_data = []

#         # Process top content (marked as "Top")
#         for item in top_content:
#             try:
#                 search_url = item.get("url", f"https://www.baidu.com/s?wd={item.get('word', '')}")
#                 logging.info(f"Processing top hot search: {item.get('word', '')}")
                
#                 news_title, news_content = get_news_detail(driver, search_url)
                
#                 parsed_data.append({
#                     "ranking": "Top",
#                     "hotsearch_title": item.get("word", ""),
#                     "hotsearch_url": search_url,
#                     "hot_index": item.get("hotScore", ""),
#                     "hotsearch_desc": item.get("desc", ""),
#                     "image_url": item.get("img", ""),
#                     "is_top": True,
#                     "news_title": news_title,
#                     "news_content": news_content[:100000],  # Limit content size
#                     "source": "Baidu Hot Search",
#                     "created_at": datetime.now(),
#                     "updated_at": datetime.now(),
#                     "tts": None,
#                     "status": "processed",
#                     "broadcasted": False,
#                     "processed_at": datetime.now()
#                 })
#             except Exception as e:
#                 logging.error(f"Failed to process top content item: {e}")
#                 continue

#         # Process regular hot search content (numbered ranking)
#         for idx, item in enumerate(hotsearch_list, 1):
#             try:
#                 search_url = item.get("url", f"https://www.baidu.com/s?wd={item.get('word', '')}")
#                 logging.info(f"Processing hot search #{idx}: {item.get('word', '')}")
                
#                 news_title, news_content = get_news_detail(driver, search_url)
                
#                 parsed_data.append({
#                     "ranking": str(idx),
#                     "hotsearch_title": item.get("word", ""),
#                     "hotsearch_url": search_url,
#                     "hot_index": item.get("hotScore", ""),
#                     "hotsearch_desc": item.get("desc", ""),
#                     "image_url": item.get("img", ""),
#                     "is_top": False,
#                     "news_title": news_title,
#                     "news_content": news_content[:100000],  # Limit content size
#                     "source": "Baidu Hot Search",
#                     "created_at": datetime.now(),
#                     "updated_at": datetime.now(),
#                     "tts": None,
#                     "status": "processed",
#                     "broadcasted": False,
#                     "processed_at": datetime.now()
#                 })
                
#                 time.sleep(1)  # Be polite with delays
#             except Exception as e:
#                 logging.error(f"Failed to process hot search item #{idx}: {e}")
#                 continue

#         return parsed_data
#     except Exception as e:
#         logging.error(f"Failed to parse hot search data: {e}")
#         return []

# def connect_to_mongodb():
#     """Connect to MongoDB with timeout settings"""
#     try:
#         client = MongoClient(
#             MONGO_URI,
#             connectTimeoutMS=5000,
#             socketTimeoutMS=5000,
#             serverSelectionTimeoutMS=5000
#         )
#         client.admin.command('ping')  # Test connection
#         db = client[DB_NAME]
#         return client, db[COLLECTION_READ], db[COLLECTION_SUCC], db[COLLECTION_FAIL]
#     except Exception as e:
#         logging.error(f"Failed to connect to MongoDB: {e}")
#         return None, None, None, None

# def filter_new_data(data: List[Dict], collections: List) -> List[Dict]:
#     """Filter out existing data by checking URLs"""
#     existing_urls = set()
#     for col in collections:
#         if col is not None:
#             try:
#                 urls = col.distinct("hotsearch_url")
#                 existing_urls.update(urls)
#             except Exception as e:
#                 logging.error(f"Error fetching URLs from collection: {e}")

#     return [item for item in data if item.get("hotsearch_url") not in existing_urls]

# def save_to_mongodb(data: List[Dict], collection) -> bool:
#     """Save data to MongoDB with error handling"""
#     if not collection or not data:
#         return False

#     try:
#         result = collection.insert_many(data, ordered=False)  # Continue on error
#         logging.info(f"Inserted {len(result.inserted_ids)} documents")
#         return True
#     except Exception as e:
#         logging.error(f"Failed to save to MongoDB: {e}")
#         return False

# def main():
#     """Main execution function with proper resource cleanup"""
#     driver, client = None, None
#     try:
#         driver = setup_driver()
#         if not driver:
#             return
            
#         client, read_col, succ_col, fail_col = connect_to_mongodb()
#         if not client:
#             return

#         logging.info("Fetching Baidu hot search data...")
#         hotsearch_data = get_baidu_hotsearch_data()
#         if not hotsearch_data:
#             return

#         logging.info("Parsing hot search data...")
#         parsed_data = parse_hotsearch_data(hotsearch_data, driver)
#         if not parsed_data:
#             return

#         # Filter duplicates
#         new_data = filter_new_data(parsed_data, [read_col, succ_col, fail_col])
#         if not new_data:
#             logging.info("No new data to insert")
#             return

#         # Save to MongoDB
#         if save_to_mongodb(new_data, read_col):
#             logging.info("Data saved successfully")
#     except Exception as e:
#         logging.error(f"Main execution failed: {e}")
#     finally:
#         try:
#             if driver:
#                 driver.quit()
#         except Exception as e:
#             logging.error(f"Failed to quit driver: {e}")
            
#         try:
#             if client:
#                 client.close()
#         except Exception as e:
#             logging.error(f"Failed to close MongoDB connection: {e}")

# if __name__ == "__main__":
#     main()


import os
import re
import time
import logging
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
from readability import Document
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# Configuration
MONGO_URI = os.getenv("MONGO_URI",
                      "mongodb+srv://newscrrawler:qwe123@crrawlercluster.eencizs.mongodb.net/?retryWrites=true&w=majority&appName=CrrawlerCluster")
DB_NAME = "mydatabase"
COLLECTION_READ = "read"
COLLECTION_SUCC = "analyzed_succ"
COLLECTION_FAIL = "analyzed_fail"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://top.baidu.com/board?tab=realtime'
}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_baidu_hotsearch_data() -> Optional[Dict]:
    """Fetch Baidu hot search data"""
    api_url = "https://top.baidu.com/api/board?tab=realtime"
    try:
        response = requests.get(api_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Failed to fetch hot search data: {e}")
        return None


def setup_driver() -> webdriver.Edge:
    """Setup and return a configured Edge WebDriver instance.

    Returns:
        webdriver.Edge: Configured Edge browser instance

    Raises:
        FileNotFoundError: If Edge driver is not found in drivers/ directory
        WebDriverException: If WebDriver initialization fails
    """
    options = Options()

    # ==================== 浏览器选项配置 ====================
    # 无头模式和基础配置
    options.add_argument("--headless=new")  # 新版Edge推荐使用"--headless=new"
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")

    # 用户代理和语言设置
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"  # 注意这里改为Edge的User-Agent
    )
    options.add_argument("--lang=en-US,en")

    # GitHub Actions专用配置
    if os.getenv('GITHUB_ACTIONS') == 'true':
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-logging")
        options.add_argument("--log-level=3")
        options.add_argument("--single-process")  # 单进程模式提升稳定性

    try:
        # ==================== 驱动路径配置 ====================
        # 动态获取项目根目录下的drivers/msedgedriver
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        driver_path = os.path.join(project_root, "drivers", "msedgedriver")

        # 验证驱动文件存在
        if not os.path.exists(driver_path):
            raise FileNotFoundError(
                f"Edge驱动未找到: {driver_path}\n"
                "请从以下地址下载匹配版本的驱动并放入drivers/目录:\n"
                "https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/"
            )

        logging.info(f"使用本地Edge驱动: {driver_path}")

        # ==================== 服务配置 ====================
        service = Service(
            executable_path=driver_path,
            service_args=['--verbose'] if logging.getLogger().level == logging.DEBUG else None
        )

        # GitHub Actions特殊配置
        if os.getenv('GITHUB_ACTIONS') == 'true':
            service.creation_flags = 0x80000000  # Windows无窗口标志
            service.start()  # 显式启动服务避免竞争条件

        # ==================== 浏览器初始化 ====================
        driver = webdriver.Edge(
            service=service,
            options=options,
            service_executor_timeout=30,  # 服务启动超时30秒
            keep_alive=True  # 保持长连接
        )

        # ==================== 反检测措施 ====================
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                    configurable: true
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                    configurable: true
                });
                window.navigator.chrome = {
                    runtime: {},
                    loadTimes: () => {},
                    csi: () => {},
                    app: {
                        isInstalled: false,
                        InstallState: 'disabled',
                        RunningState: 'stopped'
                    }
                };
            """
        })

        # 设置超时参数
        driver.set_page_load_timeout(30)  # 页面加载超时30秒
        driver.set_script_timeout(20)  # 脚本执行超时20秒

        return driver

    except Exception as e:
        logging.error("WebDriver初始化失败", exc_info=True)
        raise


def is_valid_webpage_link(href: str) -> bool:
    """Check if a link is a valid external webpage"""
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
    return href.startswith('http') and not any(href.startswith(prefix) for prefix in invalid_prefixes)


def wait_for_page_load(driver: webdriver.Edge, timeout: int = 15) -> None:
    """Wait for page to load with extended timeout for GitHub Actions"""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
    except Exception as e:
        logging.warning(f"Page load timeout: {e}")


def scroll_to_bottom(driver: webdriver.Edge, scroll_pause_time: float = 1.5, max_scrolls: int = 5) -> None:
    """Scroll to bottom of page to load lazy content with adjusted parameters"""
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(max_scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_pause_time)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


def extract_content_from_html(html: str) -> Tuple[str, str]:
    """Extract title and content from HTML using readability with error handling"""
    try:
        doc = Document(html)
        title = doc.title() or "No title found"

        summary_html = doc.summary()
        soup = BeautifulSoup(summary_html, "html.parser")

        # Remove unwanted elements
        for element in soup(['script', 'style', 'iframe', 'nav', 'footer', 'aside']):
            element.decompose()

        content = soup.get_text(separator="\n", strip=True)
        content = re.sub(r'\n{3,}', '\n\n', content)  # Reduce excessive newlines

        return title, content[:100000]  # Directly truncate here
    except Exception as e:
        logging.error(f"Error extracting content: {e}")
        return "Failed to extract title", "Failed to extract content"


def get_first_valid_url(driver: webdriver.Edge, search_url: str) -> Optional[str]:
    """Find first valid URL from search results with improved reliability"""
    try:
        driver.get(search_url)
        wait_for_page_load(driver)
        time.sleep(3)  # Additional wait for search results to load

        # Try to click the "Web" tab if available
        try:
            web_tab = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a[data-index="0"]')))
            driver.execute_script("arguments[0].click();", web_tab)
            time.sleep(2)
        except Exception:
            pass  # Continue if web tab not found

        # Find all possible result containers
        containers = driver.find_elements(By.CSS_SELECTOR,
                                          'div.c-container, div.result, div.result-op, div[mu]')

        for container in containers:
            try:
                # Find all links in container and check them
                links = container.find_elements(By.CSS_SELECTOR, 'a[href]')
                for link in links:
                    href = link.get_attribute('href')
                    if href and is_valid_webpage_link(href):
                        logging.info(f"Found valid URL: {href}")
                        return href
            except Exception:
                continue

        logging.warning("No valid external links found in search results")
        return None

    except Exception as e:
        logging.error(f"Error finding valid URL: {e}")
        return None


def get_news_detail(search_url: str) -> Tuple[str, str]:
    """Get news details with improved error handling and retry logic"""
    driver = None
    retry_count = 2  # Number of retry attempts

    for attempt in range(retry_count):
        try:
            driver = setup_driver()
            first_valid_url = get_first_valid_url(driver, search_url)

            if not first_valid_url:
                return "No valid link found", "No valid link found"

            logging.info(f"Attempting to fetch content from: {first_valid_url}")
            driver.get(first_valid_url)
            wait_for_page_load(driver)

            # Additional wait for dynamic content
            time.sleep(3)
            scroll_to_bottom(driver)

            # Final wait after scrolling
            time.sleep(2)

            html = driver.page_source
            if not html or len(html) < 500:  # Simple check for valid HTML
                raise ValueError("Page source too short, likely loading failed")

            return extract_content_from_html(html)

        except Exception as e:
            logging.warning(f"Attempt {attempt + 1} failed: {str(e)[:200]}")
            if driver:
                driver.quit()
                driver = None
            if attempt == retry_count - 1:  # Last attempt
                return "Failed to fetch", f"Failed to fetch after {retry_count} attempts"
            time.sleep(5)  # Wait before retry
        finally:
            if driver:
                driver.quit()


# [Rest of the functions remain the same as they're not related to the scraping issue]


def parse_hotsearch_data(data: Dict) -> List[Dict]:
    """Parse hot search data with ranking information"""
    if not data or "data" not in data or "cards" not in data["data"]:
        return []

    hotsearch_list = data["data"]["cards"][0].get("content", [])
    top_content = data["data"]["cards"][0].get("topContent", [])

    parsed_data = []

    # 处理置顶内容（标记为"置顶"）
    for item in top_content:
        search_url = item.get("url", "")
        if not search_url.startswith('http'):
            search_url = f"https://www.baidu.com/s?wd={item.get('word', '')}"

        logging.info(f"Processing top hot search: {item.get('word', '')}")
        news_title, news_content = get_news_detail(search_url)

        parsed_data.append({
            "ranking": "置顶",  # 特殊标记置顶内容
            "hotsearch_title": item.get("word", ""),
            "hotsearch_url": search_url,
            "hot_index": item.get("hotScore", ""),
            "hotsearch_desc": item.get("desc", ""),
            "image_url": item.get("img", ""),
            "is_top": "是",
            "news_title": news_title,
            "news_content": news_content[:100000],
            "source": "百度热搜",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "tts": None,  # 新增的tts字段，boolean类型，内容为空
            "status": "processed",
            "broadcasted": False,
            "processed_at": datetime.now(),
        })

    # 处理普通热搜内容（数字排名）
    for idx, item in enumerate(hotsearch_list[:20], 1):
        search_url = item.get("url", "")
        if not search_url.startswith('http'):
            search_url = f"https://www.baidu.com/s?wd={item.get('word', '')}"

        logging.info(f"Processing hot search #{idx}: {item.get('word', '')}")
        news_title, news_content = get_news_detail(search_url)

        parsed_data.append({
            "ranking": str(idx),  # 数字排名（从1开始）
            "hotsearch_title": item.get("word", ""),
            "hotsearch_url": search_url,
            "hot_index": item.get("hotScore", ""),
            "hotsearch_desc": item.get("desc", ""),
            "image_url": item.get("img", ""),
            "is_top": "否",
            "news_title": news_title,
            "news_content": news_content[:100000],
            "source": "百度热搜",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "tts": None,  # 新增的tts字段，boolean类型，内容为空
            "status": "processed",
            "broadcasted": False,
            "processed_at": datetime.now()
        })

        time.sleep(2)

    return parsed_data


def connect_to_mongodb():
    """Connect to MongoDB and return client and collections"""
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection_read = db[COLLECTION_READ]
        collection_succ = db[COLLECTION_SUCC]
        collection_fail = db[COLLECTION_FAIL]
        client.server_info()
        logging.info("Connected to MongoDB successfully")
        return client, collection_read, collection_succ, collection_fail
    except Exception as e:
        logging.error(f"Failed to connect to MongoDB: {e}")
        return None, None, None, None


def filter_new_data(data: List[Dict], collections: List) -> List[Dict]:
    """
    过滤出 hotsearch_url 不存在于任一指定集合的数据，避免重复插入
    """
    existing_urls = set()
    for col in collections:
        try:
            urls = col.distinct("hotsearch_url")
            existing_urls.update(urls)
        except Exception as e:
            logging.error(f"Error fetching URLs from collection {col.name}: {e}")

    filtered = [item for item in data if item.get("hotsearch_url") not in existing_urls]
    logging.info(f"Filtered {len(data) - len(filtered)} duplicate entries; {len(filtered)} new entries remain")
    return filtered


def save_to_mongodb(data: List[Dict], collection) -> bool:
    """Save data to MongoDB"""
    if collection is None:
        logging.error("Cannot save to MongoDB: Invalid connection")
        return False

    try:
        if not data:
            logging.info("No new data to insert")
            return True
        result = collection.insert_many(data)
        logging.info(f"Successfully inserted {len(result.inserted_ids)} documents")
        return True
    except Exception as e:
        logging.error(f"Failed to save to MongoDB: {e}")
        return False


def main():
    """Main execution function"""
    client, collection_read, collection_succ, collection_fail = connect_to_mongodb()
    if not client:
        logging.error("No MongoDB connection, exiting")
        return

    logging.info("Fetching Baidu hot search data...")
    hotsearch_data = get_baidu_hotsearch_data()

    if not hotsearch_data:
        logging.error("Failed to fetch hot search data")
        return

    logging.info("Parsing hot search data...")
    parsed_data = parse_hotsearch_data(hotsearch_data)

    if not parsed_data:
        logging.warning("No valid data to save")
        return

    # 过滤重复数据
    collections = [collection_read, collection_succ, collection_fail]
    new_data = filter_new_data(parsed_data, collections)

    if not new_data:
        logging.info("No new data to insert after filtering duplicates")
        return

    logging.info("Saving data to MongoDB...")
    save_to_mongodb(new_data, collection_read)

    # 关闭 MongoDB 连接
    client.close()


if __name__ == "__main__":
    main()

import os
import re
import time
import logging
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
from readability import Document

# Configuration
MONGO_URI = os.getenv("MONGO_URI",
                      "mongodb+srv://newscrrawler:qwe123@crrawlercluster.eencizs.mongodb.net/?retryWrites=true&w=majority&appName=CrrawlerCluster")
DB_NAME = "mydatabase"
COLLECTION_READ = "read"
COLLECTION_SUCC = "analyzed_succ"
COLLECTION_FAIL = "analyzed_fail"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://top.baidu.com/board?tab=realtime'
}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_baidu_hotsearch_data() -> Optional[Dict]:
    """Fetch Baidu hot search data"""
    api_url = "https://top.baidu.com/api/board?tab=realtime"
    try:
        response = requests.get(api_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Failed to fetch hot search data: {e}")
        return None


def setup_driver() -> webdriver.Edge:
    """Setup and return a configured Edge WebDriver instance.

    Returns:
        webdriver.Edge: Configured Edge browser instance

    Raises:
        FileNotFoundError: If Edge driver is not found
        WebDriverException: If WebDriver initialization fails
    """
    # ==================== 1. 浏览器选项配置 ====================
    options = Options()

    # 无头模式配置（不显示浏览器窗口）
    options.add_argument("--headless=new")  # 新版Edge推荐使用"--headless=new"

    # 性能优化参数
    options.add_argument("--disable-gpu")  # 禁用GPU硬件加速（避免云环境兼容性问题）
    options.add_argument("--no-sandbox")  # 禁用沙盒（提升容器内运行稳定性）
    options.add_argument("--disable-dev-shm-usage")  # 限制/dev/shm使用（防止内存不足）

    # 调试与自动化参数
    options.add_argument("--remote-debugging-port=9222")  # 启用远程调试端口
    options.add_argument("--disable-blink-features=AutomationControlled")  # 禁用自动化控制标记

    # 窗口尺寸设置
    options.add_argument("--window-size=1920,1080")  # 设置浏览器窗口大小（影响部分网页布局）

    # ==================== 2. 用户代理和语言设置 ====================
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
    )  # 模拟Edge浏览器最新版用户代理

    options.add_argument("--lang=en-US,en")  # 设置浏览器语言为英文（减少地域化内容干扰）

    # ==================== 3. GitHub Actions专用配置 ====================
    if os.getenv('GITHUB_ACTIONS') == 'true':
        options.add_argument("--disable-extensions")  # 禁用所有扩展
        options.add_argument("--disable-software-rasterizer")  # 禁用软件光栅化
        options.add_argument("--disable-logging")  # 禁用冗余日志
        options.add_argument("--log-level=3")  # 日志级别设置为警告及以上
        options.add_argument("--single-process")  # 单进程模式（提升容器稳定性）

    # ==================== 4. 驱动路径配置 ====================
    try:
        # 动态获取项目根目录路径
        project_root = os.path.dirname(os.path.abspath(__file__))
        driver_path = os.path.join(project_root, "drivers", "msedgedriver")

        # 驱动文件存在性验证
        if not os.path.exists(driver_path):
            raise FileNotFoundError(
                f"EdgeDriver not found at {driver_path}. "
                f"Please download from https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/"
            )

        # 记录调试信息
        logging.info(f"Initializing Edge WebDriver from: {driver_path}")

        # ==================== 5. 服务配置 ====================
        service = Service(
            executable_path=driver_path,

            # 服务启动参数
            service_args=[
                '--verbose',  # 启用详细日志（调试时使用）
                '--log-path=edgedriver.log'  # 日志输出文件
            ] if logging.getLogger().level == logging.DEBUG else None
        )

        # GitHub Actions特殊配置
        if os.getenv('GITHUB_ACTIONS') == 'true':
            service.creation_flags = 0x80000000  # CREATE_NO_WINDOW flag (Windows)
            service.start()  # 显式启动服务（避免某些环境下的竞争条件）

        # ==================== 6. 浏览器实例化 ====================
        driver = webdriver.Edge(
            service=service,
            options=options,
            # 超时设置（单位：秒）
            service_executor_timeout=30,
            keep_alive=True  # 保持长连接
        )

        # ==================== 7. 反检测措施 ====================
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                    // 隐藏navigator.webdriver属性
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });

                    // 覆盖语言偏好
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });

                    // 模拟Chrome运行时对象
                    window.navigator.chrome = {
                        runtime: {},
                        loadTimes: () => {},
                        csi: () => {}
                    };
                """
            }
        )

        # 设置页面加载超时（毫秒）
        driver.set_page_load_timeout(30000)

        return driver

    except Exception as e:
        logging.error("WebDriver初始化失败", exc_info=True)
        raise


def is_valid_webpage_link(href: str) -> bool:
    """Check if a link is a valid external webpage"""
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
    return href.startswith('http') and not any(href.startswith(prefix) for prefix in invalid_prefixes)


def wait_for_page_load(driver: webdriver.Edge, timeout: int = 15) -> None:
    """Wait for page to load with extended timeout for GitHub Actions"""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
    except Exception as e:
        logging.warning(f"Page load timeout: {e}")


def scroll_to_bottom(driver: webdriver.Edge, scroll_pause_time: float = 1.5, max_scrolls: int = 5) -> None:
    """Scroll to bottom of page to load lazy content with adjusted parameters"""
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(max_scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_pause_time)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


def extract_content_from_html(html: str) -> Tuple[str, str]:
    """Extract title and content from HTML using readability with error handling"""
    try:
        doc = Document(html)
        title = doc.title() or "No title found"

        summary_html = doc.summary()
        soup = BeautifulSoup(summary_html, "html.parser")

        # Remove unwanted elements
        for element in soup(['script', 'style', 'iframe', 'nav', 'footer', 'aside']):
            element.decompose()

        content = soup.get_text(separator="\n", strip=True)
        content = re.sub(r'\n{3,}', '\n\n', content)  # Reduce excessive newlines

        return title, content[:100000]  # Directly truncate here
    except Exception as e:
        logging.error(f"Error extracting content: {e}")
        return "Failed to extract title", "Failed to extract content"


def get_first_valid_url(driver: webdriver.Edge, search_url: str) -> Optional[str]:
    """Find first valid URL from search results with improved reliability"""
    try:
        driver.get(search_url)
        wait_for_page_load(driver)
        time.sleep(3)  # Additional wait for search results to load

        # Try to click the "Web" tab if available
        try:
            web_tab = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a[data-index="0"]')))
            driver.execute_script("arguments[0].click();", web_tab)
            time.sleep(2)
        except Exception:
            pass  # Continue if web tab not found

        # Find all possible result containers
        containers = driver.find_elements(By.CSS_SELECTOR,
                                          'div.c-container, div.result, div.result-op, div[mu]')

        for container in containers:
            try:
                # Find all links in container and check them
                links = container.find_elements(By.CSS_SELECTOR, 'a[href]')
                for link in links:
                    href = link.get_attribute('href')
                    if href and is_valid_webpage_link(href):
                        logging.info(f"Found valid URL: {href}")
                        return href
            except Exception:
                continue

        logging.warning("No valid external links found in search results")
        return None

    except Exception as e:
        logging.error(f"Error finding valid URL: {e}")
        return None


def get_news_detail(search_url: str) -> Tuple[str, str]:
    """Get news details with improved error handling and retry logic"""
    driver = None
    retry_count = 2  # Number of retry attempts

    for attempt in range(retry_count):
        try:
            driver = setup_driver()
            first_valid_url = get_first_valid_url(driver, search_url)

            if not first_valid_url:
                return "No valid link found", "No valid link found"

            logging.info(f"Attempting to fetch content from: {first_valid_url}")
            driver.get(first_valid_url)
            wait_for_page_load(driver)

            # Additional wait for dynamic content
            time.sleep(3)
            scroll_to_bottom(driver)

            # Final wait after scrolling
            time.sleep(2)

            html = driver.page_source
            if not html or len(html) < 500:  # Simple check for valid HTML
                raise ValueError("Page source too short, likely loading failed")

            return extract_content_from_html(html)

        except Exception as e:
            logging.warning(f"Attempt {attempt + 1} failed: {str(e)[:200]}")
            if driver:
                driver.quit()
                driver = None
            if attempt == retry_count - 1:  # Last attempt
                return "Failed to fetch", f"Failed to fetch after {retry_count} attempts"
            time.sleep(5)  # Wait before retry
        finally:
            if driver:
                driver.quit()


def parse_hotsearch_data(data: Dict) -> List[Dict]:
    """Parse hot search data with ranking information"""
    if not data or "data" not in data or "cards" not in data["data"]:
        return []

    hotsearch_list = data["data"]["cards"][0].get("content", [])
    top_content = data["data"]["cards"][0].get("topContent", [])

    parsed_data = []

    # 处理置顶内容（标记为"置顶"）
    for item in top_content:
        search_url = item.get("url", "")
        if not search_url.startswith('http'):
            search_url = f"https://www.baidu.com/s?wd={item.get('word', '')}"

        logging.info(f"Processing top hot search: {item.get('word', '')}")
        news_title, news_content = get_news_detail(search_url)

        parsed_data.append({
            "ranking": "置顶",  # 特殊标记置顶内容
            "hotsearch_title": item.get("word", ""),
            "hotsearch_url": search_url,
            "hot_index": item.get("hotScore", ""),
            "hotsearch_desc": item.get("desc", ""),
            "image_url": item.get("img", ""),
            "is_top": "是",
            "news_title": news_title,
            "news_content": news_content[:100000],
            "source": "百度热搜",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "tts": None,  # 新增的tts字段，boolean类型，内容为空
            "status": "processed",
            "broadcasted": False,
            "processed_at": datetime.now(),
        })

    # 处理普通热搜内容（数字排名）
    for idx, item in enumerate(hotsearch_list[:20], 1):
        search_url = item.get("url", "")
        if not search_url.startswith('http'):
            search_url = f"https://www.baidu.com/s?wd={item.get('word', '')}"

        logging.info(f"Processing hot search #{idx}: {item.get('word', '')}")
        news_title, news_content = get_news_detail(search_url)

        parsed_data.append({
            "ranking": str(idx),  # 数字排名（从1开始）
            "hotsearch_title": item.get("word", ""),
            "hotsearch_url": search_url,
            "hot_index": item.get("hotScore", ""),
            "hotsearch_desc": item.get("desc", ""),
            "image_url": item.get("img", ""),
            "is_top": "否",
            "news_title": news_title,
            "news_content": news_content[:100000],
            "source": "百度热搜",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "tts": None,  # 新增的tts字段，boolean类型，内容为空
            "status": "processed",
            "broadcasted": False,
            "processed_at": datetime.now()
        })

        time.sleep(2)

    return parsed_data


def connect_to_mongodb():
    """Connect to MongoDB and return client and collections"""
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection_read = db[COLLECTION_READ]
        collection_succ = db[COLLECTION_SUCC]
        collection_fail = db[COLLECTION_FAIL]
        client.server_info()
        logging.info("Connected to MongoDB successfully")
        return client, collection_read, collection_succ, collection_fail
    except Exception as e:
        logging.error(f"Failed to connect to MongoDB: {e}")
        return None, None, None, None


def filter_new_data(data: List[Dict], collections: List) -> List[Dict]:
    """
    过滤出 hotsearch_url 不存在于任一指定集合的数据，避免重复插入
    """
    existing_urls = set()
    for col in collections:
        try:
            urls = col.distinct("hotsearch_url")
            existing_urls.update(urls)
        except Exception as e:
            logging.error(f"Error fetching URLs from collection {col.name}: {e}")

    filtered = [item for item in data if item.get("hotsearch_url") not in existing_urls]
    logging.info(f"Filtered {len(data) - len(filtered)} duplicate entries; {len(filtered)} new entries remain")
    return filtered


def save_to_mongodb(data: List[Dict], collection) -> bool:
    """Save data to MongoDB"""
    if collection is None:
        logging.error("Cannot save to MongoDB: Invalid connection")
        return False

    try:
        if not data:
            logging.info("No new data to insert")
            return True
        result = collection.insert_many(data)
        logging.info(f"Successfully inserted {len(result.inserted_ids)} documents")
        return True
    except Exception as e:
        logging.error(f"Failed to save to MongoDB: {e}")
        return False


def main():
    """Main execution function"""
    client, collection_read, collection_succ, collection_fail = connect_to_mongodb()
    if not client:
        logging.error("No MongoDB connection, exiting")
        return

    logging.info("Fetching Baidu hot search data...")
    hotsearch_data = get_baidu_hotsearch_data()

    if not hotsearch_data:
        logging.error("Failed to fetch hot search data")
        return

    logging.info("Parsing hot search data...")
    parsed_data = parse_hotsearch_data(hotsearch_data)

    if not parsed_data:
        logging.warning("No valid data to save")
        return

    # 过滤重复数据
    collections = [collection_read, collection_succ, collection_fail]
    new_data = filter_new_data(parsed_data, collections)

    if not new_data:
        logging.info("No new data to insert after filtering duplicates")
        return

    logging.info("Saving data to MongoDB...")
    save_to_mongodb(new_data, collection_read)

    # 关闭 MongoDB 连接
    client.close()


if __name__ == "__main__":
    main()