from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import random
import time
import pytz
import subprocess
 
 # 실행파일 경로로 크롬 실행 (이미 실행 중이면 건너뜀)
import socket
def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

if not is_port_open(9222):
    subprocess.Popen([
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "--remote-debugging-port=9222",
        "--user-data-dir=./chromeCookie",
        "--no-first-run",
        "--no-default-browser-check"
    ])
    time.sleep(3)  # Chrome이 디버깅 포트를 열 때까지 대기

option = Options()
option.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
option.add_argument('--window-size=1920,1080')
option.add_argument(
    "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
)
option.add_argument("--lang=ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7")
# 자동화 탐지 방지
#option.add_argument("disable-blink-features=AutomationControlled")

for attempt in range(5):
    try:
        driver = webdriver.Chrome(options=option)
        break
    except Exception:
        print(f"Chrome 연결 재시도 ({attempt + 1}/5)...")
        time.sleep(2)

try:
    driver.maximize_window()
except Exception:
    pass  # 이미 열린 창이면 maximize 실패할 수 있음

# ChromeDriver 경로 설정 (다운로드 폴더에 있는 chromedriver)
# service = Service()
 
# WebDriver에 Service 객체 전달
# driver = webdriver.Chrome(service=service)
 
# 예약 사이트 열기
# 내곡 217811
# 양재 210031
BASE_URL = 'https://m.booking.naver.com/booking/10/bizes/217811/items/7477748'
FIRST_DATE = '2026-04-05'
SECOND_DATE = '2026-04-12'
TARGET_URL = f'{BASE_URL}?startDate={FIRST_DATE}'
# 기존 탭 정리: 첫 번째 탭만 남기고 나머지 닫기
handles = driver.window_handles
if len(handles) > 1:
    for handle in handles[1:]:
        driver.switch_to.window(handle)
        driver.close()
    driver.switch_to.window(handles[0])
else:
    driver.switch_to.window(handles[0])

driver.execute_cdp_cmd(
    "Page.addScriptToEvaluateOnNewDocument",
    {
        "source": """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko', 'en-US', 'en'] });
        Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' });
        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
        """
    }
)

# URL 이동
driver.get(TARGET_URL)
WebDriverWait(driver, 10).until(
    lambda d: d.execute_script("return document.readyState") == "complete"
)
print(f"현재 URL: {driver.current_url}")
 
# 서울 시간대 설정
seoul_tz = pytz.timezone('Asia/Seoul')
 
def is_time_button_available(xpath, wait=10):
    try:
        btn = WebDriverWait(driver, wait).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        li = btn.find_element(By.XPATH, "./ancestor::li")
        classes = li.get_attribute("class") or ""
        return "disabled" not in classes
    except Exception as e:
        print("ERROR:", e)
        return False

def click_button(xpath, wait=1):
    WebDriverWait(driver, wait).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    ).click()

# 우선순위 희망 시간대 (시작시, 끝시) - 이 슬롯들을 먼저 시도하고, 없으면 나머지 시간대 순차 탐색
PREFERRED_SLOTS = [
    (9, 11),
    (10, 12),
]
SLOT_HOURS = 2      # 연속 예약 시간 수
RANGE_START = 6     # 전체 예약 가능 시작 시간
RANGE_END = 17      # 전체 예약 가능 끝 시간 (17시 시작 슬롯까지 → 17~19)
EXCLUDE_HOURS = set(range(11, 13))  # 제외할 시간 (11시, 12시 → 점심시간)

def do_reservation():
    """시간 선택 → 다음 → 결제창 버튼 클릭까지 수행. 성공 시 True 반환."""
    # li 인덱스 = hour - 5 (li[1]=6시, li[2]=7시, li[3]=8시, ...)
    base_xpath = '/html/body/div[1]/main/section[2]/div/div[2]/div[2]/div/div[2]/ul'

    # 우선순위 슬롯 + 나머지 시간대 순차 목록 생성 (중복 제거)
    all_slots = [
        (h, h + SLOT_HOURS) for h in range(RANGE_START, RANGE_END + 1)
        if not set(range(h, h + SLOT_HOURS)) & EXCLUDE_HOURS
    ]
    preferred_set = set(PREFERRED_SLOTS)
    remaining = [s for s in all_slots if s not in preferred_set]
    slots_to_try = list(PREFERRED_SLOTS) + remaining

    selected_xpaths = None
    for start_hour, end_hour in slots_to_try:
        hours = list(range(start_hour, end_hour))
        xpaths = [f'{base_xpath}/li[{h - 5}]/button' for h in hours]

        all_available = True
        for idx, xp in enumerate(xpaths):
            if not is_time_button_available(xp, wait=3 if idx == 0 else 1):
                all_available = False
                break

        if all_available:
            print(f"{start_hour}시~{end_hour}시 예약 가능! 선택합니다.")
            selected_xpaths = xpaths
            break
        else:
            print(f"{start_hour}시~{end_hour}시 불가")

    if selected_xpaths:
        for xp in selected_xpaths:
            click_button(xp)
    else:
        print("희망 시간대 중 예약 가능한 슬롯이 없습니다.")
        return False

    print("시간 버튼 클릭 완료")
    time.sleep(random.uniform(0.3, 0.6))

    # [다음] 선택
    next_buttons = driver.find_elements(
        By.XPATH, '/html/body/div[1]/main/div[2]/div/button'
    )

    if not next_buttons:
        return False

    next_button = next_buttons[0]
    classes = next_button.get_attribute("class") or ""

    DISABLED_CLASS = 'NextButton__disabled__a3P-t'
    if DISABLED_CLASS in classes:
        return False
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", next_button)
    next_button.click()
    print("다음 버튼 클릭 완료")

    # 예약 페이지로 넘어갔는지 확인 (페이지 URL 변경 체크)
    WebDriverWait(driver, 10).until(EC.url_changes(driver.current_url))
    print("결제 창으로 넘어갔습니다!")
    time.sleep(random.uniform(0.7, 1.2))

    next_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div[2]/div[5]/div/button[2]'))
    )
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", next_button)
    next_button.click()
    return True

SECOND_URL = f'{BASE_URL}?startDate={SECOND_DATE}'

# 예약
keep_going = True
while keep_going:
    # 현재 시간을 서울 시간으로 확인
    now = datetime.now(seoul_tz)
    print(now)

    # 예약 시도
    if now.hour == 9 and now.minute == 0 and (now.second >= 0 and now.second <= 10):
        print("일찍 새로고침!")
        driver.refresh()
        time.sleep(random.uniform(0.6, 1))

        try:
            # 첫 번째 예약 진행
            if do_reservation():
                keep_going = False
                print("=== 첫 번째 예약 완료, 두 번째 예약 시작 ===")

                # 새 탭에서 두 번째 예약 진행
                driver.execute_script(f"window.open('{SECOND_URL}', '_blank');")
                driver.switch_to.window(driver.window_handles[-1])
                time.sleep(random.uniform(1, 1.5))

                do_reservation()
                print("=== 두 번째 예약 완료 ===")
        except Exception as e:
            print("예약 버튼 클릭 오류:", e)
            time.sleep(2)  # 2초 후 다시 시도

    # 정해진 시간까지 대기
    if keep_going:
        print(f"현재 시간: {now.strftime('%H:%M:%S')} - 대기 중...")
    time.sleep(random.choice([0.8, 1, 1.2]))
