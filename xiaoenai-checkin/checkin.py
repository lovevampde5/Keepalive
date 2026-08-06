#!/usr/bin/env python3
"""
肖恩AI（free.supxh.xin）每日签到脚本（GitHub Actions 专用）
使用 Cookie 认证，每次运行重新登录，支持多账号。

需要的配置（环境变量）：
  XIAOENAI_ACCOUNTS   多账号凭证，每行一个 `邮箱:密码`
                      也支持逗号分隔或单行 `邮箱:密码`
  TG_BOT_TOKEN        Telegram Bot Token（可选，为空则跳过通知）
  TG_CHAT_ID          接收通知的 Chat ID（可选）
"""

import os
import re
import sys
import logging
from datetime import datetime, timezone, timedelta
import requests

# ---------------------------------------------------------------------------
# 日志（北京时间）
# ---------------------------------------------------------------------------
BASE_URL = os.getenv("XIAOENAI_BASE_URL") or "https://free.supxh.xin"
ACCOUNTS_ENV = os.getenv("XIAOENAI_ACCOUNTS") or ""
BJT = timezone(timedelta(hours=8))

# 北京时间时区
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
    """用户名/邮箱脱敏：显示前 4 位 + *****"""
    if not name:
        return "*****"
    return (name[:4] + "*****") if len(name) > 4 else (name + "*****")

def bjt_date_str() -> str:
    """北京时间日期字符串，如 '2026年08月02日'"""
    now = datetime.now(BJT)
    return f"{now.year}年{now.month:02d}月{now.day:02d}日"

def parse_accounts(raw: str) -> list:
    """解析多账号配置（换行或逗号分隔），返回 [(username, password), ...]"""
    accounts = []
    for item in re.split(r"[\n,]+", raw):
        line = item.strip()
        if not line:
            continue
        if ":" not in line:
            log.warning("忽略格式错误的账号配置（缺少冒号）: %s", mask(line))
            continue
        # 密码中可能含冒号，只按第一个冒号切分
        username, password = line.split(":", 1)
        username, password = username.strip(), password.strip()
        if not username or not password:
            log.warning("忽略不完整的账号配置: %s", mask(line))
            continue
        accounts.append((username, password))
    return accounts

def get_json(resp: requests.Response):
    """解析 JSON；非 JSON 响应（如 Next.js 404 页面）返回 None"""
    try:
        return resp.json()
    except ValueError:
        log.warning("响应非 JSON（HTTP %s），可能接口路径已变更", resp.status_code)
        return None

# ---------------------------------------------------------------------------
# 会话与 API
# ---------------------------------------------------------------------------

def create_session() -> requests.Session:
    """创建仿浏览器 Session"""
    s = requests.Session()
    s.headers.update({
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/131.0.0.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Referer": f"{BASE_URL}/login",
        "Origin": BASE_URL,
    })
    return s

def do_login(session: requests.Session, username: str, password: str) -> bool:
    """登录，成功后 auth_token Cookie 自动存入 session"""
    payload = {"username": username, "password": password}
    try:
        data = get_json(session.post(f"{BASE_URL}/api/auth/login", json=payload, timeout=25))
        if not data:
            return False
        if data.get("success"):
            log.info("登录成功: %s", mask(username))
            return True
        log.error("登录失败: %s", data.get("message", "未知错误"))
        return False
    except requests.RequestException as e:
        log.error("登录请求异常: %s", e)
        return False

def do_signin(session: requests.Session) -> tuple:
    """
    执行签到，返回 (是否本次新签到, 状态描述)
    接口在「今天已签到」时也返回 success:false，需按 message 区分。
    """
    try:
        data = get_json(session.post(f"{BASE_URL}/api/user/signin", json={}, timeout=25))
        if not data:
            return False, "签到接口异常"

        msg = data.get("message", "")
        if data.get("success"):
            log.info("🎉 签到成功，额度已到账")
            return True, "签到成功，额度已到账"
        if "已经签到" in msg or "已签到" in msg:
            log.info("✅ 今日已签到")
            return False, "今日已签到"
        log.warning("签到失败: %s", msg)
        return False, f"签到失败：{msg or '未知错误'}"
    except requests.RequestException as e:
        log.error("签到请求异常: %s", e)
        return False, "签到请求异常"

def get_user_info(session: requests.Session) -> dict:
    """获取用户信息（含 quota / permanentQuota / dailyQuota / isVip）"""
    try:
        data = get_json(session.get(f"{BASE_URL}/api/auth/me", timeout=25))
        if data and data.get("success"):
            return data.get("data", {})
        if data:
            log.warning("获取用户信息失败: %s", data.get("message", ""))
    except requests.RequestException as e:
        log.error("获取用户信息异常: %s", e)
    return {}

# ---------------------------------------------------------------------------
# 单账号流程
# ---------------------------------------------------------------------------

def process_account(username: str, password: str) -> dict:
    """
    处理单个账号的登录 + 签到 + 查额度
    返回结果字典，供 notify 汇总使用
    """
    result = {
        "username": mask(username),
        "success": False,
        "new_signin": False,
        "status": "",
        "quota": 0,
        "permanent_quota": 0,
        "daily_quota": 0,
        "is_vip": False,
    }

    session = create_session()

    if not do_login(session, username, password):
        result["status"] = "登录失败"
        return result

    result["new_signin"], result["status"] = do_signin(session)

    # 签到后查询最新额度
    info = get_user_info(session)
    if not info:
        result["status"] += "（额度查询失败）"
        return result

    result["success"] = True
    result["username"] = mask(info.get("username") or username)
    result["quota"] = info.get("quota", 0)
    result["permanent_quota"] = info.get("permanentQuota", 0)
    result["daily_quota"] = info.get("dailyQuota", 0)
    result["is_vip"] = bool(info.get("isVip"))
    log.info("当前额度: %s（永久 %s + 每日 %s）",
             f"{result['quota']:,}",
             f"{result['permanent_quota']:,}",
             f"{result['daily_quota']:,}")
    return result

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    log.info("=" * 48)
    log.info("肖恩AI 每日签到脚本启动")
    log.info("目标站点: %s", BASE_URL)

    accounts = parse_accounts(ACCOUNTS_ENV)
    if not accounts:
        log.error("未配置 XIAOENAI_ACCOUNTS（格式：每行 `邮箱:密码`），脚本退出")
        sys.exit(1)

    log.info("共 %d 个账号待签到", len(accounts))

    results = []
    for idx, (username, password) in enumerate(accounts, 1):
        log.info("-" * 48)
        log.info("[%d/%d] 处理账号: %s", idx, len(accounts), mask(username))
        results.append(process_account(username, password))

    log.info("-" * 48)

    # 发送 TG 汇总通知
    notify_data = {
        "date": bjt_date_str(),
        "results": results,
    }
    try:
        from notify import send_tg_notification  # type: ignore
        send_tg_notification(notify_data)
    except ImportError as e:
        log.warning("无法导入 notify 模块: %s", e)
    except Exception as e:
        log.error("发送 TG 通知异常: %s", e)

    ok_count = sum(1 for r in results if r["success"])
    log.info("签到流程完成：成功 %d / 总计 %d", ok_count, len(results))
    log.info("=" * 48)

    # 有任一账号失败时以非零码退出，便于 Actions 标红告警
    if ok_count < len(results):
        sys.exit(1)

if __name__ == "__main__":
    main()
