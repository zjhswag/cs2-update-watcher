# CS2 Update Watcher

监听 Counter-Strike 2 官方更新公告，第一时间通过邮件、Bark 推送、电话通知你。

支持 DeepSeek 自动翻译英文更新日志为中文，中英文一起发送。

## 数据源

| 数据源 | 说明 |
|--------|------|
| [Steam ISteamNews API](https://partner.steamgames.com/doc/webapi/ISteamNews) | Valve 官方发布的更新公告和补丁说明 |

## 通知渠道

| 渠道 | 说明 | 开关 |
|------|------|------|
| **邮件 (SMTP)** | 完整更新内容 + 中文翻译，HTML 格式 | `ENABLE_EMAIL=true` |
| **Bark 推送 (iOS)** | iPhone 强提醒，支持 critical 级别持续响铃 | `ENABLE_BARK=true` |
| **阿里云语音电话** | 直接打电话到手机，TTS 朗读更新摘要 | `ENABLE_PHONE=true` |

## 额外功能

- **DeepSeek 翻译** — 自动将英文更新日志翻译为中文，邮件中英文原文 + 翻译一起发送
- **每日心跳** — 每天中午 12:00 (CST) 自动发邮件确认程序运行正常
- **状态持久化** — 重启后不会重复通知，断点续跑

## 快速开始

```bash
# 1. 克隆 / 进入项目目录
cd cs2-update-watcher

# 2. 创建虚拟环境
python3 -m venv .venv && source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的配置

# 5. 运行
python main.py
```

## 配置说明

所有配置通过 `.env` 文件或环境变量设置。

### 必须配置

| 配置项 | 说明 |
|--------|------|
| `SMTP_HOST` | SMTP 服务器（默认 `smtp.qq.com`） |
| `SMTP_PORT` | SMTP 端口（默认 `465`，QQ 邮箱 SSL） |
| `SMTP_USER` | 发件邮箱地址 |
| `SMTP_PASSWORD` | 邮箱授权码（QQ 邮箱需开启 POP3/SMTP 服务获取） |
| `NOTIFY_EMAIL` | 收件邮箱地址 |

### 推荐配置

| 配置项 | 说明 |
|--------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key，用于翻译更新日志 |
| `STEAM_API_KEY` | Steam Web API Key（可选，不配也能用） |

### Bark 推送（iOS）

| 配置项 | 说明 |
|--------|------|
| `ENABLE_BARK` | 开关（`true` / `false`） |
| `BARK_URL` | Bark 推送地址（如 `https://api.day.app/你的Key`） |
| `BARK_SOUND` | 铃声（默认 `alarm`） |

在 App Store 下载 [Bark](https://apps.apple.com/app/bark/id1403753865)，打开后复制推送地址即可。

### 阿里云语音电话（可选）

| 配置项 | 说明 |
|--------|------|
| `ENABLE_PHONE` | 开关（`true` / `false`） |
| `ALIYUN_ACCESS_KEY_ID` | 阿里云 AccessKey ID |
| `ALIYUN_ACCESS_KEY_SECRET` | 阿里云 AccessKey Secret |
| `ALIYUN_TTS_CODE` | 语音通知模板 ID |
| `ALIYUN_CALLED_NUMBER` | 被叫手机号 |
| `ALIYUN_SHOW_NUMBER` | 显示号码（可选） |

### 其他

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `POLL_INTERVAL_SECONDS` | 轮询间隔（秒） | `60` |
| `STATE_FILE` | 状态文件路径 | `watcher_state.json` |

## 后台运行

```bash
# 使用 nohup
nohup python main.py > watcher.log 2>&1 &

# 或使用 screen/tmux
screen -S cs2-watcher
python main.py
# Ctrl+A D 分离
```

### systemd 配置示例（Linux）

```ini
[Unit]
Description=CS2 Update Watcher
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/cs2-update-watcher
ExecStart=/path/to/cs2-update-watcher/.venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## 项目结构

```
cs2-update-watcher/
├── main.py                 # 主调度器，轮询循环 + 每日心跳
├── config.py               # 配置管理（从 .env 读取）
├── state.py                # 状态持久化（防止重启重复通知）
├── steam_news_watcher.py   # Steam ISteamNews API 监听
├── formatter.py            # 格式化通知内容（文本/HTML/BBCode 转换）
├── translator.py           # DeepSeek API 翻译（英→中）
├── notifier.py             # 通知发送（邮件/Bark/阿里云电话）
├── test_send_news.py       # 测试脚本：拉取最新新闻并发邮件
├── test_steam_news.py      # 测试脚本：Steam 新闻 API 调试
├── requirements.txt        # Python 依赖
└── .env                    # 环境变量配置（不提交）
```

## 数据流

```
main.py（每 60 秒轮询）
    │
    ├─► steam_news_watcher.check_for_news()  → 检测新公告
    │
    ├─► formatter.format_*()                  → 格式化（英文原文 + 中文翻译）
    │       └─► translator.translate_to_chinese()  → DeepSeek 翻译
    │
    ├─► notifier.notify_all()                 → 邮件 + Bark + 电话
    │
    ├─► state.save_state()                    → 持久化 last_gid
    │
    └─► _check_heartbeat()                    → 每天 12:00 心跳邮件
```
