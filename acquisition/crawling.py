# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import os
import shutil
import time
import glob
import logging
import zipfile
import subprocess

LOG_DIR = os.path.join(os.getcwd(), "logs")
LOG_FILE = os.path.join(LOG_DIR, "crawling_scheduler.log")
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
DATA_DIR = os.path.join(os.getcwd(), "data")
HDFS_PATH = "/user/maria_dev/team8"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

name_mapping = {
    "서울": "seoul",
    "부산": "busan",
    "대구": "daegu",
    "인천": "incheon",
    "광주": "gwangju",
    "대전": "daejeon",
    "울산": "ulsan",
    "세종": "sejong",
    "경기": "gyeonggi",
    "강원": "gangwon",
    "충북": "chungbuk",
    "충남": "chungnam",
    "전북": "jeonbuk",
    "전남": "jeonnam",
    "경북": "gyeongbuk",
    "경남": "gyeongnam",
    "제주": "jeju",
}


def setup_download_dir():
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)


def setup_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


def setup_chrome_options(chrome_options):
    chrome_options.binary_location = "/usr/bin/chromium-browser"
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-setuid-sandbox")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": DOWNLOAD_DIR,
            "download.prompt_for_download": False,
        },
    )

    return chrome_options


def setup_webdriver():
    chrome_options = webdriver.ChromeOptions()
    setup_chrome_options(chrome_options)
    # service = Service(ChromeDriverManager().install())
    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)

    return driver


def wait_for_download():
    file = os.path.join(DOWNLOAD_DIR, "소상공인시장진흥공단_상가(상권)정보_*.zip")
    while not glob.glob(file):
        print("waiting")
        time.sleep(1)

    return glob.glob(file)[0]


def convert_to_parquet(zip_file):
    setup_data_dir()

    try:
        with zipfile.ZipFile(os.path.join(DOWNLOAD_DIR, zip_file), "r") as file:
            file.extractall(DOWNLOAD_DIR)

        csv_files = glob.glob(os.path.join(DOWNLOAD_DIR, "*.csv"))

        for csv_file in csv_files:
            df = pd.read_csv(csv_file, encoding="utf-8", low_memory=False)
            df["층정보"] = df["층정보"].astype(str)

            title = os.path.basename(csv_file).split("_")[2]
            english_title = name_mapping.get(title, title)
            parquet_filename = f"{english_title}.parquet"
            parquet_file = os.path.join(DATA_DIR, parquet_filename)

            df.to_parquet(parquet_file, engine="pyarrow")

            logging.info(f">> 파일 변환: {os.path.basename(parquet_filename)}")
            print(f">> 파일 변환: {os.path.basename(parquet_filename)}")
    except Exception as e:
        logging.error(">> 파일 변환 실패")
        print(">> 파일 변환 실패")
        logging.error(str(e))


def upload_to_hdfs():
    try:
        subprocess.run(
            ["hdfs", "dfs", "-rm", "-r", f"{HDFS_PATH}/data"], capture_output=True
        )
        command = ["hdfs", "dfs", "-put", DATA_DIR, HDFS_PATH]
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode == 0:
            logging.info(f">> HDFS 업로드: {DATA_DIR} > {HDFS_PATH}")
            print(f">> HDFS 업로드: {DATA_DIR} > {HDFS_PATH}")
        else:
            logging.error(f">> HDFS 업로드 실패")
            print(f">> HDFS 업로드 실패")
            logging.error(result.stderr)

    except Exception as e:
        logging.error(">> HDFS 업로드 실패")
        print(">> HDFS 업로드 실패")
        logging.error(str(e))


def clean_up():
    shutil.rmtree(DOWNLOAD_DIR)


def main():
    setup_download_dir()
    driver = setup_webdriver()

    try:
        driver.get("https://www.data.go.kr/index.do")

        search_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input#keyword"))
        )
        search_input.send_keys("소상공인시장진흥공단_상가(상권)정보")

        search_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-search"))
        )
        search_button.click()

        first_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "#fileDataList > div.result-list > ul > li:nth-child(1) > div.bottom-area > a",
                )
            )
        )
        first_element.click()

        file = wait_for_download()
        logging.info(f">> 파일 다운로드: {file}")
        print(f">> 파일 다운로드: {file}")

        return file

    except Exception as e:
        logging.error(">> 파일 다운로드 실패")
        print(">> 파일 다운로드 실패")
        logging.error(str(e))

    finally:
        driver.quit()


if __name__ == "__main__":
    zip_file = main()
    convert_to_parquet(zip_file)
    upload_to_hdfs()
    clean_up()
