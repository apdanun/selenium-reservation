from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoAlertPresentException, UnexpectedAlertPresentException
from datetime import datetime
import random
import time
import pytz
import subprocess
from telegram_notifier import send_telegram

# ===================== 설정 =====================
# 예약 사이트 열기
# 내곡 217811
# 양재 210031
BIZ_URL = 'https://m.booking.naver.com/booking/10/bizes/217811/items'
# 예약할 날짜 - 앞에서부터 순서대로 시도
DATES = [
    '2026-11-07',
    '2026-11-14',
    '2026-11-01',
    '2026-11-15',
    '2026-11-22',
    '2026-11-29',
]
# 코트(item id, BIZ_URL 뒤에 붙는 값) - 날짜마다 앞에서부터 시도하고, 한 코트라도 성공하면 다음 날짜로
COURTS = [
    '8081115',
    '8081105',
    '7990859',
]

# 우선순위 희망 시간대 (시작시, 끝시) - 이 슬롯들을 먼저 시도하고, 없으면 나머지 시간대 순차 탐색
# 6 = 6시
PREFERRED_SLOTS = [
    (14,16),
    (13,15),
    (15,17),
    (16,18),
    (8,10),
    (7,9),
    (6,8)
]
SLOT_HOURS = 2      # 연속 예약 시간 수
RANGE_START = 6         # 내가 실제로 탐색을 시작할 시간
RANGE_END = 17      # 전체 예약 가능 끝 시간 (17시 시작 슬롯까지 → 17~19)
EXCLUDE_HOURS = set(range(11, 13))  # 제외할 시간 (11시, 12시 → 점심시간)

# 예약 시작 시각 (서울 시간) - 이 시각 0~10초 사이에 새로고침 후 예약 시작
RUN_HOUR = 9
RUN_MINUTE = 0

# "이미 예약됨" 같은 안내가 뜨면 기다리지 않고 바로 실패 처리할 문구 (알림창/팝업 안의 글자에 하나라도 포함되면 감지)
TAKEN_KEYWORDS = ['이미', '다른 사용자', '마감', '예약할 수 없', '예약이 불가', '선택할 수 없']

# 테스트용: True 면 "동의하고 결제하기" 화면까지만 가고 버튼은 누르지 않는다 (실제 예약 시 False 로)
DRY_RUN = False
# ===============================================

def validate_config():
    """설정값 실수(쉼표 누락, 날짜/시간 형식 오류 등)를 Chrome 실행 전에 잡는다. 문제가 있으면 목록을 출력하고 종료."""
    errors = []
    if not DATES:
        errors.append("DATES 가 비어 있습니다")
    for d in DATES:
        try:
            datetime.strptime(d, '%Y-%m-%d')
            if len(d) != 10:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"DATES 형식 오류: {d!r} (YYYY-MM-DD, 쉼표 누락 확인)")
    if len(set(DATES)) != len(DATES):
        errors.append("DATES 에 중복된 날짜가 있습니다")
    if not COURTS:
        errors.append("COURTS 가 비어 있습니다")
    for c in COURTS:
        if not (isinstance(c, str) and c.isdigit() and 5 <= len(c) <= 9):
            errors.append(f"COURTS 형식 오류: {c!r} (숫자 id, 쉼표 누락 확인)")
    for slot in PREFERRED_SLOTS:
        if not (isinstance(slot, tuple) and len(slot) == 2 and all(isinstance(h, int) for h in slot)):
            errors.append(f"PREFERRED_SLOTS 형식 오류: {slot!r} ((시작시, 끝시) 형태)")
        elif slot[1] - slot[0] != SLOT_HOURS:
            errors.append(f"PREFERRED_SLOTS {slot} 가 SLOT_HOURS({SLOT_HOURS}시간)와 맞지 않습니다")
        elif not (0 <= slot[0] < slot[1] <= 24):
            errors.append(f"PREFERRED_SLOTS 시간 범위 오류: {slot}")
    if not (0 <= RANGE_START <= RANGE_END <= 23):
        errors.append(f"RANGE_START({RANGE_START}) / RANGE_END({RANGE_END}) 범위 오류")
    if not (0 <= RUN_HOUR <= 23 and 0 <= RUN_MINUTE <= 59):
        errors.append(f"RUN_HOUR({RUN_HOUR}) / RUN_MINUTE({RUN_MINUTE}) 범위 오류")
    if not isinstance(DRY_RUN, bool):
        errors.append(f"DRY_RUN 은 True / False 여야 합니다: {DRY_RUN!r}")

    if errors:
        print("설정 오류가 있어 실행하지 않습니다:")
        for e in errors:
            print(f"  - {e}")
        raise SystemExit(1)
    print(f"설정 확인 완료: 날짜 {len(DATES)}개, 코트 {len(COURTS)}개, DRY_RUN={DRY_RUN}, 시작 {RUN_HOUR:02d}:{RUN_MINUTE:02d}")

validate_config()
 
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
 

class SlotTaken(Exception):
    """'예약이 마감되었습니다' 등 안내가 떠서 진행할 수 없음. slot 에 시도했던 (시작시, 끝시)."""
    slot = None

# 1순위: 네이버 예약 마감 안내 팝업 (div.confirm_alert_con[role=dialog] > .in_ly_dsc)
# 2순위: 그 외 팝업으로 보이는 요소 중 TAKEN_KEYWORDS 가 들어간 것
_FIND_NOTICE_JS = """
const keywords = arguments[0];
const visible = el => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
for (const el of document.querySelectorAll('.confirm_alert_con')) {
  if (!visible(el)) continue;
  const dsc = el.querySelector('.in_ly_dsc');
  const text = ((dsc || el).innerText || '').trim();
  if (text) return text;
}
const sel = '[role="dialog"],[role="alertdialog"],[role="alert"],'
  + '[class*="popup"],[class*="Popup"],[class*="layer"],[class*="Layer"],'
  + '[class*="modal"],[class*="Modal"],[class*="toast"],[class*="Toast"],'
  + '[class*="alert"],[class*="Alert"],[class*="dialog"],[class*="Dialog"]';
for (const el of document.querySelectorAll(sel)) {
  if (!visible(el)) continue;  // 안 보이는 요소 제외
  const text = (el.innerText || '').trim();
  if (text && text.length < 300 && keywords.some(k => text.includes(k))) return text;
}
return null;
"""

def find_taken_notice():
    """브라우저 알림창(alert) 또는 화면 팝업에 '이미 예약됨' 류 안내가 있으면 그 문구를, 없으면 None."""
    try:
        alert = driver.switch_to.alert
        text = alert.text
        alert.accept()
        return text or "(알림창)"
    except NoAlertPresentException:
        pass
    except UnexpectedAlertPresentException as e:
        return e.alert_text or "(알림창)"
    try:
        return driver.execute_script(_FIND_NOTICE_JS, TAKEN_KEYWORDS)
    except UnexpectedAlertPresentException as e:
        return e.alert_text or "(알림창)"
    except Exception:
        return None

def wait_or_taken(condition, timeout=10, interval=0.2):
    """condition(driver) 가 참이 될 때까지 기다리되, 중간에 '이미 예약됨' 안내가 뜨면 즉시 SlotTaken.
    시간 초과면 TimeoutError."""
    end = time.time() + timeout
    while time.time() < end:
        notice = find_taken_notice()
        if notice:
            raise SlotTaken(notice.replace('\n', ' ')[:100])
        try:
            value = condition(driver)
            if value:
                return value
        except UnexpectedAlertPresentException as e:
            raise SlotTaken((e.alert_text or "(알림창)")[:100])
        except Exception:
            pass
        time.sleep(interval)
    raise TimeoutError(f"{timeout}초 내 화면 전환 없음")

def reservation_url(date, court):
    return f'{BIZ_URL}/{court}?startDate={date}'

TARGET_URL = reservation_url(DATES[0], COURTS[0])
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

def time_button_xpath(base_xpath, hour):
    """시간 버튼을 위치(li 순번)가 아닌 aria-label 로 찾는다. 예) 6시 → '오전 6:00', 14시 → '오후 2:00'
    목록이 몇 시부터 시작하든 상관없이 같은 시간 버튼을 찾을 수 있다."""
    ampm = '오전' if hour < 12 else '오후'
    h12 = hour % 12 or 12
    labels = {f'{ampm} {h12}:00', f'{ampm} {hour}:00'}  # 오후 표기가 2:00 / 14:00 중 어느 쪽이어도 대응
    cond = ' or '.join(f"@aria-label='{label}'" for label in sorted(labels))
    return f'{base_xpath}/li/button[{cond}]'

def do_reservation(skip_slots=()):
    """시간 선택 → 다음 → 동의하고 결제하기 클릭까지 수행. 성공 시 (시작시, 끝시, 결제화면 URL) 반환, 실패 시 False."""
    # 절대 경로(div[2]/div[3]) 대신 class 기반으로 탐색해 레이아웃 변동에 견고하게 대응
    # section_calendar > section_inner > section_content > time_area > slick-slider > time_list(ul) 안의 li
    base_xpath = (
        "//section[contains(@class,'section_calendar')]"
        "//div[contains(@class,'section_inner')]"
        "//div[contains(@class,'section_content')]"
        "//div[contains(@class,'time_area')]"
        "//div[contains(@class,'slick-slider')]"
        "//ul[contains(@class,'time_list')]"
    )

    # 우선순위 슬롯 + 나머지 시간대 순차 목록 생성 (중복 제거)
    all_slots = [
        (h, h + SLOT_HOURS) for h in range(RANGE_START, RANGE_END + 1)
        if not set(range(h, h + SLOT_HOURS)) & EXCLUDE_HOURS
    ]
    preferred_set = set(PREFERRED_SLOTS)
    remaining = [s for s in all_slots if s not in preferred_set]
    slots_to_try = [s for s in list(PREFERRED_SLOTS) + remaining if s not in skip_slots]

    selected_xpaths = None
    selected_slot = None
    for start_hour, end_hour in slots_to_try:
        hours = list(range(start_hour, end_hour))
        xpaths = [time_button_xpath(base_xpath, h) for h in hours]

        all_available = True
        for idx, xp in enumerate(xpaths):
            if not is_time_button_available(xp, wait=3 if idx == 0 else 1):
                all_available = False
                break

        if all_available:
            print(f"{start_hour}시~{end_hour}시 예약 가능! 선택합니다.")
            selected_xpaths = xpaths
            selected_slot = (start_hour, end_hour)
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

    # 예약 페이지로 넘어갔는지 확인 (페이지 URL 변경 체크) - '이미 예약됨' 안내가 뜨면 즉시 실패
    before_url = driver.current_url
    try:
        wait_or_taken(lambda d: d.current_url != before_url)
    except SlotTaken as e:
        e.slot = selected_slot
        raise
    print("동의하고 결제하기 화면으로 넘어갔습니다!")
    time.sleep(random.uniform(0.7, 1.2))

    if DRY_RUN:
        print("[DRY_RUN] 동의하고 결제하기 버튼은 누르지 않고 종료")
        return selected_slot + (driver.current_url,)

    # [동의하고 결제하기] 선택
    next_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div[2]/div[5]/div/button[2]'))
    )
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", next_button)
    agree_url = driver.current_url
    handles_before = set(driver.window_handles)
    next_button.click()
    print("동의하고 결제하기 클릭 완료")

    try:
        payment_url = wait_payment_url(agree_url, handles_before)  # 마감 안내가 뜨면 SlotTaken
    except SlotTaken as e:
        e.slot = selected_slot
        raise
    if not payment_url:
        # 이미 누가 예약했거나 에러 팝업 등으로 결제 화면이 안 뜬 경우
        raise PaymentNotReached(selected_slot)
    print(f"결제 화면 URL: {payment_url}")
    return selected_slot + (payment_url,)

class PaymentNotReached(Exception):
    """동의하고 결제하기를 눌렀지만 결제 화면으로 넘어가지 못함."""
    def __init__(self, slot):
        super().__init__(f"{slot[0]}시~{slot[1]}시 결제 화면 진입 실패")

def wait_payment_url(agree_url, handles_before, wait=10):
    """동의하고 결제하기 클릭 후 결제 화면 URL 을 얻는다. 같은 탭 이동 / 새 창(팝업) 열림 둘 다 대응.
    '이미 예약됨' 안내가 뜨면 SlotTaken, 그 외 이유로 넘어가지 못하면(시간 초과 등) None 을 반환한다."""
    origin_handle = driver.current_window_handle
    try:
        wait_or_taken(
            lambda d: set(d.window_handles) - handles_before or d.current_url != agree_url,
            timeout=wait,
        )
        new_handles = set(driver.window_handles) - handles_before
        if new_handles:
            # 결제가 새 창으로 열린 경우: 새 창의 URL 을 읽고 원래 탭으로 복귀
            driver.switch_to.window(new_handles.pop())
            WebDriverWait(driver, wait).until(lambda d: d.current_url not in ("", "about:blank"))
            url = driver.current_url
            driver.switch_to.window(origin_handle)
            return url
        return driver.current_url
    except SlotTaken:
        raise
    except Exception as e:
        print(f"결제 화면 진입 실패: {type(e).__name__}")
        try:
            driver.switch_to.window(origin_handle)
        except Exception:
            pass
        return None

def notify_success(date, court, slot):
    """do_reservation 성공 시에만 텔레그램 발송. 알림 실패가 다음 예약을 막지 않도록 예외를 밖으로 내보내지 않는다."""
    if not slot:
        return
    try:
        start_hour, end_hour, url = slot
        send_telegram(
            ("[테스트] " if DRY_RUN else "") +
            f"✅ [네이버 예약 성공] {date} 코트 {court} {start_hour}시~{end_hour}시 결제창 진입! 결제를 완료하세요.\n{url}"
        )
    except Exception as e:
        print(f"성공 알림 처리 실패: {type(e).__name__}")

def run_reservations():
    """DATES x COURTS 를 순서대로 시도. 날짜당 한 코트 성공하면 다음 날짜로 넘어간다.
    성공한 탭은 결제를 위해 그대로 두고, 실패한 탭은 다음 시도에 재사용한다."""
    results = []
    first_attempt = True
    reuse_current_tab = True  # 첫 시도는 이미 TARGET_URL 이 열린(새로고침된) 현재 탭 사용

    for date in DATES:
        for court in COURTS:
            url = reservation_url(date, court)
            result = False
            keep_tab = False
            skip_slots = set()  # 마감 안내가 떴던 시간대 - 같은 코트 재시도 시 건너뜀

            # 마감 안내가 뜨면 그 시간대만 빼고 같은 코트의 남은 가능 시간대를 계속 시도.
            # 가능한 시간대가 더 없으면(do_reservation False) 다음 코트로. 시도할 때마다 시간대가 하나씩 빠지므로 무한 반복은 없다.
            attempt = 0
            while True:
                print(f"=== {date} 코트 {court} 예약 시도" + (f" (다른 시간 재시도 {attempt})" if attempt else "") + " ===")
                try:
                    if first_attempt:
                        first_attempt = False
                    elif reuse_current_tab or attempt:
                        driver.get(url)
                        WebDriverWait(driver, 10).until(
                            lambda d: d.execute_script("return document.readyState") == "complete"
                        )
                    else:
                        driver.execute_script(f"window.open('{url}', '_blank');")
                        driver.switch_to.window(driver.window_handles[-1])
                        time.sleep(random.uniform(1, 1.5))

                    result = do_reservation(skip_slots)
                except SlotTaken as e:
                    # 마감 안내 → 같은 탭을 새로고침해서 그 시간대만 빼고 다시 시도
                    if e.slot:
                        skip_slots.add(e.slot)
                    slot_text = f"{e.slot[0]}시~{e.slot[1]}시 " if e.slot else ""
                    print(f"{date} 코트 {court} {slot_text}마감: {e} - 다른 시간 재시도")
                    attempt += 1
                    if not e.slot:
                        break  # 어떤 시간대가 마감인지 모르면 같은 시도를 반복하게 되므로 다음 코트로
                    continue
                except PaymentNotReached as e:
                    # 혹시 실제로는 결제 화면이 떠 있을 수 있으니 이 탭은 닫거나 재사용하지 않고 남겨둔다
                    keep_tab = True
                    print(f"{date} 코트 {court} {e} - 다음 코트 시도")
                except Exception as e:
                    print(f"{date} 코트 {court} 예약 오류:", e)
                break  # 성공 / 가능한 시간 없음 / 마감 외 오류 → 이 코트는 종료

            print(f"=== {date} 코트 {court} 예약 {'완료' if result else '실패'} ===")
            # 성공한 탭은 결제용으로 남겨두고 다음 시도는 새 탭에서
            reuse_current_tab = not result and not keep_tab
            if result:
                notify_success(date, court, result)
                results.append((date, court))
                break

    print(f"=== 전체 예약 종료: 성공 {len(results)}/{len(DATES)} ===")
    for date, court in results:
        print(f"  - {date} 코트 {court}")

# 예약
keep_going = True
while keep_going:
    # 현재 시간을 서울 시간으로 확인
    now = datetime.now(seoul_tz)
    print(now)

    # 예약 시도
    if now.hour == RUN_HOUR and now.minute == RUN_MINUTE and (now.second >= 0 and now.second <= 10):
        print("일찍 새로고침!")
        driver.refresh()
        time.sleep(random.uniform(0.6, 1))

        keep_going = False
        run_reservations()

    # 정해진 시간까지 대기
    if keep_going:
        print(f"현재 시간: {now.strftime('%H:%M:%S')} - 대기 중...")
    time.sleep(random.choice([0.8, 1, 1.2]))
