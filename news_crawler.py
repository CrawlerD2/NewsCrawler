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
COLLECTION_NAME = "raw_read"
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
        response = requests.get(api_url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Failed to fetch hot search data: {e}")
        return None


def setup_driver() -> webdriver.Edge:
    """Setup and return WebDriver instance"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # Cache the driver to avoid repeated downloads
    driver_path = EdgeChromiumDriverManager().install()
    service = Service(driver_path)
    driver = webdriver.Edge(service=service, options=options)

    # Anti-detection
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        """
    })
    return driver


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
    return not any(href.startswith(prefix) for prefix in invalid_prefixes)


def wait_for_page_load(driver: webdriver.Edge, timeout: int = 10) -> None:
    """Wait for page to load"""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    except Exception as e:
        logging.warning(f"Page load timeout: {e}")


def scroll_to_bottom(driver: webdriver.Edge, scroll_pause_time: float = 1.0, max_scrolls: int = 10) -> None:
    """Scroll to bottom of page to load lazy content"""
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(max_scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_pause_time)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


def extract_content_from_html(html: str) -> Tuple[str, str]:
    """Extract title and content from HTML using readability"""
    doc = Document(html)
    title = doc.title()
    summary_html = doc.summary()

    soup = BeautifulSoup(summary_html, "html.parser")
    content = soup.get_text(separator="\n", strip=True)

    return title, content


def get_first_valid_url(driver: webdriver.Edge, search_url: str) -> Optional[str]:
    """Find first valid URL from search results"""
    driver.get(search_url)
    wait_for_page_load(driver)
    time.sleep(3)

    # Try to click "Web" tab if available
    try:
        web_tab = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[data-index="0"]')))
        web_tab.click()
        time.sleep(3)
    except Exception:
        pass

    # Find first valid link
    containers = driver.find_elements(By.CSS_SELECTOR, 'div.c-container, div.result')
    for container in containers:
        try:
            a = container.find_element(By.CSS_SELECTOR, 'a[href]')
            href = a.get_attribute('href')
            if is_valid_webpage_link(href):
                return href
        except Exception:
            continue
    return None


def get_news_detail(search_url: str) -> Tuple[str, str]:
    """Get news details (title and content) from a search URL"""
    driver = None
    try:
        driver = setup_driver()
        first_valid_url = get_first_valid_url(driver, search_url)

        if not first_valid_url:
            return "No valid link found", "No valid link found"

        driver.get(first_valid_url)
        wait_for_page_load(driver)
        scroll_to_bottom(driver)

        html = driver.page_source
        return extract_content_from_html(html)
    except Exception as e:
        logging.error(f"Failed to get news details: {str(e)[:200]}")
        return "Failed to fetch", "Failed to fetch"
    finally:
        if driver:
            driver.quit()


def parse_hotsearch_data(data: Dict) -> List[Dict]:
    """Parse hot search data"""
    if not data or "data" not in data or "cards" not in data["data"]:
        return []

    hotsearch_list = data["data"]["cards"][0].get("content", [])
    top_content = data["data"]["cards"][0].get("topContent", [])

    parsed_data = []
    for idx, item in enumerate((top_content + hotsearch_list)[:3], 1):
        search_url = item.get("url", "")
        if not search_url.startswith('http'):
            search_url = f"https://www.baidu.com/s?wd={item.get('word', '')}"

        logging.info(f"Processing hot search #{idx}: {item.get('word', '')}")
        news_title, news_content = get_news_detail(search_url)

        parsed_data.append({
            "hotsearch_title": item.get("word", ""),
            "hotsearch_url": search_url,
            "hot_index": item.get("hotScore", ""),
            "hotsearch_desc": item.get("desc", ""),
            "image_url": item.get("img", ""),
            "is_top": "是" if item in top_content else "否",
            "news_title": news_title,
            "news_content": news_content[:100000],  # Limit content length
            "source": "百度热搜",
            "crawl_time": datetime.now(),
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        })

        time.sleep(2)

    return parsed_data


def connect_to_mongodb():
    """Connect to MongoDB and return collection"""
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        client.server_info()  # Test connection
        logging.info("Connected to MongoDB successfully")
        return collection
    except Exception as e:
        logging.error(f"Failed to connect to MongoDB: {e}")
        return None


def save_to_mongodb(data: List[Dict], collection) -> bool:
    """Save data to MongoDB"""
    if collection is None:
        logging.error("Cannot save to MongoDB: Invalid connection")
        return False

    try:
        result = collection.insert_many(data)
        logging.info(f"Successfully inserted {len(result.inserted_ids)} documents")
        return True
    except Exception as e:
        logging.error(f"Failed to save to MongoDB: {e}")
        return False


def main():
    """Main execution function"""
    collection = connect_to_mongodb()

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

    if collection is not None:
        logging.info("Saving data to MongoDB...")
        save_to_mongodb(parsed_data, collection)
    else:
        logging.error("No MongoDB connection available")


if __name__ == "__main__":
    main()
