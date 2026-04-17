import asyncio
import sys
from playwright.async_api import async_playwright
import json
import os
import urllib.request
import glob
import platform

def _get_data_dir():
    """사용자 데이터 폴더 (업데이트해도 유지됨)"""
    if platform.system() == "Darwin":
        d = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "MyShop")
    else:
        d = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MyShop")
    os.makedirs(d, exist_ok=True)
    # 기존 파일 마이그레이션 (프로그램 폴더 → 데이터 폴더)
    import shutil
    search_dirs = [os.path.dirname(os.path.abspath(__file__))]
    if getattr(sys, 'frozen', False):
        search_dirs.append(os.path.dirname(sys.executable))
    # Windows 기본 설치 경로도 확인
    if platform.system() != "Darwin":
        pf = os.environ.get("LOCALAPPDATA", "")
        if pf:
            search_dirs.append(os.path.join(pf, "Programs", "마이샵통합관리"))
    for fname in ["wing_cookies.json", "coupang_accounts.json", "wing_passwords.json",
                   "cs_memos.json", "courier_map.json", "product_code_map.json",
                   "login_settings.json", "saved_accounts.json"]:
        new = os.path.join(d, fname)
        new_size = os.path.getsize(new) if os.path.exists(new) else 0
        for search_dir in search_dirs:
            old = os.path.join(search_dir, fname)
            if os.path.exists(old):
                old_size = os.path.getsize(old)
                if not os.path.exists(new) or (old_size > new_size and old_size > 10):
                    try:
                        shutil.copy2(old, new)
                        new_size = old_size
                    except: pass
    return d

DATA_DIR = _get_data_dir()

def _data_path(filename):
    return os.path.join(DATA_DIR, filename)

def _find_chromium_executable():
    """PyInstaller 빌드 또는 로컬 환경에서 Chromium 경로 찾기"""
    is_mac = platform.system() == "Darwin"

    # 1. PyInstaller 빌드 환경
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
        if is_mac:
            pattern = os.path.join(base, "ms-playwright", "chromium-*", "chrome-mac-*",
                                   "Google Chrome for Testing.app", "Contents", "MacOS", "Google Chrome for Testing")
        else:
            pattern = os.path.join(base, "ms-playwright", "chromium-*", "chrome-win64", "chrome.exe")
        found = glob.glob(pattern)
        if found:
            return sorted(found)[-1]

    # 2. 로컬 ms-playwright
    if is_mac:
        # macOS: ~/Library/Caches/ms-playwright
        local_pw = os.path.join(os.path.expanduser("~"), "Library", "Caches", "ms-playwright")
        if os.path.isdir(local_pw):
            pattern = os.path.join(local_pw, "chromium-*", "chrome-mac-*",
                                   "Google Chrome for Testing.app", "Contents", "MacOS", "Google Chrome for Testing")
            found = glob.glob(pattern)
            if found:
                return sorted(found)[-1]
    else:
        # Windows: %LOCALAPPDATA%/ms-playwright
        local_pw = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")
        if os.path.isdir(local_pw):
            pattern = os.path.join(local_pw, "chromium-*", "chrome-win64", "chrome.exe")
            found = glob.glob(pattern)
            if found:
                return sorted(found)[-1]
    # 3. 못 찾으면 자동 설치
    try:
        import subprocess
        print("[Playwright] Chromium 자동 설치 중...")
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
            node = os.path.join(base, "_internal", "playwright", "driver", "node.exe") if not is_mac else None
            cli = os.path.join(base, "_internal", "playwright", "driver", "package", "cli.js") if not is_mac else None
            if node and cli and os.path.isfile(node) and os.path.isfile(cli):
                subprocess.run([node, cli, "install", "chromium"], timeout=120)
        else:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], timeout=120)
        # 재검색
        if is_mac:
            local_pw = os.path.join(os.path.expanduser("~"), "Library", "Caches", "ms-playwright")
        else:
            local_pw = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")
        if os.path.isdir(local_pw):
            if is_mac:
                pattern = os.path.join(local_pw, "chromium-*", "chrome-mac-*",
                    "Google Chrome for Testing.app", "Contents", "MacOS", "Google Chrome for Testing")
            else:
                pattern = os.path.join(local_pw, "chromium-*", "chrome-win64", "chrome.exe")
            found = glob.glob(pattern)
            if found:
                print(f"[Playwright] Chromium 설치 완료: {sorted(found)[-1]}")
                return sorted(found)[-1]
    except Exception as e:
        print(f"[Playwright] 자동 설치 실패: {e}")
    return None

def get_public_ip():
    try:
        with urllib.request.urlopen('https://api.ipify.org', timeout=3) as r:
            return r.read().decode('utf-8').strip()
    except:
        try:
            with urllib.request.urlopen('https://ifconfig.me/ip', timeout=3) as r:
                return r.read().decode('utf-8').strip()
        except:
            return ""

def save_ip(ip):
    with open("ip_info.json", "w") as f:
        json.dump({"ip": ip}, f)

def save_cookies(username, cookies):
    p = _data_path("wing_cookies.json")
    all_cookies = {}
    if os.path.exists(p):
        try:
            with open(p, "r") as f:
                all_cookies = json.load(f)
        except: pass
    all_cookies[username] = cookies
    with open(p, "w") as f:
        json.dump(all_cookies, f)

def load_cookies(username):
    p = _data_path("wing_cookies.json")
    if os.path.exists(p):
        try:
            with open(p, "r") as f:
                return json.load(f).get(username, [])
        except: pass
    return []

def verify_cookies(username, timeout=10):
    """저장된 쿠키로 Wing 주문관리 페이지 GET → 200이면 로그인 유효.

    302(로그인 리다이렉트) / 401 / 연결 실패 → 만료.
    (search JSON API는 xsrf 헤더 요구하므로 HTML 라우트로 검증)
    """
    cookies = load_cookies(username)
    if not cookies:
        return False
    try:
        import urllib.request, urllib.error, ssl
        cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies if c.get("name") and c.get("value") is not None)
        if not cookie_header:
            return False

        url = "https://wing.coupang.com/tenants/sfl-portal/delivery/management"

        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, hdrs, newurl):
                return None

        ctx = ssl._create_unverified_context()
        opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=ctx))
        req = urllib.request.Request(
            url,
            headers={
                "Cookie": cookie_header,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        try:
            with opener.open(req, timeout=timeout) as resp:
                if resp.status != 200:
                    return False
                # 로그인 페이지로 온 게 아니라 주문관리 HTML이면 유효
                body = resp.read(4096).decode("utf-8", errors="ignore").lower()
                if "login" in body and "keycloak" in body:
                    return False
                return True
        except urllib.error.HTTPError:
            return False
    except Exception:
        return False

async def _extract_wing_error(page):
    """Wing/Keycloak 로그인 페이지에서 에러 메시지 추출 (없으면 빈 문자열)"""
    try:
        msg = await page.evaluate("""
            () => {
                // 1) 명시적 에러 셀렉터
                const sels = [
                    '#input-error', '#input-error-username', '#input-error-password',
                    '.alert-error', '.kc-feedback-text', '.pf-c-alert__description',
                    '.alert.alert-danger', 'span.kc-feedback-text',
                    '[role="alert"]', '.error-message', '.login-error',
                    'p.instruction', '#kc-content-wrapper .alert'
                ];
                for (const s of sels) {
                    const el = document.querySelector(s);
                    if (el) {
                        const t = (el.innerText || el.textContent || '').trim();
                        if (t) return t;
                    }
                }
                // 2) 본문에서 에러 키워드 포함 짧은 텍스트 찾기
                const keywords = ['비밀번호', '아이디', '일치하지', '올바르지', '확인', 'invalid', 'incorrect', 'not match'];
                const nodes = document.querySelectorAll('body *');
                for (const n of nodes) {
                    if (!n.innerText) continue;
                    const t = (n.innerText || '').trim();
                    if (t.length > 0 && t.length < 120) {
                        const lower = t.toLowerCase();
                        for (const k of keywords) {
                            if (t.includes(k) || lower.includes(k)) {
                                return t;
                            }
                        }
                    }
                }
                return '';
            }
        """)
        return (msg or "").strip()
    except Exception:
        return ""


async def do_login(username, password, callback=None):
    """Wing 로그인 후 쿠키 저장. 비번 오류 시 정확한 에러 메시지 반환."""
    async with async_playwright() as p:
        _chrome_path = _find_chromium_executable()
        browser = await p.chromium.launch(
            headless=False,
            executable_path=_chrome_path,
            args=["--window-size=560,720", "--window-position=120,80"],
        )
        context = await browser.new_context(viewport={"width": 560, "height": 720})
        page = await context.new_page()

        try:
            if callback: callback("Wing 접속 중...")
            await page.goto("https://wing.coupang.com/login", wait_until="domcontentloaded")
            await asyncio.sleep(1)

            if callback: callback("로그인 중...")
            await page.fill('#username', username)
            await page.fill('#password', password)
            await page.click('#kc-login')

            def _is_logged_in(url):
                return "wing.coupang.com" in url and "login" not in url

            if callback: callback("로그인 확인 중...")
            for i in range(60):
                await asyncio.sleep(1)
                current_url = page.url
                if _is_logged_in(current_url):
                    if callback: callback("로그인 확인!")
                    break
                # 로그인 페이지에 머물러 있으면 에러 메시지 체크 (3초 후부터)
                if i >= 2 and ("login" in current_url):
                    err = await _extract_wing_error(page)
                    if err:
                        await browser.close()
                        return {"success": False, "message": err}
                remaining = 59 - i
                if remaining > 0 and callback:
                    if i < 3:
                        callback("로그인 확인 중...")
                    else:
                        callback(f"2차 인증 대기 중... ({remaining}초 남음)")
            else:
                # 60초 타임아웃 직전 에러 한 번 더 체크
                err = await _extract_wing_error(page)
                await browser.close()
                if err:
                    return {"success": False, "message": err}
                return {"success": False, "message": "로그인 시간 초과 — 아이디/비밀번호 또는 2차 인증을 확인하세요."}

            cookies = await context.cookies()
            save_cookies(username, [dict(c) for c in cookies])

            await browser.close()
            if callback: callback("연동 완료!")
            return {"success": True, "username": username, "message": "연동 성공!"}

        except Exception as e:
            try: await browser.close()
            except: pass
            return {"success": False, "message": f"오류: {str(e)}"}

# 하위 호환성 유지
async def get_coupang_api_keys(username, password, callback=None):
    return await do_login(username, password, callback)

def save_account(username, vendor_id="", access_key="", secret_key=""):
    accounts = load_all_accounts()
    for acc in accounts:
        if acc["username"] == username:
            with open(_data_path("coupang_accounts.json"), "w", encoding="utf-8") as f:
                json.dump(accounts, f, ensure_ascii=False)
            return
    accounts.append({"username": username, "vendor_id": vendor_id, "access_key": access_key, "secret_key": secret_key})
    with open(_data_path("coupang_accounts.json"), "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False)

def delete_account(username):
    accounts = [acc for acc in load_all_accounts() if acc["username"] != username]
    with open(_data_path("coupang_accounts.json"), "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False)
    p = _data_path("wing_cookies.json")
    if os.path.exists(p):
        try:
            with open(p, "r") as f:
                all_cookies = json.load(f)
            all_cookies.pop(username, None)
            with open(p, "w") as f:
                json.dump(all_cookies, f)
        except: pass

def load_all_accounts():
    p = _data_path("coupang_accounts.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return []
