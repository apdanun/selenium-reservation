import json
import os
import ssl
import threading
import urllib.request

# 토큰/채팅 ID 는 telegram_config.py 에 적는다 (gitignore 대상). 환경변수가 있으면 그 값이 우선.
try:
    import telegram_config
except ImportError:
    telegram_config = None

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or getattr(telegram_config, "BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or getattr(telegram_config, "CHAT_ID", "")

try:
    import certifi
    _ssl_context = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _ssl_context = ssl.create_default_context()


def send_telegram(message):
    """텔레그램 전송을 백그라운드 스레드로 넘기고 즉시 반환한다.
    전송이 느리거나 실패해도 예약 흐름이 기다리거나 중단되지 않는다."""
    try:
        # daemon=False: 스크립트가 끝나도 전송 중인 메시지는 마저 보내고 종료
        threading.Thread(target=_send, args=(message,), daemon=False).start()
    except Exception as e:
        print(f"텔레그램 전송 스레드 시작 실패: {type(e).__name__}")


def _send(message):
    try:
        if not BOT_TOKEN or not CHAT_ID:
            print("텔레그램 설정 없음(TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID) - 알림 생략")
            return
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        body = json.dumps({"chat_id": CHAT_ID, "text": message}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5, context=_ssl_context) as res:
            if res.status != 200:
                print(f"텔레그램 전송 실패: HTTP {res.status}")
    except Exception as e:
        # URL 에 토큰이 포함되므로 예외 메시지 대신 타입만 출력
        print(f"텔레그램 전송 실패: {type(e).__name__}")
