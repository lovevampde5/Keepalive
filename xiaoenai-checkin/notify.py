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


def _format_account(r: dict) -> str:
    """格式化单个账号的通知片段"""
    username = escape(str(r.get("username", "")))

    if not r.get("success"):
        return (f"👤 <b>{username}</b>\n"
                f"   ❌ {escape(str(r.get('status', '处理失败')))}")

    icon = "🎉" if r.get("new_signin") else "✅"
    vip_tag = " 👑VIP" if r.get("is_vip") else ""
    return (f"👤 <b>{username}</b>{vip_tag}\n"
            f"   {icon} {escape(str(r.get('status', '')))}\n"
            f"   💰 额度：{r.get('quota', 0):,}"
            f"（永久 {r.get('permanent_quota', 0):,}"
            f" + 每日 {r.get('daily_quota', 0):,}）")


def send_tg_notification(data: dict) -> bool:
    """
    发送 TG 签到汇总通知

    参数 data 结构:
    {
        "date":    str,    # 北京时间日期，如 "2026年08月02日"
        "results": [       # 每个账号一条结果
            {
                "username":        str,   # 脱敏用户名
                "success":         bool,  # 整体是否成功
                "new_signin":      bool,  # True=本次新签到, False=今日已签到
                "status":          str,   # 状态描述
                "quota":           int,   # 总额度
                "permanent_quota": int,   # 永久额度
                "daily_quota":     int,   # 每日额度
                "is_vip":          bool,
            }, ...
        ],
    }

    返回 True 表示发送成功，False 表示跳过或失败
    """
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        log.info("未配置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过通知")
        return False

    date = escape(str(data.get("date", "")))
    results = data.get("results", [])
    ok_count = sum(1 for r in results if r.get("success"))

    lines = [
        "<b>肖恩AI 签到通知</b>",
        "--------------------",
        f"📅 <b>日期</b>：{date}",
        f"📊 <b>结果</b>：成功 {ok_count} / 总计 {len(results)}",
        "--------------------",
    ]
    lines.extend(_format_account(r) for r in results)

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": "\n".join(lines),
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
