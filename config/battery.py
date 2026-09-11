# -*- coding: utf-8 -*-
"""
电池行业 - 分类与搜索词配置
REPORT_TITLE 为行业基名，最终标题由 main 按周期拼成「…日报 / …周报」
"""

REPORT_TITLE = "电池行业"
REPORT_EMOJI = "🔋"

# ── Google Alerts 邮件过滤 ──
# 只处理邮件标题中包含以下关键词的 Alert 邮件
ALERT_SUBJECTS = [
    "碳酸锂",
    "锂矿",
    "钴矿",
    "镍矿",
    "正极材料",
    "磷酸铁锂",
    "负极材料",
    "硅碳",
    "电解液",
    "隔膜",
    "锂电设备",
    "固态电池",
    "钠离子电池",
    "能量密度",
    "快充",
    "BMS",
    "CTP",
    "CTC",
    "CTB",
    "新能源汽车",
    "超充桩",
    "换电站",
    "储能电站",
    "户用储能",
    "工商业储能",
    "电池回收",
    "宁德时代",
    "比亚迪",
    "电池企业",
    "电池 政策",
    "欧盟电池法",
    "电池行业",
]

CATEGORIES = [
    # ── 上游 ──
    {
        "id":      "resource",
        "name":    "上游资源",
        "emoji":   "⛏️",
        "color":   "#c4a35a",
        "queries": [
            "碳酸锂 氢氧化锂 价格 走势",
            "锂矿 钴矿 镍矿 开采 最新",
            "锰矿 磷矿 石墨矿 电池级",
        ],
    },
    {
        "id":      "material",
        "name":    "四大主材",
        "emoji":   "🧪",
        "color":   "#00d4ff",
        "queries": [
            "正极材料 磷酸铁锂 三元 锰铁锂 最新",
            "负极材料 石墨 硅碳 硬碳 最新",
            "电解液 锂盐 LiFSI 添加剂 溶剂",
            "隔膜 湿法 干法 涂覆膜 最新",
        ],
    },
    {
        "id":      "auxiliary",
        "name":    "辅材与设备",
        "emoji":   "⚙️",
        "color":   "#8a9aae",
        "queries": [
            "铜箔 铝箔 集流体 PVDF 导电剂",
            "锂电设备 涂布机 卷绕 叠片 分容化成",
        ],
    },
    # ── 中游 ──
    {
        "id":      "cell_tech",
        "name":    "电芯与技术路线",
        "emoji":   "🔋",
        "color":   "#00ff88",
        "queries": [
            "固态电池 半固态电池 最新进展",
            "钠离子电池 量产 进展",
            "磷酸铁锂 三元锂 刀片电池 最新",
            "4680电池 大圆柱 方形 软包 技术",
            "电池能量密度 快充技术 安全 突破",
        ],
    },
    {
        "id":      "pack_system",
        "name":    "Pack与系统集成",
        "emoji":   "📐",
        "color":   "#b47fff",
        "queries": [
            "电池包 BMS 电池管理 热管理 最新",
            "CTP CTC CTB 电池集成 技术",
        ],
    },
    # ── 下游 ──
    {
        "id":      "ev_app",
        "name":    "车端应用",
        "emoji":   "🚗",
        "color":   "#ff6b35",
        "queries": [
            "新能源汽车 电池 装车量 最新",
            "换电站 超充桩 充电桩 补能",
            "混动 增程 纯电 电池需求",
        ],
    },
    {
        "id":      "storage",
        "name":    "储能应用",
        "emoji":   "🏭",
        "color":   "#ffd700",
        "queries": [
            "储能电站 工商业储能 招标 最新",
            "户用储能 便携电源 光储",
            "电网侧储能 调峰 调频 项目",
        ],
    },
    # ── 回收 ──
    {
        "id":      "recycle",
        "name":    "回收与梯次利用",
        "emoji":   "♻️",
        "color":   "#66cc99",
        "queries": [
            "电池回收 拆解 再生利用 最新",
            "梯次利用 退役电池 镍钴锰锂回收",
        ],
    },
    # ── 企业/资本 ──
    {
        "id":      "company",
        "name":    "企业与资本",
        "emoji":   "📊",
        "color":   "#ff9999",
        "queries": [
            "宁德时代 比亚迪 电池 最新动态",
            "亿纬锂能 中创新航 国轩高科 蜂巢能源",
            "LG新能源 三星SDI 松下 SK 电池",
            "电池企业 融资 上市 收购 扩产",
        ],
    },
    # ── 政策 ──
    {
        "id":      "policy",
        "name":    "政策法规",
        "emoji":   "⚖️",
        "color":   "#ffaa44",
        "queries": [
            "电池 政策 补贴 白名单 最新",
            "欧盟电池法 碳足迹 电池护照",
            "电池回收 管理办法 国标 强制检测",
        ],
    },
    # ── 市场 ──
    {
        "id":      "market",
        "name":    "市场与前瞻",
        "emoji":   "🔮",
        "color":   "#99ffcc",
        "queries": [
            "电池行业 出货量 排名 数据",
            "电池 技术路线 预测 趋势",
            "电池 传闻 新品 路线图",
        ],
    },
]

# ═══════════════════════════════════════════════════
#  数据源配置（见 src/sources/）
# ═══════════════════════════════════════════════════
# 启用哪些数据源。可选：gmail / rss / search
# 优先级：--sources 参数 > 环境变量 SOURCES > 此处配置 > 默认 ["gmail"]
#
# 建议：Gmail 可用时用 ["gmail", "rss"] 双源互补；
#       Gmail 不可用（无法访问 Google / 地区限制 / 不想配 Google Alerts）时改为 ["rss"]。
SOURCES = ["gmail"]

# ── RSS 订阅源（SOURCES 含 "rss" 时生效，纯标准库抓取，无需 API key）──
RSS_FEEDS = [
    # 国内
    {"name": "36氪快讯",             "url": "https://www.36kr.com/feed-newsflash",       "region": "cn"},
    {"name": "IT之家",               "url": "https://www.ithome.com/rss/",             "region": "cn"},
    {"name": "钛媒体",               "url": "https://www.tmtpost.com/rss.xml",         "region": "cn"},
    # 海外
    {"name": "electrive",           "url": "https://www.electrive.com/feed/",         "region": "global"},
    {"name": "Electrek",            "url": "https://electrek.co/feed/",               "region": "global"},
    {"name": "CleanTechnica",       "url": "https://cleantechnica.com/feed/",         "region": "global"},
    {"name": "Energy-Storage.news", "url": "https://www.energy-storage.news/feed/",   "region": "global"},
]

# ── 搜索源检索式（SOURCES 含 "search" 时生效）──
# 留空则自动取 CATEGORIES 里前 3 个分类的首个关键词兜底。
# 需要同时配置：SEARCH_PROVIDER / SEARCH_API_URL（或 TAVILY_API_KEY）
SEARCH_QUERIES = [
    "锂电池 行业 最新消息",
    "储能 项目 中标 最新",
    "动力电池 装车量 最新",
]
