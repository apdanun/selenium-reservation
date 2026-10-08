# reservation_naver

네이버 예약(테니스 코트)을 지정한 시각에 자동으로 시도하고, 성공하면 텔레그램으로 결제화면 링크를 보내준다.

## 실행 방법

Python 3.10 이상, Google Chrome 설치 필요.

### macOS

```bash
python3 -m venv venv              # 최초 1회
source venv/bin/activate
pip install -r requirements.txt   # 최초 1회
python3 reservation.py
```

### Windows (PowerShell)

```powershell
py -3 -m venv venv                # 최초 1회
venv\Scripts\activate
pip install -r requirements.txt   # 최초 1회
python reservation.py
```

- PowerShell 에서 `activate` 가 실행 정책 오류로 막히면: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
- `venv` 폴더는 OS 간에 공유되지 않으므로 각 PC 에서 새로 만든다.
- Chrome 은 기본 설치 경로(`Program Files`, `AppData\Local`)에서 자동으로 찾는다. 다른 곳에 설치했다면 설정의 `CHROME_PATH` 에 `r"D:\Chrome\chrome.exe"` 처럼 지정한다.

### 공통

- 실행하면 먼저 설정값을 검사하고(`설정 확인 완료: ...` 출력), 문제가 있으면 Chrome 을 띄우기 전에 종료한다.
- 디버깅 포트(9222)로 Chrome 을 띄우거나 이미 떠 있는 Chrome 에 붙는다. 처음 한 번은 열린 Chrome 에서 네이버 로그인이 되어 있어야 한다.
- `RUN_HOUR:RUN_MINUTE` 이 될 때까지 대기하다가 0~10초 사이에 새로고침 후 예약을 시작한다.

설정 문법만 미리 확인하려면:

```bash
python3 -m py_compile reservation.py telegram_notifier.py
```

## 설정 (`reservation.py` 상단 `설정` 블록)

| 변수 | 설명 |
|---|---|
| `BIZ_URL` | 예약 업체 주소 (양재 `210031`, 내곡 `217811`) |
| `DATES` | 예약할 날짜 목록 `'YYYY-MM-DD'`. 앞에서부터 순서대로 시도 |
| `COURTS` | 코트 id 목록 (예약 페이지 주소 `.../items/` 뒤의 숫자). 날짜마다 앞에서부터 시도하고, 한 코트라도 성공하면 다음 날짜로 |
| `PREFERRED_SLOTS` | 우선 시도할 시간대 `(시작시, 끝시)`. 없으면 나머지 시간대를 순서대로 탐색 |
| `SLOT_HOURS` | 연속 예약 시간 수 |
| `RANGE_START` / `RANGE_END` | 탐색할 시작 시간 범위 |
| `EXCLUDE_HOURS` | 제외할 시간 |
| `RUN_HOUR` / `RUN_MINUTE` | 예약 시작 시각 (서울 시간) |
| `TAKEN_KEYWORDS` | "예약이 마감되었습니다" 류 안내를 감지할 문구 |
| `DRY_RUN` | `True` 면 "동의하고 결제하기" 직전까지만 진행 (테스트용). 실제 예약은 `False` |
| `CHROME_PATH` | Chrome 실행 파일 경로. `None` 이면 OS 별 기본 경로에서 자동 탐색 |

목록 항목 사이 쉼표(`,`)를 빠뜨리지 않도록 주의. 빠뜨리면 실행 시 설정 검사에서 멈춘다.

## 동작

1. 날짜 → 코트 순서로 시도하며, 각 코트에서 가능한 시간대를 골라 "다음" → "동의하고 결제하기"까지 진행한다.
2. "선택한 일정의 예약이 마감되었습니다" 팝업이 뜨면 그 시간대를 빼고 같은 코트의 남은 시간대를 다시 시도하고, 남은 시간대가 없으면 다음 코트로 넘어간다.
3. 결제화면에 들어가면 텔레그램으로 날짜·코트·시간과 결제화면 링크를 보낸다. 그 탭은 결제를 위해 열어둔다.
4. 텔레그램은 성공했을 때만 보낸다. 실패·마감·오류는 콘솔에만 출력한다.

## 텔레그램 설정

`telegram_config.py` 에 봇 토큰과 채팅 ID 를 적는다 (환경변수 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 가 있으면 그 값이 우선).

```python
BOT_TOKEN = "..."
CHAT_ID = "..."
```

전송 테스트:

```bash
python3 -c "from telegram_notifier import send_telegram; send_telegram('테스트')"
```

텔레그램 전송이 실패하거나 느려도 예약 진행에는 영향이 없다 (백그라운드 전송).
