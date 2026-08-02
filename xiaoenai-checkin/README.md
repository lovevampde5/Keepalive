# xiaoenai-ckin

肖恩AI（[free.supxh.xin](https://free.supxh.xin)）免费大模型 API 每日自动签到脚本。

## 功能

- ✅ 每日自动登录 + 签到（北京时间 00:05，GitHub Actions 定时）
- ✅ 支持多账号，TG 汇总一条通知
- ✅ 每次运行重新登录，无需 Cookie 持久化
- ✅ 签到后查询最新额度（总额 / 永久 / 每日）
- ✅ 任一账号失败时 Action 标红，便于告警

## 目录结构

```
xiaoenai-ckin/
├── checkin.py        # 主流程：登录 → 签到 → 查额度 → 汇总
├── notify.py         # Telegram 通知组件
├── requirements.txt
└── README.md

.github/workflows/
  └── xiaoenai-checkin.yml
```

## GitHub Secrets 配置

在仓库 Settings → Secrets and variables → Actions 中配置：

| Secret | 说明 |
|--------|------|
| `XIAOENAI_ACCOUNTS` | 多账号凭证，每行 `邮箱:密码`（支持逗号分隔） |
| `TG_BOT_TOKEN` | Telegram Bot Token（可选，缺省则跳过通知） |
| `TG_CHAT_ID` | 接收通知的 Chat ID（可选） |

### XIAOENAI_ACCOUNTS 示例

```
12345678@qq.com:password1
user2@qq.com:password2
```

单账号也支持单行格式。

## 本地调试

```bash
cd xiaoenai-ckin
pip install -r requirements.txt

# Linux/macOS
export XIAOENAI_ACCOUNTS="12345678@qq.com:password1"
export TG_BOT_TOKEN="your-bot-token"
export TG_CHAT_ID="your-chat-id"
python checkin.py

# Windows PowerShell
$env:XIAOENAI_ACCOUNTS="12345678@qq.com:password1"
$env:TG_BOT_TOKEN="your-bot-token"
$env:TG_CHAT_ID="your-chat-id"
python checkin.py
```

## 接口说明

| 功能 | 接口 | 说明 |
|------|------|------|
| 登录 | `POST /api/auth/login` | body `{username, password}`，`username` 字段填邮箱；返回 `auth_token` Cookie，有效期 7 天 |
| 签到 | `POST /api/user/signin` | 带 Cookie，空 body；已签到返回 `success:false` |
| 用户信息 | `GET /api/auth/me` | 返回 `quota` / `permanentQuota` / `dailyQuota` / `hasSignedInToday` / `isVip` |

## TG 通知示例

```
肖恩AI 签到通知
----------------
📅 日期：2026年08月02日
📊 结果：成功 1 / 总计 1
----------------
👤 1234*****
   ✅ 今日已签到
   💰 额度：8,452（永久 8,000 + 每日 452）
```

## 定时说明

- 默认北京时间每日 00:05 运行（cron `5 16 * * *` UTC）
- 可在 GitHub Actions 页面手动触发 `肖恩AI 每日签到` workflow
