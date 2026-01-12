from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
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
        logging.FileHandler('instagram_followers_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class InstagramFollowersScraper:

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

            password_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "password"))
            )
            self.simulate_human_typing(password_input, self.password)

            login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
            )

            ActionChains(self.driver).move_to_element(login_button).click().perform()
            time.sleep(15)

            try:
                WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//button[contains(text(), 'Not Now') or contains(text(), 'Not now')]")
                    )
                ).click()
            except TimeoutException:
                pass

            return True
        except Exception:
            return False

    def navigate_to_profile(self, profile_url):
        self.driver.get(profile_url)
        time.sleep(random.uniform(4, 6))

    def click_followers_button(self):
        try:
            followers_link = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/followers/')]"))
            )
            followers_link.click()
            time.sleep(random.uniform(3, 5))
            return True
        except Exception:
            return False

    def scroll_followers_popup(self):
        try:
            return WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@role='dialog']//div[contains(@class, 'x1dm5mii')]")
                )
            )
        except Exception:
            return None

    def extract_followers_from_popup(self):
        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        followers = set()

        for span in soup.find_all('span', class_='_ap3a'):
            username = span.get_text(strip=True)
            if username:
                followers.add(username)

        return followers

    def scrape_all_followers(self, profile_url, max_followers=None, save_interval=50):
        self.navigate_to_profile(profile_url)

        if not self.click_followers_button():
            return None

        popup_div = self.scroll_followers_popup()
        if not popup_div:
            return None

        all_followers = set()
        last_count = 0
        no_change = 0

        while True:
            current = self.extract_followers_from_popup()
            all_followers.update(current)

            if max_followers and len(all_followers) >= max_followers:
                break

            if len(all_followers) == last_count:
                no_change += 1
                if no_change >= 5:
                    break
            else:
                no_change = 0

            last_count = len(all_followers)

            try:
                self.driver.execute_script(
                    "arguments[0].scrollTop = arguments[0].scrollHeight", popup_div
                )
                time.sleep(random.uniform(2, 4))
            except StaleElementReferenceException:
                popup_div = self.scroll_followers_popup()
                if not popup_div:
                    break

        return {
            "profile_url": profile_url,
            "total_followers": len(all_followers),
            "followers": sorted(all_followers),
            "scraped_at": datetime.now().isoformat()
        }

    def save_to_json(self, data, filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def save_to_csv(self, data, filename):
        pd.DataFrame({"username": data["followers"]}).to_csv(
            filename, index=False, encoding="utf-8-sig"
        )

    def save_to_txt(self, data, filename):
        with open(filename, "w", encoding="utf-8") as f:
            for u in data["followers"]:
                f.write(u + "\n")

    def close(self):
        if self.driver:
            self.driver.quit()


if __name__ == "__main__":
    USERNAME = "INSTAGRAM_USERNAME_PLACEHOLDER"
    PASSWORD = "INSTAGRAM_PASSWORD_PLACEHOLDER"
    PROFILE_URL = "https://www.instagram.com/PROFILE_USERNAME/"
    MAX_FOLLOWERS = None
    HEADLESS = True

    os.makedirs("output", exist_ok=True)

    scraper = InstagramFollowersScraper(USERNAME, PASSWORD)
    scraper.initialize_driver(headless=HEADLESS)

    if scraper.login():
        data = scraper.scrape_all_followers(PROFILE_URL, MAX_FOLLOWERS)

        if data:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            scraper.save_to_json(data, f"output/followers_{ts}.json")
            scraper.save_to_csv(data, f"output/followers_{ts}.csv")
            scraper.save_to_txt(data, f"output/followers_{ts}.txt")

    scraper.close()
