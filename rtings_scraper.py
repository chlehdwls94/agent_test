#!/usr/bin/env python3
"""
RTINGS.com TV 제품 정보 크롤링 및 BigQuery 업데이트 스크립트

이 스크립트는 RTINGS.com에서 TV 제품 정보를 크롤링하여
products.json 파일을 업데이트하고 BigQuery에 자동으로 로드합니다.

사용법:
    python rtings_scraper.py

필요한 패키지:
    pip install requests beautifulsoup4 selenium webdriver-manager google-cloud-bigquery
"""

import json
import os
import time
import logging
import re
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from google.cloud import bigquery

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rtings_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TVProduct:
    """TV 제품 정보를 저장하는 데이터 클래스"""
    product_id: str
    brand: str
    product_name: str
    product_type: str = "TV"
    specs: Dict = None
    rtings_scores: Dict = None
    price_usd: Dict = None
    summary: str = ""

class RTINGSscraper:
    """RTINGS.com 크롤링 클래스"""
    
    def __init__(self):
        self.base_url = "https://www.rtings.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.driver = None
        self.products = []
        
    def setup_driver(self):
        """Selenium WebDriver 설정"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            
            self.driver = webdriver.Chrome(
                ChromeDriverManager().install(),
                options=chrome_options
            )
            logger.info("WebDriver 설정 완료")
        except Exception as e:
            logger.error(f"WebDriver 설정 실패: {e}")
            raise
    
    def close_driver(self):
        """WebDriver 종료"""
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver 종료")
    
    def get_tv_list_page(self) -> List[str]:
        """TV 목록 페이지에서 모든 TV 링크 수집"""
        tv_links = []
        
        try:
            # RTINGS.com TV 리뷰 페이지
            tv_list_url = "https://www.rtings.com/tv/reviews"
            
            if self.driver:
                self.driver.get(tv_list_url)
                time.sleep(3)
                
                # 페이지 로딩 대기
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "product-card"))
                )
                
                # 모든 TV 링크 수집
                product_cards = self.driver.find_elements(By.CLASS_NAME, "product-card")
                
                for card in product_cards:
                    try:
                        link_element = card.find_element(By.TAG_NAME, "a")
                        href = link_element.get_attribute("href")
                        if href and "/tv/reviews/" in href:
                            tv_links.append(href)
                    except NoSuchElementException:
                        continue
                
                logger.info(f"총 {len(tv_links)}개의 TV 링크를 수집했습니다")
                
            else:
                # requests를 사용한 대체 방법
                response = self.session.get(tv_list_url)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                links = soup.find_all('a', href=True)
                for link in links:
                    href = link['href']
                    if '/tv/reviews/' in href and href not in tv_links:
                        tv_links.append(urljoin(self.base_url, href))
                
                logger.info(f"requests로 {len(tv_links)}개의 TV 링크를 수집했습니다")
                
        except Exception as e:
            logger.error(f"TV 링크 수집 실패: {e}")
        
        return tv_links
    
    def extract_product_info(self, url: str) -> Optional[TVProduct]:
        """개별 TV 제품 페이지에서 정보 추출"""
        try:
            if self.driver:
                self.driver.get(url)
                time.sleep(2)
                
                # 제품명 추출
                try:
                    title_element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
                    )
                    product_name = title_element.text.strip()
                except TimeoutException:
                    logger.warning(f"제품명을 찾을 수 없습니다: {url}")
                    return None
                
                # 브랜드 추출 (제품명에서 첫 번째 단어)
                brand = product_name.split()[0] if product_name else "Unknown"
                
                # 제품 ID 생성
                product_id = f"tv-{brand.lower()}-{self.generate_product_id(product_name)}"
                
                # 사양 정보 추출
                specs = self.extract_specs()
                
                # RTINGS 점수 추출
                rtings_scores = self.extract_rtings_scores()
                
                # 가격 정보 추출 (실제 가격은 외부 사이트에서 가져와야 함)
                price_usd = self.extract_price_info()
                
                # 요약 정보 추출
                summary = self.extract_summary()
                
                product = TVProduct(
                    product_id=product_id,
                    brand=brand,
                    product_name=product_name,
                    specs=specs,
                    rtings_scores=rtings_scores,
                    price_usd=price_usd,
                    summary=summary
                )
                
                logger.info(f"제품 정보 추출 완료: {product_name}")
                return product
                
        except Exception as e:
            logger.error(f"제품 정보 추출 실패 ({url}): {e}")
            return None
    
    def extract_specs(self) -> Dict:
        """사양 정보 추출"""
        specs = {
            "sizes": [55, 65],  # 기본값
            "type": "LED",      # 기본값
            "resolution": "4k", # 기본값
            "refresh_rate": "60 Hz",  # 기본값
            "peak_brightness_hdr_nits": 500,  # 기본값
            "input_lag_1080p_ms": 15.0,  # 기본값
            "vrr_support": "HDMI Forum VRR"  # 기본값
        }
        
        try:
            # 사양 테이블 찾기
            spec_tables = self.driver.find_elements(By.CSS_SELECTOR, ".spec-table, .specs-table")
            
            for table in spec_tables:
                rows = table.find_elements(By.TAG_NAME, "tr")
                
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 2:
                        spec_name = cells[0].text.strip().lower()
                        spec_value = cells[1].text.strip()
                        
                        # 사양 매핑
                        if "panel type" in spec_name or "display type" in spec_name:
                            specs["type"] = self.normalize_panel_type(spec_value)
                        elif "resolution" in spec_name:
                            specs["resolution"] = self.normalize_resolution(spec_value)
                        elif "refresh rate" in spec_name:
                            specs["refresh_rate"] = self.normalize_refresh_rate(spec_value)
                        elif "peak brightness" in spec_name:
                            brightness = self.extract_number(spec_value)
                            if brightness:
                                specs["peak_brightness_hdr_nits"] = brightness
                        elif "input lag" in spec_name:
                            lag = self.extract_number(spec_value)
                            if lag:
                                specs["input_lag_1080p_ms"] = lag
                        elif "vrr" in spec_name or "variable refresh" in spec_name:
                            specs["vrr_support"] = spec_value
                            
        except Exception as e:
            logger.warning(f"사양 정보 추출 중 오류: {e}")
        
        return specs
    
    def extract_rtings_scores(self) -> Dict:
        """RTINGS 점수 추출"""
        scores = {
            "mixed_usage": 7.0,
            "movies": 7.0,
            "tv_shows": 7.0,
            "sports": 7.0,
            "video_games": 7.0
        }
        
        try:
            # 점수 섹션 찾기
            score_elements = self.driver.find_elements(By.CSS_SELECTOR, ".score, .rating")
            
            for element in score_elements:
                text = element.text.strip()
                score_value = self.extract_number(text)
                
                if score_value:
                    # 점수 유형 판별
                    parent_text = element.find_element(By.XPATH, "..").text.lower()
                    
                    if "mixed" in parent_text or "overall" in parent_text:
                        scores["mixed_usage"] = score_value
                    elif "movie" in parent_text:
                        scores["movies"] = score_value
                    elif "tv show" in parent_text or "show" in parent_text:
                        scores["tv_shows"] = score_value
                    elif "sport" in parent_text:
                        scores["sports"] = score_value
                    elif "game" in parent_text:
                        scores["video_games"] = score_value
                        
        except Exception as e:
            logger.warning(f"RTINGS 점수 추출 중 오류: {e}")
        
        return scores
    
    def extract_price_info(self) -> Dict:
        """가격 정보 추출 (기본값 반환)"""
        # 실제 가격은 외부 사이트에서 가져와야 함
        return {
            "55": 1000,
            "65": 1500,
            "75": 2000
        }
    
    def extract_summary(self) -> str:
        """요약 정보 추출"""
        try:
            # 요약 섹션 찾기
            summary_elements = self.driver.find_elements(By.CSS_SELECTOR, ".summary, .overview, .description")
            
            for element in summary_elements:
                text = element.text.strip()
                if len(text) > 50:  # 충분한 길이의 텍스트
                    return text[:500]  # 500자로 제한
                    
        except Exception as e:
            logger.warning(f"요약 정보 추출 중 오류: {e}")
        
        return "RTINGS.com에서 추출한 TV 제품입니다."
    
    def normalize_panel_type(self, panel_type: str) -> str:
        """패널 타입 정규화"""
        panel_type = panel_type.lower()
        if "oled" in panel_type:
            return "OLED"
        elif "qled" in panel_type or "quantum" in panel_type:
            return "LED"
        elif "mini led" in panel_type:
            return "LED"
        else:
            return "LED"
    
    def normalize_resolution(self, resolution: str) -> str:
        """해상도 정규화"""
        resolution = resolution.lower()
        if "8k" in resolution:
            return "8k"
        elif "4k" in resolution or "uhd" in resolution:
            return "4k"
        elif "1080p" in resolution or "fhd" in resolution:
            return "1080p"
        else:
            return "4k"
    
    def normalize_refresh_rate(self, refresh_rate: str) -> str:
        """주사율 정규화"""
        refresh_rate = refresh_rate.lower()
        if "144" in refresh_rate:
            return "144 Hz"
        elif "120" in refresh_rate:
            return "120 Hz"
        elif "60" in refresh_rate:
            return "60 Hz"
        else:
            return "60 Hz"
    
    def extract_number(self, text: str) -> Optional[float]:
        """텍스트에서 숫자 추출"""
        try:
            # 숫자와 소수점만 추출
            numbers = re.findall(r'\d+\.?\d*', text)
            if numbers:
                return float(numbers[0])
        except ValueError:
            pass
        return None
    
    def generate_product_id(self, product_name: str) -> str:
        """제품명에서 제품 ID 생성"""
        # 특수문자 제거하고 소문자로 변환
        clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', product_name)
        clean_name = clean_name.lower().replace(' ', '-')
        
        # 길이 제한
        if len(clean_name) > 20:
            clean_name = clean_name[:20]
        
        return clean_name
    
    def scrape_all_products(self) -> List[TVProduct]:
        """모든 TV 제품 정보 크롤링"""
        logger.info("RTINGS.com 크롤링 시작")
        
        try:
            self.setup_driver()
            
            # TV 링크 수집
            tv_links = self.get_tv_list_page()
            
            if not tv_links:
                logger.error("TV 링크를 찾을 수 없습니다")
                return []
            
            # 각 TV 제품 정보 추출
            for i, link in enumerate(tv_links[:50]):  # 처음 50개만 처리 (테스트용)
                logger.info(f"처리 중 ({i+1}/{min(50, len(tv_links))}): {link}")
                
                product = self.extract_product_info(link)
                if product:
                    self.products.append(product)
                
                # 요청 간격 조절
                time.sleep(2)
            
            logger.info(f"총 {len(self.products)}개의 제품 정보를 수집했습니다")
            
        except Exception as e:
            logger.error(f"크롤링 중 오류 발생: {e}")
        finally:
            self.close_driver()
        
        return self.products
    
    def save_to_json(self, filename: str = "products.json"):
        """수집한 제품 정보를 JSON 파일로 저장"""
        try:
            # 기존 파일이 있으면 로드
            existing_products = []
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    existing_products = json.load(f)
                logger.info(f"기존 {len(existing_products)}개 제품 로드")
            
            # 새로운 제품 추가
            new_products = []
            existing_ids = {p.get('product_id') for p in existing_products}
            
            for product in self.products:
                if product.product_id not in existing_ids:
                    product_dict = {
                        "product_id": product.product_id,
                        "brand": product.brand,
                        "product_name": product.product_name,
                        "product_type": product.product_type,
                        "specs": product.specs,
                        "rtings_scores": product.rtings_scores,
                        "price_usd": product.price_usd,
                        "summary": product.summary
                    }
                    new_products.append(product_dict)
                    existing_products.append(product_dict)
            
            # 파일 저장
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(existing_products, f, indent=2, ensure_ascii=False)
            
            logger.info(f"{len(new_products)}개의 새 제품을 추가했습니다")
            logger.info(f"총 {len(existing_products)}개의 제품이 저장되었습니다")
            
        except Exception as e:
            logger.error(f"JSON 파일 저장 실패: {e}")

class BigQueryUpdater:
    """BigQuery 업데이트 클래스"""
    
    def __init__(self):
        self.project_id = self.get_project_id()
        self.client = bigquery.Client(project=self.project_id)
    
    def get_project_id(self) -> str:
        """프로젝트 ID 가져오기"""
        try:
            with open("image_agent/.env", "r") as f:
                for line in f:
                    if line.strip().startswith("GOOGLE_CLOUD_PROJECT="):
                        return line.strip().split('=')[1]
        except FileNotFoundError:
            logger.error("image_agent/.env 파일을 찾을 수 없습니다")
            return None
    
    def update_bigquery(self, json_file: str = "products.json"):
        """BigQuery 테이블 업데이트"""
        try:
            table_id = f"{self.project_id}.product_recommendations.products"
            
            # 테이블 존재 확인
            try:
                self.client.get_table(table_id)
            except Exception:
                logger.error(f"BigQuery 테이블 {table_id}가 존재하지 않습니다")
                return False
            
            # JSON 파일 읽기
            with open(json_file, 'r', encoding='utf-8') as f:
                products_data = json.load(f)
            
            # 데이터 변환
            rows_to_insert = []
            for product in products_data:
                row = {
                    "product_id": product.get("product_id"),
                    "brand": product.get("brand"),
                    "product_name": product.get("product_name"),
                    "product_type": product.get("product_type"),
                    "specs": json.dumps(product.get("specs")),
                    "rtings_scores": json.dumps(product.get("rtings_scores")),
                    "price_usd": json.dumps(product.get("price_usd")),
                    "summary": product.get("summary"),
                }
                rows_to_insert.append(row)
            
            # 테이블 비우기 (전체 업데이트)
            delete_query = f"DELETE FROM `{table_id}` WHERE TRUE"
            self.client.query(delete_query).result()
            
            # 새 데이터 삽입
            errors = self.client.insert_rows_json(table_id, rows_to_insert)
            
            if errors == []:
                logger.info(f"{len(rows_to_insert)}개의 제품이 BigQuery에 업데이트되었습니다")
                return True
            else:
                logger.error(f"BigQuery 업데이트 중 오류: {errors}")
                return False
                
        except Exception as e:
            logger.error(f"BigQuery 업데이트 실패: {e}")
            return False

def main():
    """메인 함수"""
    logger.info("RTINGS.com 크롤링 및 BigQuery 업데이트 시작")
    
    try:
        # 크롤링 실행
        scraper = RTINGSscraper()
        products = scraper.scrape_all_products()
        
        if products:
            # JSON 파일 저장
            scraper.save_to_json()
            
            # BigQuery 업데이트
            bq_updater = BigQueryUpdater()
            if bq_updater.project_id:
                success = bq_updater.update_bigquery()
                if success:
                    logger.info("BigQuery 업데이트 완료")
                else:
                    logger.error("BigQuery 업데이트 실패")
            else:
                logger.error("프로젝트 ID를 찾을 수 없어 BigQuery 업데이트를 건너뜁니다")
        else:
            logger.error("수집된 제품이 없습니다")
            
    except Exception as e:
        logger.error(f"메인 실행 중 오류: {e}")

if __name__ == "__main__":
    main()
