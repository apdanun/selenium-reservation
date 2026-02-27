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
 
 # 실행파일 경로로 크롬 실행
subprocess.Popen([
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "--remote-debugging-port=9222",
    "--user-data-dir=./chromeCookie"
])

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

driver = webdriver.Chrome(options=option)
driver.maximize_window()

# ChromeDriver 경로 설정 (다운로드 폴더에 있는 chromedriver)
# service = Service()
 
# WebDriver에 Service 객체 전달
# driver = webdriver.Chrome(service=service)
 
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

# 예약 사이트 열기
# 내곡 217811 → section[2]
# 양재 210031 → section[3]
# SECTION = 2
# driver.get('https://m.booking.naver.com/booking/10/bizes/217811/items/7409707?startDate=2026-03-17')
SECTION = 3
driver.get('https://m.booking.naver.com/booking/10/bizes/210031/items/7458024?startDate=2026-04-05')
 
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

def do_reservation(section):
    """시간 선택 → 다음 → 결제창 버튼 클릭까지 수행. 성공 시 True 반환."""
    # 오후 1시~6시 중 연속 2시간 예약 가능한 슬롯 찾기
    # li[8]=13시, li[9]=14시, li[10]=15시, li[11]=16시, li[12]=17시, li[13]=18시
    base_xpath = f'/html/body/div[1]/main/section[{section}]/div/div[2]/div[2]/div/div[2]/ul'
    time_slots = []
    for li_idx in range(8, 14):  # li[8](13시) ~ li[13](18시)
        xpath = f'{base_xpath}/li[{li_idx}]/button'
        hour = li_idx + 5
        time_slots.append((hour, li_idx, xpath))

    # 연속 2시간 가능한 쌍 찾기 (13-14, 14-15, 15-16, 16-17, 17-18)
    selected_pair = None
    for i in range(len(time_slots) - 1):
        hour1, _, xpath1 = time_slots[i]
        hour2, _, xpath2 = time_slots[i + 1]
        if is_time_button_available(xpath1, wait=3) and is_time_button_available(xpath2, wait=1):
            selected_pair = (hour1, hour2, xpath1, xpath2)
            print(f"{hour1}시~{hour2 + 1}시 예약 가능! 선택합니다.")
            break

    if selected_pair:
        _, _, xpath1, xpath2 = selected_pair
        click_button(xpath1)
        click_button(xpath2)
    else:
        print("오후 1시~6시 중 연속 2시간 예약 가능한 슬롯이 없습니다.")
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

# 두 번째 예약 정보
SECOND_URL = 'https://m.booking.naver.com/booking/10/bizes/210031/items/7458029?startDate=2026-04-12'
SECOND_SECTION = 3

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
            if do_reservation(SECTION):
                keep_going = False
                print("=== 첫 번째 예약 완료, 두 번째 예약 시작 ===")

                # 새 탭에서 두 번째 예약 진행
                driver.execute_script(f"window.open('{SECOND_URL}', '_blank');")
                driver.switch_to.window(driver.window_handles[-1])
                time.sleep(random.uniform(1, 1.5))

                do_reservation(SECOND_SECTION)
                print("=== 두 번째 예약 완료 ===")
        except Exception as e:
            print("예약 버튼 클릭 오류:", e)
            time.sleep(2)  # 2초 후 다시 시도

    # 정해진 시간까지 대기
    if keep_going:
        print(f"현재 시간: {now.strftime('%H:%M:%S')} - 대기 중...")
    time.sleep(random.choice([0.8, 1, 1.2]))
