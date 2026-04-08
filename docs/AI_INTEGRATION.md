# AI 大模型接入指南

## 概述

Augur 使用 Anthropic Claude 3.5 Haiku 模型提供 AI 对话和媒体分析功能。

## 功能列表

### 1. AI 对话助手 ✅ 已实现
- **位置**: 所有页面右下角浮动按钮
- **功能**:
  - 回答足球预测相关问题
  - 解释比赛预测依据
  - 分析球队近期表现
  - 提供投注建议
- **实现文件**:
  - 前端: `web/components/ChatWindow.tsx`
  - 后端: `src/api/main.py` - `/api/chat` 端点

### 2. 批量生成预测说明 ✅ 已实现
- **功能**: 为所有比赛生成 AI 分析说明
- **使用方法**:
  ```bash
  # 设置 API Key
  export ANTHROPIC_API_KEY=sk-ant-xxxxx

  # 生成 10 场比赛的说明
  python3 src/generate_explanations.py 10

  # 重新生成已有说明
  python3 src/generate_explanations.py 10 --regenerate
  ```
- **实现文件**: `src/generate_explanations.py`

### 3. 媒体分析 🚧 待实现
- **功能**: 整合赛前新闻、伤病情况、阵容变化等实时信息
- **数据源**:
  - 新闻 API (如 NewsAPI, Google News)
  - 社交媒体 (Twitter/X)
  - 官方球队公告
- **实现方案**: 见下文

## 配置步骤

### 1. 获取 Anthropic API Key

1. 访问 https://console.anthropic.com/
2. 注册/登录账号
3. 创建 API Key
4. 复制 Key (格式: `sk-ant-xxxxx`)

### 2. 配置环境变量

创建 `.env` 文件:

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API Key:

```bash
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### 3. 重启后端服务

```bash
# 停止当前服务
# 重新启动
python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 测试 AI 对话

1. 打开浏览器访问 http://localhost:3000
2. 点击右下角聊天按钮
3. 输入问题，例如: "这场比赛的预测依据是什么？"

## API 使用说明

### 对话 API

**端点**: `POST /api/chat`

**请求体**:
```json
{
  "message": "这场比赛的预测依据是什么？",
  "match_id": 123,
  "match_context": {
    "homeTeam": "曼城",
    "awayTeam": "利物浦",
    "league": "英超",
    "predHome": 0.45,
    "predDraw": 0.25,
    "predAway": 0.30
  },
  "history": [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！我是AI足球分析师"}
  ]
}
```

**响应**:
```json
{
  "response": "根据我们的 AI 模型分析，这场比赛主队曼城有 45% 的胜率...",
  "sources": null
}
```

### 批量生成说明

**脚本**: `src/generate_explanations.py`

**参数**:
- `limit`: 处理的比赛数量 (默认: 10)
- `--regenerate`: 重新生成已有说明

**示例**:
```bash
# 生成 20 场比赛的说明
python3 src/generate_explanations.py 20

# 重新生成所有比赛的说明
python3 src/generate_explanations.py 100 --regenerate
```

## 媒体分析实现方案

### 方案 1: 新闻 API 集成

**推荐数据源**:
- NewsAPI (https://newsapi.org/) - 免费额度: 100 请求/天
- Google News RSS
- 球队官方 RSS

**实现步骤**:

1. **创建新闻爬虫**:
```python
# src/scrapers/news_scraper.py
import httpx
from bs4 import BeautifulSoup

async def fetch_team_news(team_name: str, days: int = 7):
    """获取球队最近的新闻"""
    # 实现新闻抓取逻辑
    pass
```

2. **添加数据库表**:
```sql
CREATE TABLE match_news (
    id SERIAL PRIMARY KEY,
    match_id INT REFERENCES matches(id),
    title VARCHAR(500),
    content TEXT,
    source VARCHAR(100),
    published_at TIMESTAMP,
    sentiment FLOAT,  -- 情感分析分数
    created_at TIMESTAMP DEFAULT NOW()
);
```

3. **AI 分析端点**:
```python
@app.get("/api/match/{match_id}/media-analysis")
async def get_media_analysis(match_id: int):
    # 获取相关新闻
    news = await fetch_match_news(match_id)

    # 使用 Claude 分析
    analysis = await generate_media_analysis(news)

    return {"analysis": analysis, "sources": news}
```

### 方案 2: 社交媒体情感分析

**数据源**:
- Twitter/X API
- Reddit r/soccer
- 球迷论坛

**实现**:
- 抓取关键词相关推文
- 使用 Claude 进行情感分析
- 生成球迷情绪报告

### 方案 3: 伤病和阵容信息

**数据源**:
- Transfermarkt
- 官方球队网站
- FBref

**实现**:
- 定期爬取伤病名单
- 分析阵容变化影响
- 整合到预测模型

## 成本估算

### Anthropic Claude 3.5 Haiku 定价

- **输入**: $0.80 / 百万 tokens
- **输出**: $4.00 / 百万 tokens

### 使用场景估算

**1. 对话功能**:
- 平均每次对话: ~1000 tokens (输入) + 500 tokens (输出)
- 成本: ~$0.0028 / 次对话
- 1000 次对话: ~$2.80

**2. 批量生成说明**:
- 每场比赛: ~800 tokens (输入) + 300 tokens (输出)
- 成本: ~$0.0018 / 场比赛
- 100 场比赛: ~$0.18

**3. 媒体分析**:
- 每场比赛: ~2000 tokens (输入) + 500 tokens (输出)
- 成本: ~$0.0036 / 场比赛
- 100 场比赛: ~$0.36

**月度估算** (假设 100 用户):
- 对话: 1000 次 × $0.0028 = $2.80
- 说明生成: 500 场 × $0.0018 = $0.90
- 媒体分析: 200 场 × $0.0036 = $0.72
- **总计**: ~$4.50/月

## 优化建议

### 1. 缓存策略
- 缓存生成的说明 (已实现 - 存储在数据库)
- 缓存新闻分析结果 (24小时)
- 减少重复 API 调用

### 2. 批处理
- 使用批量 API 调用
- 非高峰时段生成说明
- 定时任务自动更新

### 3. 降级方案
- API 失败时返回预设模板
- 使用本地模型作为备份
- 限制免费用户的 AI 功能使用次数

## 监控和日志

### 记录 API 使用情况

```python
# 在 main.py 中添加
import logging

logger = logging.getLogger("anthropic_usage")

@app.post("/api/chat")
async def chat(request: ChatRequest):
    start_time = time.time()

    response = anthropic_client.messages.create(...)

    # 记录使用情况
    logger.info(f"Chat API - Input: {response.usage.input_tokens}, "
                f"Output: {response.usage.output_tokens}, "
                f"Time: {time.time() - start_time:.2f}s")

    return {"response": ...}
```

### 设置使用限制

```python
# 添加速率限制
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/chat")
@limiter.limit("10/minute")  # 每分钟最多 10 次
async def chat(request: ChatRequest):
    ...
```

## 下一步计划

- [ ] 实现新闻爬虫和媒体分析
- [ ] 添加 AI 使用统计面板
- [ ] 实现用户级别的 AI 功能限制
- [ ] 优化 prompt 提高分析质量
- [ ] 添加多语言支持
- [ ] 集成更多数据源

## 常见问题

**Q: API Key 安全吗？**
A: API Key 存储在服务器端环境变量中，不会暴露给前端。建议使用 secrets 管理工具。

**Q: 如何限制 AI 功能的使用？**
A: 可以在用户表中添加 `ai_quota` 字段，每次调用时检查并扣减配额。

**Q: 对话历史会保存吗？**
A: 目前不保存。如需保存，可以创建 `chat_history` 表存储对话记录。

**Q: 可以使用其他模型吗？**
A: 可以。修改 `model` 参数即可，例如使用 `claude-3-5-sonnet-20241022` 获得更好的分析质量（但成本更高）。

## 技术支持

如有问题，请查看:
- Anthropic 文档: https://docs.anthropic.com/
- 项目 Issues: https://github.com/your-repo/issues
