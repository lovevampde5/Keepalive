# AgentRouter 每日签到

自动为 [AgentRouter](https://agentrouter.org) 站点每日签到领取免费额度，并通过 TG Bot 发送通知。

**支持两种模式：**
- **单用户模式**：配置 `AGENTROUTER_USERNAME` + `AGENTROUTER_PASSWORD`
- **多用户模式**：配置 `AGENTROUTER_ACCOUNTS`（允许多个账号批量签到）

---

## 一、准备工作

1. 用 GitHub 登录 https://agentrouter.org
2. **绑定邮箱 设置密码**：进入「个人设置」→ 绑定邮箱并设置登录密码。
   - 登录时选择「邮箱」或「用户名」+ 密码登录，点击 `忘记密码` 来重置密码。
3. **准备代理**：一个能访问该站点且未被 WAF 拦截的 SOCKS5 / HTTP 代理（国内 / 香港 / 新加坡 IP）。

---

## 二、配置

### Secrets（敏感信息）

在 **Settings → Secrets → Actions secrets** 中添加：

| Secret 名称 | 值 | 说明 |
|------------|-----|------|
| `TG_BOT_TOKEN` | `123456:ABC-DEF...` | Telegram Bot Token（可选） |
| `TG_CHAT_ID` | `123456789` | Telegram Chat ID（可选） |

### Variables（非敏感信息）

在 **Settings → Secrets → Variables** 中添加：

#### 单用户模式（二选一）

| Variable 名称 | 值 | 说明 |
|--------------|-----|------|
| `AGENTROUTER_USERNAME` | `你的邮箱或用户名` | 登录账号，邮箱或 `github_<ID>`（**必需**） |
| `AGENTROUTER_PASSWORD` | `你的登录密码` | 登录密码（**必需**） |

> 单用户为原有模式，行为不变：签到后发送一条独立的 TG 通知。

#### 多用户模式（二选一）

| Variable 名称 | 值 | 说明 |
|--------------|-----|------|
| `AGENTROUTER_ACCOUNTS` | `user1:pass1,user2:pass2` | 多账号列表（**替代**单用户模式） |

`AGENTROUTER_ACCOUNTS` 格式说明：
- 每个条目：`用户名:密码`
- 多个条目用**英文逗号**或**换行**分隔
- user id 从登录响应自动获取，无需手动填写
- 示例：
  ```
  admin@example.com:pass123
  test@example.com:pass456,admin2:pass789
  ```

#### 通用变量（两种模式都需要）

| Variable 名称 | 值 | 说明 |
|--------------|-----|------|
| `SOCKS5_PROXY` | `socks5://user:pass@host:1080` | SOCKS5 代理地址（可选），支持换行/逗号分隔多个代理 |

### 模式判定逻辑

| 条件 | 模式 |
|------|------|
| `AGENTROUTER_USERNAME` 和 `AGENTROUTER_PASSWORD` 都存在 | **单用户模式**（原有逻辑） |
| 缺少 `AGENTROUTER_USERNAME` / `AGENTROUTER_PASSWORD` 任一，且 `AGENTROUTER_ACCOUNTS` 存在 | **多用户模式** |
| 以上均不满足 | 脚本报错退出 |

> 若两种模式都配置了，单用户优先（兼容现有工作流）。

---

## 三、Workflow 配置

### 已包含的 Action

`.github/workflows/agentrouter-checkin.yml` 中包含了所有变量传递。单用户使用者无需修改工作流；多用户使用者在 GitHub 仓库 Variables 中新增 `AGENTROUTER_ACCOUNTS` 即可。

---

## 四、常见错误

| 错误日志 | 含义与处理 |
|---------|-----------|
| `aliyun_waf` | 请求被阿里云 WAF 拦截，当前 IP（或代理）不可用，请检查/更换 `SOCKS5_PROXY` |
| `用户名或密码错误` | 确认已在网站「个人设置」绑定邮箱并设置密码，且用户名/邮箱正确 |
| `未配置账号信息` | 未设置任何账号变量，请检查 `AGENTROUTER_USERNAME`+`AGENTROUTER_PASSWORD` 或 `AGENTROUTER_ACCOUNTS` |
| `AGENTROUTER_ACCOUNTS 解析后无有效账号` | `AGENTROUTER_ACCOUNTS` 格式错误，请检查是否遗漏冒号分隔符 |

---

## 五、TG 通知效果

### 单用户模式

**今日已签到：**
```
<b>AgentRouter 签到通知</b>
----------------
📅 <b>日期</b>：2026年07月26日
👤 <b>用户</b>：admi*****
✅ <b>签到</b>：今日已签到
💰 <b>余额</b>：$106.30
```

**今日新签到：**
```
<b>AgentRouter 签到通知</b>
----------------
📅 <b>日期</b>：2026年07月26日
👤 <b>用户</b>：admi*****
🎉 <b>签到</b>：签到成功，额度已到账
💰 <b>余额</b>：$106.30
```

### 多用户模式（汇总通知）

```
<b>AgentRouter 签到通知</b>
----------------
📅 <b>日期</b>：2026年08月04日
✅ <b>数量</b>：3 个账号
----------------
👉 账号：user1@******
     🎉 签到成功，余额 $10.50
👉 账号：user2@******
     ✅ 今日已签到，余额 $5.20
👉 账号：test3@*****
     ❌ 登录失败：用户名或密码错误
----------------
💰 <b>总余额</b>：$15.70
```

> 失败账号计入数量、计入总数，**不计入总余额**。