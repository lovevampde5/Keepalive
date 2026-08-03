#!/usr/bin/env python3
"""
TG 通知组件
通过 Telegram Bot API 发送签到通知，作为独立模块被 checkin.py 调用。
使用 HTML parse_mode，避免与 Markdown 特殊字符冲突。
"""

import os
import logging
from html import escape
import requests

log = logging.getLogger("notify")

# TG 配置（从环境变量读取，为空则跳过通知）
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN") or ""
TG_CHAT_ID = os.getenv("TG_CHAT_ID") or ""


def send_tg_notification(data: dict) -> bool:
    """
    发送 TG 签到通知

    参数 data 结构:
    {
        "username":    str,   # 脱敏后的用户名，如 "yuti*****"
        "date":        str,   # 北京时间日期，如 "2026年07月26日"
        "checked_in":  bool,  # True=今日已签到, False=本次新签到
        "balance_usd": float, # 当前总余额
    }

    返回 True 表示发送成功，False 表示跳过或失败
    """
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        log.info("未配置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过通知")
        return False

    username = escape(str(data.get("username", "")))
    date = escape(str(data.get("date", "")))
    balance = data.get("balance_usd", 0.0)
    sign_line = "✅ <b>签到</b>：今日已签到" if data.get("checked_in") \
        else "🎉 <b>签到</b>：签到成功，额度已到账"

    message = (
        f"<b>AgentRouter 签到通知</b>\n"
        f"----------------\n"
        f"📅 <b>日期</b>：{date}\n"
        f"👤 <b>用户</b>：{username}\n"
        f"{sign_line}\n"
        f"💰 <b>余额</b>：${balance:,.2f}"
    )

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        result = resp.json()
        if result.get("ok"):
            log.info("TG 通知发送成功")
            return True
        log.warning("TG 通知发送失败: %s", result.get("description", "未知错误"))
        return False
    except requests.RequestException as e:
        log.error("TG 通知请求异常: %s", e)
        return False


def _bjt_date_str() -> str:
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone(timedelta(hours=8)))
    return f"{now.year}年{now.month:02d}月{now.day:02d}日"


def send_combined_notification(results: list) -> bool:
    """
    发送多用户汇总签到通知

    参数 results 结构:
    [
        {
            "display":     str,   # 脱敏后账号，如 "user1@******"
            "checked_in":  bool,  # True=本次新签到, False=今日已签到
            "balance_usd": float, # 该账号当前余额（失败为 0）
            "error":       str,   # 失败原因，空串表示成功
        },
        ...
    ]

    返回 True 表示发送成功，False 表示跳过或失败
    """
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        log.info("未配置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过通知")
        return False

    success = [r for r in results if not r.get("error")]
    total_balance = sum(r.get("balance_usd", 0.0) for r in success)
    date = escape(_bjt_date_str())

    lines = [
        "<b>AgentRouter 签到通知</b>",
        "----------------",
        f"📅 <b>日期</b>：{date}",
        f"✅ <b>数量</b>：{len(results)} 个账号",
        "----------------",
    ]
    for r in results:
        display = escape(str(r.get("display", "")))
        lines.append(f"👉 账号：{display}")
        if r.get("error"):
            lines.append(f"     ❌ 登录失败：{escape(str(r['error']))}")
        elif r.get("checked_in"):
            lines.append(f"     🎉 签到成功，余额 ${r.get('balance_usd', 0.0):,.2f}")
        else:
            lines.append(f"     ✅ 今日已签到，余额 ${r.get('balance_usd', 0.0):,.2f}")
    lines.append("----------------")
    lines.append(f"💰 <b>总余额</b>：${total_balance:,.2f}")
    message = "\n".join(lines)

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        result = resp.json()
        if result.get("ok"):
            log.info("TG 汇总通知发送成功")
            return True
        log.warning("TG 通知发送失败: %s", result.get("description", "未知错误"))
        return False
    except requests.RequestException as e:
        log.error("TG 通知请求异常: %s", e)
        return False
