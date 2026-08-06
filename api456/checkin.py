#!/usr/bin/env python3
"""
API456 每日签到脚本（GitHub Actions 专用）

需要的配置（环境变量）：
API456_ACCOUNTS    多账号登录，格式 user1:pass1,user2:pass2
                   支持换行或逗号分隔，每行一个 user:pass
                   单账号时只需写一行即可
API456_BASE_URL    API456 站地址（可选，默认 https://api456.me）
SOCKS5_PROXY       代理，可多个（换行或逗号分隔），如
                   socks5://user:pass@host:port
TG_BOT_TOKEN       Telegram Bot Token（可选）
TG_CHAT_ID         Telegram Chat ID（可选）

模式判定：
只要 API456_ACCOUNTS 存在且解析后不为空，即进入签到流程。
单行 user:pass 即为单账号，多行即多账号，统一处理。

New-API 配额 美元换算：1 USD = 500000 quota
"""

import os
import re
import sys
import time
import json
import logging
import requests
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# 配置（全部从环境变量读取）
# ---------------------------------------------------------------------------
BASE_URL = os.getenv("API456_BASE_URL") or "https://api456.me"
ACCOUNTS = os.getenv("API456_ACCOUNTS") or ""
PROXY_ENV = os.getenv("SOCKS5_PROXY") or ""

QUOTA_PER_UNIT = 500000  # New-API 配额转 USD
BJT = timezone(timedelta(hours=8))

# ---------------------------------------------------------------------------
# 日志（北京时间）
# ---------------------------------------------------------------------------
class BJTFormatter(logging.Formatter):
    """日志时间固定为北京时间（UTC+8）"""
    def converter(self, secs):
        return time.gmtime(secs + 8 * 3600)

log = logging.getLogger("checkin")
log.setLevel(logging.INFO)
log.propagate = False
_handler = logging.StreamHandler()
_handler.setFormatter(BJTFormatter(
    fmt="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
log.addHandler(_handler)

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def mask(name: str) -> str:
    """用户名脱敏：显示前 4 位，其余用 ***** 代替"""
    if not name:
        return "*****"
    if len(name) <= 4:
        return name[0] + "****"
    return name[:4] + "*****"

def bjt_date_str() -> str:
    """北京时间日期字符串，如 '2026年08月06日'"""
    now = datetime.now(BJT)
    return f"{now.year}年{now.month:02d}月{now.day:02d}日"

def parse_proxies(raw: str) -> list:
    """解析代理配置（换行或逗号分隔），socks/socks5 统一转 socks5h"""
    proxies = []
    for item in re.split(r"[\n,]+", raw):
        url = item.strip()
        if not url:
            continue
        if url.startswith("socks5://"):
            url = "socks5h://" + url[len("socks5://"):]
        elif url.startswith("socks://"):
            url = "socks5h://" + url[len("socks://"):]
        proxies.append(url)
    return proxies

def parse_accounts(raw: str) -> list:
    """解析账号配置，支持逗号分隔和换行分隔，格式 user:pass"""
    accounts = []
    for item in re.split(r"[\n,]+", raw):
        item = item.strip()
        if not item or ":" not in item:
            continue
        user, _, passwd = item.partition(":")
        accounts.append((user.strip(), passwd.strip()))
    return accounts

def get_json(resp: requests.Response):
    """解析 JSON；被 WAF 拦截或非 JSON 时返回 None"""
    try:
        return resp.json()
    except (json.JSONDecodeError, ValueError):
        if "aliyun_waf" in resp.text.lower() or "waf" in resp.text.lower():
            log.warning("响应被 WAF 拦截（当前 IP/代理不可用）")
        return None

def quota_to_usd(quota: int) -> float:
    """配额转换为美元"""
    return round((quota or 0) / QUOTA_PER_UNIT, 2)

# ---------------------------------------------------------------------------
# 会话与 API
# ---------------------------------------------------------------------------
def create_session(proxy_url: str = "") -> requests.Session:
    """创建仿浏览器 Session（可选代理）"""
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Referer": f"{BASE_URL}/login",
        "Origin": BASE_URL,
    })
    if proxy_url:
        s.proxies.update({"http": proxy_url, "https": proxy_url})
    return s

def find_working_proxy() -> str:
    """逐个尝试代理/直连，返回第一个能绕过 WAF 的代理 URL；全部失败返回 None"""
    proxies = parse_proxies(PROXY_ENV)
    attempts = [(p, p.split("@")[-1]) for p in proxies] + [("", "直连（无代理）")]

    for proxy_url, label in attempts:
        log.info("尝试连接方式: %s", label)
        s = create_session(proxy_url)
        try:
            data = get_json(s.get(f"{BASE_URL}/api/status", timeout=25))
            if data and data.get("success"):
                log.info("✅ 连接可用：%s（已绕过 WAF）", label)
                return proxy_url
        except Exception as e:
            log.warning("连接 [%s] 异常: %s", label, e)
        log.warning("❌ 连接 [%s] 不可用，尝试下一个", label)
    return None

def do_login(session: requests.Session, username: str, password: str) -> tuple:
    """
    登录（= 触发签到）。
    成功返回 (user_data, "")；失败返回 ({}, error_message)
    """
    try:
        resp = session.post(
            f"{BASE_URL}/api/user/login",
            json={"username": username, "password": password},
            timeout=25,
        )
        data = get_json(resp)
        if not data or not data.get("success"):
            msg = data.get("message", "未知错误") if data else "响应解析失败"
            # 常见错误提示
            if "用户名或密码" in msg or "invalid" in msg.lower():
                msg = "用户名或密码错误"
            elif "未激活" in msg or "not activated" in msg.lower():
                msg = "账号未激活"
            elif "频率" in msg or "频率" in msg.lower():
                msg = "登录频率受限，请稍后重试"
            return {}, msg

        user = data.get("data", {})
        user_id = user.get("id", "")
        access_token = user.get("access_token", "")

        # 用 access_token 查询最新余额
        quota = 0
        if access_token:
            try:
                headers = {
                    "Authorization": access_token,
                    "New-API-User": str(user_id),
                }
                self_data = get_json(
                    session.get(
                        f"{BASE_URL}/api/user/self",
                        headers=headers,
                        timeout=25,
                    )
                )
                if self_data and self_data.get("success"):
                    quota = self_data.get("data", {}).get("quota", 0)
            except Exception as e:
                log.warning("查询余额异常: %s", e)

        return {
            "id": user_id,
            "username": user.get("username", username),
            "access_token": access_token,
            "quota": quota,
            "checked_in": user.get("checked_in", False),
        }, ""

    except requests.RequestException as e:
        log.error("登录请求异常: %s", e)
        return {}, str(e)

def do_checkin_for_account(session: requests.Session, username: str, password: str) -> dict:
    """单个账号登录（触发签到）+ 查余额，返回结果 dict 供汇总通知使用"""
    user, err = do_login(session, username, password)
    result = {
        "display": mask(username),
        "checked_in": False,
        "balance_usd": 0.0,
        "error": err,
    }
    if not user:
        return result

    result["checked_in"] = bool(user.get("checked_in"))
    result["balance_usd"] = quota_to_usd(user.get("quota", 0))
    return result

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    log.info("=" * 48)
    log.info("API456 每日签到脚本启动")

    accounts = parse_accounts(ACCOUNTS)
    if not accounts:
        log.error("未配置账号信息：需 API456_ACCOUNTS（格式 user:pass，多账号逗号/换行分隔），脚本退出")
        sys.exit(1)

    log.info("共 %d 个账号待签到", len(accounts))

    # 1. 选出能绕过 WAF 的连接
    proxy_url = find_working_proxy()
    if proxy_url is None:
        log.error("所有连接方式均无法绕过 WAF，请检查 SOCKS5_PROXY，脚本退出")
        sys.exit(1)

    # 2. 逐账号签到（任一失败不中断，继续下一个）
    results = []
    for username, password in accounts:
        log.info("签到中: %s", mask(username))
        session = create_session(proxy_url)  # 独立 session，避免 cookie 串扰
        result = do_checkin_for_account(session, username, password)
        results.append(result)
        if result["error"]:
            log.warning("❌ %s 登录失败: %s", mask(username), result["error"])
        elif result["checked_in"]:
            log.info("🎉 %s 签到成功，余额 $%.2f", mask(username), result["balance_usd"])
        else:
            log.info("✅ %s 今日已签到，余额 $%.2f", mask(username), result["balance_usd"])

    # 3. 发送汇总通知
    try:
        from notify import send_combined_notification
        send_combined_notification(results)
    except ImportError as e:
        log.warning("无法导入 notify 模块: %s", e)
    except Exception as e:
        log.error("发送 TG 通知异常: %s", e)

    log.info("签到流程完成")
    log.info("=" * 48)

if __name__ == "__main__":
    main()