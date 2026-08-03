"""checkin.py 纯函数单元测试（pytest，非 CI 依赖）"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import checkin  # noqa: E402


def test_parse_accounts_comma():
    raw = "user1@a.com:pass1, user2@b.com:pass2"
    assert checkin.parse_accounts(raw) == [
        ("user1@a.com", "pass1"),
        ("user2@b.com", "pass2"),
    ]


def test_parse_accounts_newline_and_mixed():
    raw = "user1@a.com:pass1\nuser2@b.com:pass2,user3@c.com:pass3"
    assert len(checkin.parse_accounts(raw)) == 3


def test_parse_accounts_password_with_colon():
    raw = "user@a.com:pa:ss:word"
    assert checkin.parse_accounts(raw) == [("user@a.com", "pa:ss:word")]


def test_parse_accounts_skips_invalid():
    raw = "user1@a.com:pass1\n\nno-colon-line\n:emptypass\nuser2@b.com:pass2"
    assert checkin.parse_accounts(raw) == [
        ("user1@a.com", "pass1"),
        ("user2@b.com", "pass2"),
    ]


def test_detect_mode_single_first():
    assert checkin.detect_mode("u", "p", "") == "single"
    assert checkin.detect_mode("u", "p", "a:b") == "single"  # 单用户优先


def test_detect_mode_multi_when_partial_missing():
    assert checkin.detect_mode("u", "", "a:b") == "multi"
    assert checkin.detect_mode("", "p", "a:b") == "multi"


def test_detect_mode_none():
    assert checkin.detect_mode("", "", "") == "none"


def test_mask():
    assert checkin.mask("user1@example.com") == "user*****"  # 前 4 位 user
    assert checkin.mask("admin") == "admi*****"
    assert checkin.mask("") == "*****"