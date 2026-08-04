## PidginHost 免费云服务器自动续期

自动将 PidginHost 免费服务器续期 30 天。

### 核心思路

**Google 账号登录 → 自动续期**

PidginHost 使用 **Google OAuth** 登录（无密码），无法用账号密码直接自动化。

本脚本用 **Playwright 保存完整登录态**（含 Google cookie + PidginHost session cookie），后续运行自动恢复，即使 session 过期也能自动走 Google OAuth 重新登录——因为 Google 的 cookie 也在 storage_state 中，OAuth 流程无需人工干预就能自动完成。

### 使用方法

#### 1. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

#### 2. 首次：登录（交互式，只需做一次）

```bash
python pidginhost_extend.py --login
```

- 脚本会打开一个浏览器窗口 → 跳转到 PidginHost 登录页
- 你在窗口中点击 **"Continue with Google"** → 用 Google 账号登录
- 登录成功后脚本自动保存登录态 → 立即执行续期
- 之后可关闭窗口

#### 3. 日常：自动续期（headless 无界面）

```bash
python pidginhost_extend.py --extend
```

脚本恢复已保存的登录态，自动续期。**无需任何交互。**

**自动处理 session 过期：** 如果 PidginHost 的 session cookie 过期（通常 2 周），脚本会自动：
1. 跳转到 Google OAuth 页面
2. 由于 Google 登录 cookie 依然有效，OAuth 自动完成
3. 获取新的 PidginHost session → 续期 → 保存更新后的登录态

### 环境变量

| 变量 | 说明 |
|------|------|
| `PIDGINHOST_SERVER_ID` | 服务器 ID（默认 4155） |
| `TG_BOT_TOKEN` | Telegram Bot Token（可选，用于推送通知） |
| `TG_CHAT_ID` | Telegram Chat ID（可选，用于推送通知） |

### 文件说明

| 文件 | 说明 |
|------|------|
| `storage_state.json` | Playwright 完整登录态（含所有 cookie，自动生成） |
| `session.json` | 仅 sessionid + csrftoken，用于 requests 模式（自动生成） |

### 定时执行

建议每 25 天执行一次（免费服务器 30 天到期）。

**Windows 计划任务：**
```powershell
schtasks /create /tn "PidginHost Extend" /tr "python E:\vscode\Keepalive\pidginhost-extend\pidginhost_extend.py --extend" /sc monthly /mo 1
```

**Linux crontab：**
```bash
0 8 1 * * cd /path/to/Keepalive && python pidginhost-extend/pidginhost_extend.py --extend
```

### GitHub Actions

工作流文件：`.github/workflows/pidginhost-extend.yml`

**设置步骤：**

1. 本地运行 `python pidginhost_extend.py --login` 完成首次登录
2. 将 `session.json` 的 **内容** 添加到 GitHub 仓库 Secret：
   - 仓库 → Settings → Secrets and variables → Actions → New repository secret
   - Name: `PIDGINHOST_SESSION`
   - Value: session.json 文件的全部内容（JSON 格式）
3. 工作流会在每月 1 号和 15 号自动运行

**注意：** Google cookie 和 PidginHost session 都有过期时间。如果 Action 运行失败，重新运行 `--login` 本地登录一次，更新 Secret 即可。