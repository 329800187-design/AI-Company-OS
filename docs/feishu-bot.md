# 飞书群聊智能体接入

AI Company OS 支持把飞书企业自建应用机器人接入群聊：群里 `@机器人` 提问，系统调用 Commander 聊天能力并回复到同一条消息下。

## 1. 本地配置

在 `.env` 中添加：

```env
FEISHU_BOT_ENABLED=true
FEISHU_APP_ID=你的 App ID
FEISHU_APP_SECRET=你的 App Secret
FEISHU_REPLY_ONLY_MENTION=true
FEISHU_MAX_REPLY_CHARS=1800
```

如飞书事件订阅配置了 Verification Token，也添加：

```env
FEISHU_VERIFICATION_TOKEN=你的 Verification Token
```

MVP 暂不处理加密事件。飞书后台请先关闭事件加密；如必须开启，再补 `FEISHU_ENCRYPT_KEY` 解密支持。

## 2. 推荐：长连接模式

如果飞书后台使用“长连接模式”，本地不需要公网 HTTPS 回调地址。安装 SDK：

```bash
pip install lark-oapi
```

然后启动长连接 worker：

```bash
python scripts/feishu_long_connection_worker.py
```

保持这个进程运行，机器人被拉进群后，群里 `@机器人 问题` 即可触发回复。

## 3. 备用：HTTP 回调模式

如果改用 HTTP 回调，接口为：

```text
POST /integrations/feishu/events
GET  /integrations/feishu/health
```

飞书事件订阅要求公网 HTTPS 地址。开发环境可用 Cloudflare Tunnel 或 ngrok 暴露：

```text
https://你的公网域名/integrations/feishu/events
```

## 4. 飞书后台配置

1. 开启机器人能力。
2. 权限中申请发送消息、接收消息相关权限。
3. 事件订阅中选择长连接模式或 HTTP 回调模式。
4. 订阅接收消息事件：`im.message.receive_v1`。
4. 把机器人拉入群聊。
5. 群里通过 `@机器人 问题` 触发回复。

## 5. 安全说明

- App Secret 只放 `.env`，不要写入源码或提交仓库。
- 群聊默认只在被 @ 时回复，避免刷屏。
- 浏览器采集、Hermes 自动化仍受现有授权闸门控制。
