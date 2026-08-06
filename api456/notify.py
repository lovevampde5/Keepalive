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


def send_combined_notification(notify_data: dict) -> bool:
    """
    发送多用户汇总签到通知

    参数 notify_data 结构:
    {
        "date":    str,    # 北京时间日期，如 "2026年08月06日"
        "results": [
            {
                "username":     str,   # 脱敏后账号
                "success":      bool,  # True=成功, False=失败
                "new_signin":   bool,  # True=本次新签到, False=今日已签到
                "status":       str,   # 状态描述
                "quota":         int,   # 当前额度
                "balance_coins": float, # 当前余额硬币
            },
            ...
        ]
    }

    返回 True 表示发送成功，False 表示跳过或失败
    """
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        log.info("未配置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过通知")
        return False

    results = notify_data.get("results", [])
    date = escape(notify_data.get("date", ""))
    total_balance = sum(r.get("balance_coins", 0.0) for r in results if r.get("success"))

    lines = [
        "<b>API456 签到通知</b>",
        "----------------",
        f"📅 <b>日期</b>：{date}",
        f"✅ <b>数量</b>：{len(results)} 个账号",
        "----------------",
    ]
    for r in results:
        display = escape(str(r.get("username", "")))
        lines.append(f"👉 账号：{display}")
        if not r.get("success"):
            lines.append(f"     ❌ 签到失败：{escape(str(r.get('status', '')))}")
        elif r.get("new_signin"):
            lines.append(f"     🎉 签到成功，余额 {r.get('balance_coins', 0.0):,.2f} 硬币")
        else:
            lines.append(f"     ✅ 今日已签到，余额 {r.get('balance_coins', 0.0):,.2f} 硬币")
    lines.append("----------------")
    lines.append(f"💰 <b>总余额</b>：{total_balance:,.2f} 硬币")
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