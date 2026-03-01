# CS2 Update Watcher

监听 Counter-Strike 2 的代码变更和官方更新公告，第一时间通过邮件/电话通知你。

## 数据源

| 数据源 | 说明 | 延迟 |
|--------|------|------|
| [SteamDatabase/GameTracking-CS2](https://github.com/SteamDatabase/GameTracking-CS2) | 自动追踪 CS2 游戏文件变更的 GitHub 仓库，能感知到代码级的改动 | ~分钟级 |
| [Steam ISteamNews API](https://partner.steamgames.com/doc/webapi/ISteamNews) | Valve 官方发布的更新公告和补丁说明 | 官方发布后即可获取 |

## 通知渠道

- **邮件 (SMTP)** — 包含完整的变更文件列表和更新摘要，支持 HTML 格式
- **电话 (Twilio)** — 可选，通过 TTS 朗读更新摘要，适合需要即时响应的场景

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

所有配置通过 `.env` 文件或环境变量设置，参考 `.env.example`。

### 必须配置

- `SMTP_*` + `NOTIFY_EMAIL` — 邮件通知（推荐至少配这个）

### 推荐配置

- `GITHUB_TOKEN` — GitHub Personal Access Token，不需要勾选任何权限。不配也能用，但未认证的 API 每小时只有 60 次请求限额，配了有 5000 次。

### 可选配置

- `STEAM_API_KEY` — Steam Web API Key
- `TWILIO_*` — Twilio 电话通知
- `POLL_INTERVAL_SECONDS` — 轮询间隔，默认 60 秒

## 后台运行

```bash
# 使用 nohup
nohup python main.py > watcher.log 2>&1 &

# 或使用 systemd (Linux)
# 参考下方 systemd 配置

# 或使用 screen/tmux
screen -S cs2-watcher
python main.py
# Ctrl+A D 分离
```

### systemd 配置示例

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

## 架构

```
main.py                 # 主调度器，轮询循环
├── github_watcher.py   # GitHub commit 监听
├── steam_news_watcher.py # Steam 新闻监听
├── formatter.py        # 格式化通知内容
├── notifier.py         # 通知发送 (邮件/电话)
├── state.py            # 状态持久化
└── config.py           # 配置管理
```
