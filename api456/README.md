# API456 每日签到

针对 [https://api456.me/](https://api456.me/) 中转站的自动签到脚本，支持多账号和 Telegram 通知。

## 功能

- ✅ 自动登录 + 签到触发
- ✅ 余额查询（硬币 / USD）
- ✅ 多账号批量签到（`API456_ACCOUNTS`）
- ✅ Telegram 汇总通知

## 使用方法

### 1. 配置环境变量

在 GitHub Actions 的 **Settings → Secrets and variables → Actions** 中设置：

#### Variables（公开变量）

| 变量名 | 说明 | 是否必需 |
|--------|------|----------|
| `API456_ACCOUNTS` | 账号列表，格式 `user1:pass1,user2:pass2`，支持换行或逗号分隔 | **是** |
| `API456_BASE_URL` | 站地址，默认 `https://api456.me` | 可选 |

#### Secrets（机密变量）

| 变量名 | 说明 | 是否必需 |
|--------|------|----------|
| `TG_BOT_TOKEN` | Telegram Bot Token | 可选 |
| `TG_CHAT_ID` | Telegram Chat ID | 可选 |

### 2. 账号格式

`API456_ACCOUNTS` 支持多种分隔方式：

```
user1:pass1,user2:pass2
```

或换行分隔（在 GitHub Variables 中换行输入）：

```
user1:pass1
user2:pass2
```

> 单行 `user:pass` 即单账号，无需额外配置。

### 3. 工作流

- 每天 **UTC 02:30**（北京时间 10:30）自动执行
- 支持手动触发（`workflow_dispatch`）

## 项目结构

```
api456/
├── checkin.py         # 签到主脚本
├── notify.py          # Telegram 通知组件
├── requirements.txt   # Python 依赖
└── README.md          # 说明文档
```

## 常见问题

| 错误 | 原因与处理 |
|------|-----------|
| 登录失败：用户名或密码错误 | 确认账号密码正确 |
| 登录失败：账号未激活 | 账号尚未激活或已被禁用 |
| 签到接口异常 | 接口路径可能已变更，检查 `BASE_URL` |
| 未配置账号信息 | 未设置 `API456_ACCOUNTS` |