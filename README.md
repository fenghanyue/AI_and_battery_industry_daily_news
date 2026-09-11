# 行业日报/周报自动生成系统

自动抓取多源新闻（Google Alerts / RSS / 搜索 API）、AI 摘要筛选、生成 HTML 日报/周报并发送邮件。支持 AI 行业和电池行业两个独立配置。

> 数据源是可插拔的（见 `src/sources/`）：默认只启用 Gmail + Google Alerts，行为与旧版一致；
> 无法访问 Google 的环境可以改用 RSS 源，不配 Gmail 也能跑。

## 工作原理

```
GitHub Actions 定时触发（日报每天 8 点 / 周报每周一 8 点，北京时间）
  └→ 逐个数据源抓取（SOURCES 指定，单个源失败自动跳过）
     ├─ gmail  ：读取 Gmail 中的 Google Alerts 邮件（IMAP）
     ├─ rss    ：聚合多源 RSS/Atom（纯标准库，无需 API key）
     └─ search ：按检索式调搜索 API 兜底
        └→ 合并 + 跨源去重（链接 + 标题归一化）
           └→ 按关键词分配到各分类
              └→ 调用豆包 AI 筛选，每分类保留 3-5 条最值得关注的
                 └→ 生成暗黑主题 HTML 报告（交互式、可展开）
                    └→ SMTP 发送邮件（正文 + HTML 附件）
```

## 快速开始

### 0. 选择数据源（可选）

数据源层是可插拔的，默认只用 Gmail + Google Alerts（与旧版一致）。

- **Gmail 可用**：无需改动，或设 `SOURCES=gmail,rss` 让 RSS 一起补充时效性。
- **无法访问 Google（国内网络 / 企业网络 / 不想配 Google Alerts）**：设 `SOURCES=rss`，下面的第 1 步和第 2 步中的 Gmail 变量都可以跳过。

```bash
# 只看有哪些源可用
python main.py --profile battery --period daily --sources rss --dry-run
```

可用源：`gmail` / `rss` / `search`（自定义方式见文末「数据源层」）。

### 1. 配置 Google Alerts

在 [google.com/alerts](https://www.google.com/alerts) 创建你关注的搜索词提醒，选择接收到 Gmail 邮箱。

搜索词示例（AI 行业）：`大模型`、`AI 产品`、`AI 监管`……

### 2. 配置环境变量

本地运行：在项目根目录创建 `.env` 文件：

```env
SOURCES=gmail                        # 可选：gmail,rss / rss / gmail,rss,search（默认 gmail）
DOUBAO_API_KEY=your_doubao_api_key
DOUBAO_MODEL=doubao-pro-32k          # 或其他豆包模型
GMAIL_ADDRESS=your@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx   # Gmail 应用专用密码，非账号密码
OUTLOOK_EMAIL=your@163.com           # 发件邮箱（163/网易）
OUTLOOK_PASSWORD=your_smtp_password  # SMTP 授权码
RECIPIENT_EMAILS=a@x.com,b@x.com     # 收件人，多个用逗号分隔

# 仅在 SOURCES 含 search 时需要
SEARCH_PROVIDER=tavily               # tavily / generic
SEARCH_API_KEY=your_tavily_key
```

> 用 `SOURCES=rss` 时不需要 GMAIL_* 两个变量；RSS 订阅列表在 `config/<profile>.py` 的 `RSS_FEEDS`。

> **Gmail 应用密码获取**：Google 账户 → 安全性 → 两步验证（先开启）→ 应用专用密码

### 3. 安装依赖

```bash
pip install requests python-dotenv
```

### 4. 运行

```bash
# AI 行业日报（每天，回溯1天）
python main.py --profile ai --period daily

# AI 行业周报（每周，回溯7天）
python main.py --profile ai --period weekly

# 电池行业日报
python main.py --profile battery --period daily

# 改用多源：Gmail + RSS（或只用 RSS，不需要 Gmail）
python main.py --profile battery --period daily --sources gmail,rss
python main.py --profile ai --period daily --sources rss

# 只生成 HTML，不发邮件（测试用）
python main.py --profile ai --period weekly --dry-run

# 用上次缓存数据，跳过邮件抓取（节省时间）
python main.py --profile ai --no-fetch
```

## 自动化部署（GitHub Actions）

### 配置 Secrets

在 GitHub 仓库 → Settings → Secrets and variables → Actions 中添加以下 Secrets：

| Secret 名称 | 说明 |
|-------------|------|
| `DOUBAO_API_KEY` | 豆包 API 密钥 |
| `DOUBAO_MODEL` | 豆包模型名（如 `doubao-pro-32k`） |
| `GMAIL_ADDRESS` | Gmail 地址（用于读取 Alerts） |
| `GMAIL_APP_PASSWORD` | Gmail 应用专用密码 |
| `OUTLOOK_EMAIL` | 发件邮箱地址（163） |
| `OUTLOOK_PASSWORD` | 发件邮箱 SMTP 授权码 |
| `RECIPIENT_EMAILS` | 收件人列表（逗号分隔） |

配置完成后，日报每天、周报每周一北京时间早上 8 点自动运行。也可在 GitHub Actions 页面手动点击 "Run workflow" 触发。

### 查看产物

每次运行后，生成的 HTML 文件会作为 Artifacts 上传，保留 7 天，可在 Actions → 对应运行记录 → Artifacts 下载。

## 目录结构

```
├── .github/workflows/daily.yml    # 日报定时任务（每天）
│   └── weekly.yml                # 周报定时任务（每周一）
├── config/
│   ├── settings.py               # 配置加载器
│   ├── ai.py                     # AI 行业分类配置
│   └── battery.py                # 电池行业分类配置
├── src/
│   ├── sources/                  # 数据源层（可插拔）
│   │   ├── base.py              # Source 基类 + 通用工具（去重/清洗/HTTP）
│   │   ├── gmail_source.py      # Gmail + Google Alerts
│   │   ├── rss_source.py        # 多源 RSS/Atom（纯标准库）
│   │   └── search_source.py     # 搜索 API 兜底
│   ├── gmail_fetcher.py          # Gmail IMAP + Google Alerts 解析
│   ├── news_fetcher.py           # 抓取调度层（多源 -> 去重 -> 分类）
│   ├── ai_summarizer.py          # 豆包 API 筛选摘要
│   ├── html_generator.py         # HTML 报告生成（日报/周报）
│   └── email_sender.py           # SMTP 邮件发送
├── main.py                        # 主程序入口
├── cache/                         # 缓存文件（运行时生成）
├── logs/                          # 日志文件（运行时生成）
└── output/                        # HTML 产物（运行时生成）
```

## 自定义行业配置

以 `config/ai.py` 为参考，修改或新增行业配置：

```python
REPORT_TITLE = "AI 行业"   # 行业基名，日报/周报后缀由程序按 --period 自动拼接

# 只处理邮件标题包含这些词的 Alerts 邮件
ALERT_SUBJECTS = ["大模型", "AI", "GPT", ...]

CATEGORIES = [
    {
        "id":      "model",       # 分类唯一 ID
        "name":    "模型发布",    # 显示名称
        "emoji":   "🚀",
        "color":   "#00d4ff",     # 分类标题颜色（CSS 颜色值）
        "queries": ["大模型 发布", "LLM 开源"],  # 关键词，空格分隔，命中任意一个即归入此分类
    },
    ...
]
```

新增行业后，在 `config/settings.py` 中注册，并在 `main.py` 的 `--profile choices` 中添加即可。

## HTML 报告功能

生成的 HTML 报告具备以下功能（无需服务器，本地浏览器打开即可）：

- **暗黑主题**，移动端自适应
- **分类导航**：顶部标签页，点击滚动定位
- **展开/收起**：点击标题查看完整摘要和来源链接
- **重要度标签**：重要 / 关注 / 一般，由 AI 评级
- **一键复制深度分析提示词**：点击按钮，复制结构化提示词到任意 AI（如 ChatGPT、Claude）进行深度分析

## 数据源层

抓取逻辑与数据来源解耦：每个数据源只需实现 `Source.fetch()`，返回统一结构的文章列表。

```python
# src/sources/base.py 中的统一结构
{
    "title":     "...",        # 标题
    "summary":   "...",        # 摘要片段
    "link":      "...",        # 原文链接（用于去重）
    "source":    "electrive",  # 来源名
    "published": "2026/09/11", # 发布日期
    "raw_date":  "2026/09/11", # 采集日期
}
```

调度在 `src/news_fetcher.fetch_all()`：逐个源抓取，**单个源失败只记日志、不影响其他源**；
全部源都拿不到内容时才抛出异常（保持旧版“配置错要吵”的行为）。

### 内置数据源

| 名称 | 说明 | 需要什么 |
|------|------|----------|
| `gmail` | 读取 Gmail 里的 Google Alerts 邮件 | `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` |
| `rss` | 聚合多源 RSS/Atom，标准库实现 | 无（列表在 `RSS_FEEDS`） |
| `search` | 按检索式调搜索 API 兜底 | `SEARCH_PROVIDER` + API Key |

### 启用与优先级

```
--sources 参数  >  环境变量 SOURCES  >  config/<profile>.py: SOURCES  >  默认 ["gmail"]
```

### 新增一个数据源

1. 继承 `src/sources/base.py` 的 `Source`，实现 `fetch()`；
2. 在 `src/sources/__init__.py` 的 `REGISTRY` 里登记一行。

主流程不用改。

## 常见问题

**Q: Gmail 连接失败？**
检查是否开启了两步验证，并使用应用专用密码（不是 Gmail 账号密码）。

**Q: 豆包 API 调用失败？**
检查 `DOUBAO_API_KEY` 和 `DOUBAO_MODEL` 是否正确。模型名可在火山方舟控制台确认。

**Q: 收不到邮件？**
检查 163 邮箱是否开启了 SMTP 服务，`OUTLOOK_PASSWORD` 填的是 SMTP 授权码而非登录密码。

**Q: 无法访问 Google，整个日报跑不起来？**
改用 RSS 源即可，不需要 Gmail：`SOURCES=rss python main.py --profile battery --period daily`。
RSS 订阅列表在 `config/<profile>.py` 的 `RSS_FEEDS`，可自由增删。

**Q: 某些分类没有内容？**
可能是 Google Alerts 近期没有匹配文章，或 `ALERT_SUBJECTS` 过滤掉了相关邮件。可用 `--no-fetch` 配合缓存调试。
