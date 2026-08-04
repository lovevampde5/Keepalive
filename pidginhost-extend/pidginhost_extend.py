"""
PidginHost 免费云服务器自动续期脚本

自动处理 Google OAuth 登录（首次手动，之后自动恢复登录态）。
核心思路：用 Playwright 的 storage_state 保存完整登录态（含 Google cookie 和
PidginHost session cookie），session 过期时自动走 Google 登录流程，
由于 Google cookie 仍在有效期，OAuth 无需人工干预即可自动完成。

用法:
    python pidginhost_extend.py --login     # 首次：浏览器手动 Google 登录并保存 session
    python pidginhost_extend.py --extend    # 日常：自动续期（headless，自动处理过期）
"""

import os
import sys
import json
import time
import re
import requests
from datetime import datetime, timedelta
from pathlib import Path

# ─── 配置 ───────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
STORAGE_FILE = BASE_DIR / "storage_state.json"
SESSION_FILE = BASE_DIR / "session.json"

# 默认服务器 ID，可通过环境变量覆盖
SERVER_ID = int(os.environ.get("PIDGINHOST_SERVER_ID", "4155"))
PANEL_BASE = "https://www.pidginhost.com"
SERVER_URL = f"{PANEL_BASE}/panel/cloud/servers/{SERVER_ID}/"
LOGIN_URL = f"{PANEL_BASE}/panel/account/login?next=/panel/cloud/servers/{SERVER_ID}/"

# ─── 日志 & Telegram 推送 ─────────────────────────────
log_buffer = []


def log(msg):
    print(msg)
    log_buffer.append(msg)


def send_tg_log():
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not token or not chat_id:
        log("⚠️ Telegram 未配置，跳过推送")
        return

    utc_now = datetime.utcnow()
    beijing_now = utc_now + timedelta(hours=8)
    now_str = beijing_now.strftime("%Y-%m-%d %H:%M:%S") + " UTC+8"

    final_msg = f"📌 PidginHost 续期日志\n🕒 {now_str}\n\n" + "\n".join(log_buffer)

    for i in range(0, len(final_msg), 3900):
        chunk = final_msg[i:i + 3900]
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{token}/sendMessage",
                params={"chat_id": chat_id, "text": chunk},
                timeout=10,
            )
            if resp.status_code == 200:
                log(f"✅ Telegram 推送成功 [{i // 3900 + 1}]")
            else:
                log(f"⚠️ Telegram 推送失败 [{i // 3900 + 1}]: HTTP {resp.status_code}")
        except Exception as e:
            log(f"⚠️ Telegram 推送异常 [{i // 3900 + 1}]: {e}")


# ─── 核心功能 ───────────────────────────────────────────

def save_storage(context):
    """保存 storage_state 和 session cookie 到文件"""
    storage = context.storage_state()
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(storage, f)

    session_cookies = {}
    for cookie in storage.get("cookies", []):
        if cookie["name"] in ("sessionid", "csrftoken") and "pidginhost" in cookie.get("domain", ""):
            session_cookies[cookie["name"]] = cookie["value"]

    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(session_cookies, f)

    log(f"✅ 登录态已保存 ({STORAGE_FILE.name} / {SESSION_FILE.name})")


def click_extend(page):
    """在服务器页面点击 'Extend 30 days' 按钮并验证结果"""
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    body_text = page.locator("body").inner_text()

    # 页面可能没有续期按钮（例如已续期、非免费服务器、或未登录）
    if "Extend" not in body_text:
        if "Log in" in body_text or "login" in page.url:
            log("⚠️ 未登录，页面跳转到登录页")
            return "not_logged_in"
        log("⚠️ 页面未找到 'Extend 30 days' 按钮（可能已续期或不可续期）")
        return "no_button"

    btn = page.get_by_role("button", name="Extend 30 days")
    if btn.count() == 0:
        btn = page.locator("button:has-text('Extend')")
    if btn.count() == 0:
        log("❌ 未找到 'Extend 30 days' 按钮")
        return "no_button"

    btn.click()
    time.sleep(2)

    body_text = page.locator("body").inner_text()
    if "Server extended" in body_text or "extended" in body_text.lower():
        log("✅ 服务器已成功续期 30 天！")
        return "success"
    else:
        log("⚠️ 点击续期按钮后未看到成功提示")
        return "unknown"


def auto_google_relogin(page, context):
    """
    自动重新登录：当 PidginHost session 过期时，跳转 Google OAuth。
    由于 storage_state 保存了 Google 的登录 cookie，Google 会自动
    完成授权（无需人工），随后自动回到 PidginHost。
    返回 True 表示登录成功。
    """
    log("🔄 PidginHost session 已过期，尝试自动通过 Google 重新登录...")

    # 确保在登录页
    page.goto(LOGIN_URL)
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    # 点击 "Continue with Google"
    google_link = page.get_by_text("Continue with Google")
    if google_link.count() == 0:
        google_link = page.locator("a:has-text('Google')")
    if google_link.count() == 0:
        log("❌ 未找到 'Continue with Google' 按钮")
        return False

    log("🔄 点击 Continue with Google，等待 Google 自动授权...")
    google_link.click()

    # 等待 OAuth 完成（Google 会自动跳回 pidginhost）
    # 如果 Google cookie 有效：几秒内完成；如果过期：会停在 Google 登录页
    try:
        page.wait_for_url(f"{PANEL_BASE}/**", timeout=60000)
    except Exception:
        # 可能停在 Google 登录页或中间页
        pass

    # 等页面稳定
    time.sleep(3)

    if "accounts.google.com" in page.url:
        log("⚠️ Google cookie 也已过期，需要手动登录。")
        log("📌 请运行: python pidginhost_extend.py --login")
        return False

    # 可能需要点一次 "Continue as xxx" / 确认页
    try:
        continue_btn = page.get_by_role("button", name=re.compile(r"Continue|继续", re.I))
        if continue_btn.count() > 0:
            continue_btn.click()
            time.sleep(3)
    except Exception:
        pass

    # 检查是否回到了 panel
    if "panel" in page.url or "/panel/" in page.content():
        log("✅ 自动重新登录成功！")
        save_storage(context)
        return True
    else:
        log(f"⚠️ 登录结果未知，当前 URL: {page.url}")
        return False


def do_login():
    """交互式登录：打开浏览器 → 用户手动 Google 登录 → 保存 session → 续期"""
    from playwright.sync_api import sync_playwright

    log("🔄 打开浏览器，请手动通过 Google 登录...")
    log("📌 请在浏览器窗口中完成 Google 登录")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto(LOGIN_URL)
        page.wait_for_load_state("networkidle")

        log("⏳ 等待用户完成 Google 登录（最长 5 分钟）...")
        try:
            page.wait_for_url(f"{PANEL_BASE}/panel/**", timeout=300_000)
            log("✅ 登录成功！")
        except Exception:
            current = page.url
            if "panel" in current:
                log("✅ 已检测到面板页面")
            else:
                log(f"❌ 登录超时或失败，当前页面: {current}")
                context.close()
                browser.close()
                return False

        # 导航到服务器页面
        if SERVER_URL not in page.url:
            page.goto(SERVER_URL)
            page.wait_for_load_state("networkidle")

        # 保存登录态
        save_storage(context)

        # 立即执行续期
        log("")
        log("🔄 首次登录后立即执行续期...")
        result = click_extend(page)
        if result == "success":
            log("✅ 续期成功！")
            ok = True
        else:
            log("⚠️ 续期未成功，请检查")
            ok = False

        context.close()
        browser.close()
        return ok


def do_extend():
    """自动续期：优先 Playwright storage_state（可自动处理过期），降级 requests"""
    if STORAGE_FILE.exists():
        log("🔄 使用 Playwright headless 模式续期...")
        return _extend_with_storage()
    elif SESSION_FILE.exists():
        log("🔄 使用 requests 直接续期（无浏览器）...")
        return _extend_with_requests()
    else:
        log("❌ 未找到登录态文件，请先运行: python pidginhost_extend.py --login")
        return False


def _extend_with_storage():
    """从 storage_state.json 恢复登录态，headless 续期；session 过期时自动 Google 重登"""
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                storage = json.load(f)
            context = browser.new_context(storage_state=storage)
            page = context.new_page()

            # 访问服务器页面
            page.goto(SERVER_URL)
            page.wait_for_load_state("networkidle")
            time.sleep(2)

            body_text = page.locator("body").inner_text()

            # 如果未登录（跳到登录页），尝试自动 Google 重登
            if "login" in page.url or "Log in" in body_text:
                log("⚠️ 检测到登录态已失效")
                if not auto_google_relogin(page, context):
                    log("❌ 自动重登失败")
                    context.close()
                    browser.close()
                    return False
                # 重登成功后回到服务器页
                page.goto(SERVER_URL)
                page.wait_for_load_state("networkidle")

            result = click_extend(page)

            # 保存最新登录态
            save_storage(context)

            context.close()
            browser.close()
            return result == "success"

    except Exception as e:
        log(f"❌ storage_state 模式续期异常: {e}")
        return False


def _extend_with_requests():
    """使用 requests 直接发送续期请求（无浏览器，纯 HTTP）"""
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            session_data = json.load(f)

        sessionid = session_data.get("sessionid", "")
        csrftoken = session_data.get("csrftoken", "")

        if not sessionid or not csrftoken:
            log("❌ session.json 中缺少 sessionid 或 csrftoken")
            return False

        s = requests.Session()
        s.cookies.set("sessionid", sessionid, domain="www.pidginhost.com")
        s.cookies.set("csrftoken", csrftoken, domain="www.pidginhost.com")
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": SERVER_URL,
        })

        # 1. 先 GET 页面，获取最新 csrfmiddlewaretoken
        log("📌 获取页面 CSRF token...")
        resp = s.get(SERVER_URL, timeout=15)
        if resp.status_code != 200:
            log(f"❌ 获取页面失败: HTTP {resp.status_code}")
            if resp.status_code in (301, 302, 303, 307, 308):
                log("⚠️ Session 已过期，请重新运行 --login（或改用 Playwright 模式）")
            return False

        match = re.search(
            r'<input[^>]*name=["\']csrfmiddlewaretoken["\'][^>]*value=["\']([^"\']+)["\']',
            resp.text,
        )
        if not match:
            log("❌ 无法提取 CSRF token，session 可能已过期")
            return False

        csrf_token = match.group(1)
        log("✅ 成功获取 CSRF token")

        # 2. 发送续期 POST
        log("📌 发送续期请求...")
        post_resp = s.post(
            SERVER_URL,
            data={
                "csrfmiddlewaretoken": csrf_token,
                "action": "extend_renewal",
            },
            headers={"X-CSRFToken": csrf_token},
            timeout=15,
        )

        if post_resp.status_code == 200:
            if "Server extended" in post_resp.text or "extended" in post_resp.text.lower():
                log("✅ 服务器已成功续期 30 天！")
                return True
            else:
                log("⚠️ 请求返回 200，但未检测到成功提示")
                return False
        else:
            log(f"❌ 续期请求失败: HTTP {post_resp.status_code}")
            if post_resp.status_code in (301, 302, 303, 307, 308):
                log("⚠️ Session 已过期，请重新运行 --login")
            return False

    except Exception as e:
        log(f"❌ requests 模式续期异常: {e}")
        return False


# ─── 主入口 ─────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    mode = sys.argv[1]
    if mode == "--login":
        log("🔐 PidginHost 登录模式")
        log(f"📌 服务器 ID: {SERVER_ID}")
        result = do_login()
    elif mode == "--extend":
        log("🔁 PidginHost 自动续期模式")
        log(f"📌 服务器 ID: {SERVER_ID}")
        result = do_extend()
    else:
        print(f"❌ 未知参数: {mode}")
        print(__doc__)
        sys.exit(1)

    send_tg_log()

    if not result:
        sys.exit(1)


if __name__ == "__main__":
    main()