# Rustix 服务器自动启动

自动登录 [my.rustix.me](https://my.rustix.me)，进入 Manage Server，检测并启动服务器，通过浏览器控制台 `Running Done!` 与 stop 按钮状态确认上线。支持多账号轮流操作。

## 功能

- 多账号轮流登录与操作（每个账号独立浏览器上下文）
- 自动登录 → 点击 `Manage Server` → 判断 `start` 按钮是否可点击
  - `start` 可点击 → 服务器离线，点击启动
  - `start` 不可点击 → 服务器已在线，跳过
- 监听浏览器控制台输出 `Running Done!` 确认上线
- 通过 `stop` 按钮可点击状态验证（**不点击 stop**）
- 完整日志输出 + 文件日志 `run.log`
- 支持 GitHub Actions 自动运行：手动触发 / 定时器 / Uptime Kuma 故障触发
- 支持 Telegram 通知（批量汇总通知，邮箱脱敏）

## 目录结构

```
.github/workflows/rustix-checkin.yml  # GitHub Actions 工作流
rustix-auto/
├── main.py                     # 主脚本
├── notify.py                   # Telegram 通知组件
├── requirements.txt            # Python 依赖
├── accounts.example.json       # 账号配置示例
├── .env.example                # 环境变量示例
└── .gitignore
```

## 配置 Secrets

在仓库 **Settings → Secrets and variables → Actions → New repository secret** 添加：

- 名称：`RUSTIX_ACCOUNTS`
- 值（简单格式 `邮箱:密码`，多账号用英文逗号分隔）：
  ```
  a@example.com:pwd1,b@example.com:pwd2
  ```
  > 注意：密码不能包含英文逗号；密码可以包含冒号（按第一个冒号分割邮箱与密码）。

可选通知 Secrets

- `TG_BOT_TOKEN`：Bot Token
- `TG_CHAT_ID`：Chat ID

## 通知示例

```
📊 Rustix 批量执行汇总

🚩 总体: 🎉 全部成功
⏰ 时间: 2026-06-27 13:46:00
📈 统计: 共 2 个
✅ 成功 2 | ❌ 失败 0
━━━━━━━━━━━━━━━━━━
账号明细
1️⃣ *********@example.com
    ✅ 成功启动
2️⃣ **********@example.com
    🟢 已在线
━━━━━━━━━━━━━━━━━━
🔗 前往控制台
```

> 未配置 `TG_BOT_TOKEN` / `TG_CHAT_ID` 时自动跳过通知，不影响主流程。网络异常时仅记录日志，不中断运行。

## GitHub Actions 自动运行

工作流文件：`.github/workflows/rustix-checkin.yml`，支持三种触发方式：

| 触发方式 | 说明 | 配置 |
|----------|------|------|
| 手动触发 | Actions 页面点 Run workflow | 默认支持，无需配置 |
| 定时器 | 按 cron 周期执行 | 取消注释 `schedule` 段（默认已停用）|
| Uptime Kuma | 服务器离线时自动触发拉起 | 见下方配置 |

### 方式一：定时触发（默认已停用）

如需恢复定时触发，编辑 workflow 取消注释 `schedule` 段：

```yaml
on:
  schedule:
    - cron: '0 */6 * * *'   # 每 6 小时
    # - cron: '0 * * * *'   # 每小时
    # - cron: '0 0 * * *'   # 每天 0 点
  workflow_dispatch:
```

> GitHub Actions cron 使用 UTC 时间。

### 方式二：Uptime Kuma 故障触发（推荐，当前默认）

当 Uptime Kuma 检测到服务器离线（DOWN）时，通过 Webhook 调用 GitHub `repository_dispatch` API 触发 workflow；服务器恢复（UP）时触发但自动跳过执行，不浪费 Actions 额度。

**触发逻辑**：workflow 通过 `if` 判断 `client_payload.status` 是否包含 `Down`，仅在 Down 时执行启动流程。

#### 1. 创建 GitHub PAT

Uptime Kuma 调用 GitHub API 需要 Personal Access Token：

1. GitHub → Settings → Developer settings → **Personal access tokens** → Fine-grained tokens → Generate new token
2. 设置：
   - **Token name**：`uptime-kuma-rustix`
   - **Repository access**：Only select repositories → 勾选 `Keepalive`
   - **Permissions**：Repository permissions → Actions → Read and write
3. 复制生成的 Token（只显示一次）

#### 2. Uptime Kuma 配置 Webhook 通知

在 Uptime Kuma 新建通知，类型选 **Webhook**：

| 字段 | 填写内容 |
|------|---------|
| 显示名称 | `Rustix 触发`（自定义）|
| Post URL | `https://api.github.com/repos/<用户名>/Keepalive/dispatches` |
| HTTP 方法 | `POST` |

勾选「额外 Header」，填：

```json
{
  "Authorization": "Bearer <你的PAT>",
  "Accept": "application/vnd.github+json"
}
```

请求体选「自定义」，填：

```json
{
  "event_type": "rustix",
  "client_payload": {
    "status": "{{ status }}"
  }
}
```

> 关键：`event_type` 必须为 `rustix`，与 workflow 里 `types: [rustix]` 对应。`{{msg}}` 是 Uptime Kuma 内置模板变量，DOWN 时值为 `Down`，UP 时值为 `Up`。

#### 3. 关联到监控项

在 Rustix 服务器对应的监控项设置页底部「通知」处，勾选刚创建的 Webhook 通知。

#### 4. 测试

- 手动 Pause 再 Resume 监控项，触发一次 DOWN
- 去仓库 **Actions** 页面，应看到 `rustix-auto-alive` 产生新 run，触发事件显示 `repository_dispatch`
- DOWN 时正常执行启动流程；UP 恢复时 run 显示 skipped（不消耗 Actions 分钟数）

### 切换触发方式

- **从定时切换到 Uptime Kuma**：注释 `schedule` 段，保留 `repository_dispatch`（当前默认状态）
- **从 Uptime Kuma 切换回定时**：取消注释 `schedule` 段，删除 `repository_dispatch` 段及 job 的 `if` 条件
- **两者并存**：同时保留 `schedule` + `repository_dispatch`（定时兜底 + 故障即时触发），`if` 条件需保留以过滤 UP 事件

## 说明

- 账号密码等敏感信息仅通过 `accounts.json`（本地）或 `RUSTIX_ACCOUNTS`（环境变量/Secrets）传入，**不会**硬编码到脚本或提交到仓库。
- 调试截图 `debug_*.png` 仅在找不到关键元素时生成，便于排查页面结构变化。
- 若站点页面结构更新导致选择器失效，可在 `find_button_by_text` / `find_first_clickable` 中补充选择器。
- Uptime Kuma 方案下，PAT 存在于 Uptime Kuma 配置中，请确保 Uptime Kuma 所在机器安全；建议用 fine-grained PAT 最小化权限并定期轮换。
