from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import time
import random
import pandas as pd
import json
import os
import re
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('instagram_selenium_scraper.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class InstagramScraper:

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.driver = None

    def initialize_driver(self, headless=True):
        options = webdriver.EdgeOptions()

        if headless:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1920,1080")

        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        if not headless:
            options.add_argument("--start-maximized")

        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        )

        self.driver = webdriver.Edge(options=options)
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

    def simulate_human_typing(self, element, text):
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.1, 0.3))
            if random.random() < 0.1:
                time.sleep(random.uniform(0.3, 0.7))

    def login(self):
        try:
            self.driver.get("https://www.instagram.com/accounts/login/")
            time.sleep(random.uniform(3, 5))

            username_input = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            self.simulate_human_typing(username_input, self.username)

            time.sleep(random.uniform(1, 2))

            password_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "password"))
            )
            self.simulate_human_typing(password_input, self.password)

            time.sleep(random.uniform(1, 2))

            login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
            )

            ActionChains(self.driver).move_to_element(login_button).click().perform()

            time.sleep(15)

            try:
                not_now = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//button[contains(text(), 'Not Now') or contains(text(), 'Not now')]")
                    )
                )
                not_now.click()
            except TimeoutException:
                pass

            try:
                not_now = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Not Now')]"))
                )
                not_now.click()
            except TimeoutException:
                pass

            return True

        except Exception:
            return False

    def navigate_to_profile(self, profile_url):
        self.driver.get(profile_url)
        time.sleep(random.uniform(4, 6))

    def slow_scroll(self, step=500):
        self.driver.execute_script(f"window.scrollBy(0, {step});")
        time.sleep(random.uniform(2, 3))

    def get_profile_stats(self):
        soup = BeautifulSoup(self.driver.page_source, "html.parser")

        stats = {"followers": None, "following": None, "posts": None}

        meta = soup.find("meta", {"name": "description"})
        if meta:
            text = meta.get("content", "")
            for key in stats:
                match = re.search(r"([\d,.]+[KMB]?)\s+" + key, text, re.I)
                if match:
                    stats[key] = match.group(1)

        return stats

    def detect_content_type(self, soup):
        if soup.find("video"):
            return "video"
        if soup.find("img"):
            return "image"
        return "unknown"

    def extract_posts_with_bs(self):
        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        posts = []
        seen = set()

        for a in soup.find_all("a", href=True):
            if re.match(r"^/[^/]+/(p|reel)/", a["href"]):
                link = "https://www.instagram.com" + a["href"].split("?")[0]
                if link in seen:
                    continue
                seen.add(link)

                posts.append({
                    "post_link": link,
                    "content_type": None,
                    "media_url": None,
                    "caption": None,
                    "mentions": [],
                    "likes": None,
                    "comments": None,
                    "post_time": None
                })

        return posts

    def click_and_extract_post_details(self, post_url):
        self.driver.get(post_url)
        time.sleep(random.uniform(3, 5))

        soup = BeautifulSoup(self.driver.page_source, "html.parser")

        post = {
            "post_link": post_url,
            "content_type": "video" if soup.find("video") else "image",
            "media_url": None,
            "caption": None,
            "mentions": [],
            "likes": None,
            "comments": None,
            "post_time": None
        }

        img = soup.find("img")
        if img:
            post["media_url"] = img.get("src")
            post["caption"] = img.get("alt")
            if post["caption"]:
                post["mentions"] = list(set(re.findall(r"@(\w+)", post["caption"])))

        time_tag = soup.find("time")
        if time_tag:
            post["post_time"] = time_tag.get("datetime")

        return post

    def scrape_posts(self, profile_url, max_posts=50, detailed=False):
        self.navigate_to_profile(profile_url)
        stats = self.get_profile_stats()
        all_posts = []

        while len(all_posts) < max_posts:
            posts = self.extract_posts_with_bs()
            all_posts.extend(posts)
            all_posts = list({p["post_link"]: p for p in all_posts}.values())
            self.slow_scroll()

        all_posts = all_posts[:max_posts]

        if detailed:
            detailed_posts = []
            for post in all_posts:
                detailed_posts.append(self.click_and_extract_post_details(post["post_link"]))
            all_posts = detailed_posts

        return {
            "profile_url": profile_url,
            "stats": stats,
            "posts": all_posts,
            "scraped_at": datetime.now().isoformat()
        }

    def save_to_json(self, data, filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def save_to_csv(self, data, filename):
        pd.DataFrame(data["posts"]).to_csv(filename, index=False, encoding="utf-8-sig")

    def save_to_excel(self, data, filename):
        with pd.ExcelWriter(filename, engine="openpyxl") as writer:
            pd.DataFrame([data["stats"]]).to_excel(writer, sheet_name="Profile Stats", index=False)
            pd.DataFrame(data["posts"]).to_excel(writer, sheet_name="Posts", index=False)

    def close(self):
        if self.driver:
            self.driver.quit()


if __name__ == "__main__":

    INSTAGRAM_USERNAME = "YOUR_INSTAGRAM_USERNAME"
    INSTAGRAM_PASSWORD = "YOUR_INSTAGRAM_PASSWORD"
    PROFILE_URL = "https://www.instagram.com/PROFILE_NAME/"
    MAX_POSTS = 3
    DETAILED = True
    HEADLESS = True

    os.makedirs("output", exist_ok=True)

    scraper = InstagramScraper(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)

    try:
        scraper.initialize_driver(headless=HEADLESS)
        if scraper.login():
            data = scraper.scrape_posts(PROFILE_URL, MAX_POSTS, DETAILED)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            scraper.save_to_json(data, f"output/data_{ts}.json")
            scraper.save_to_csv(data, f"output/posts_{ts}.csv")
            scraper.save_to_excel(data, f"output/data_{ts}.xlsx")
    finally:
        scraper.close()
