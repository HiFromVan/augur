# AI 功能说明

## 功能概述

Augur 提供了两个 AI 增强功能：

1. **AI 预测说明** - 为每场比赛生成简洁的预测分析（80-120字）
2. **媒体分析** - 基于网络搜索的真实新闻生成赛前分析（250-350字）

## 开关控制

AI 功能默认**关闭**，通过配置文件控制：

### 启用 AI 功能

编辑 `config.py`：

```python
ENABLE_AI_FEATURES = True  # 改为 True
```

### 关闭 AI 功能

编辑 `config.py`：

```python
ENABLE_AI_FEATURES = False  # 改为 False
```

## 架构设计

### 数据流程

```
1. 爬取比赛数据 (定时任务)
   ↓
2. 生成预测结果 (定时任务)
   ↓
3. 生成 AI 分析 (定时任务 - 仅当 ENABLE_AI_FEATURES=True)
   ├─ AI 预测说明
   └─ 媒体分析（搜索真实新闻）
   ↓
4. 缓存到数据库
   ↓
5. 用户访问 (只查询数据库，不触发生成)
```

### 关键特性

- **后台生成**：所有 AI 分析在定时任务中完成，不阻塞用户请求
- **去重机制**：已生成的分析不会重复生成
- **开关控制**：可随时启用/关闭 AI 功能
- **成本控制**：关闭后不会调用 Claude API

## 使用方法

### 手动运行定时任务

```bash
# 确保已设置环境变量
export ANTHROPIC_API_KEY="your-api-key"
export ANTHROPIC_BASE_URL="https://api.anthropic.com"

# 运行 AI 分析生成
python3 src/generate_ai_analysis.py
```

### 设置定时任务（Cron）

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每小时运行一次）
0 * * * * cd /Users/van/work/augur && ANTHROPIC_API_KEY=xxx ANTHROPIC_BASE_URL=xxx python3 src/generate_ai_analysis.py >> /tmp/ai_analysis.log 2>&1
```

## 数据库结构

### matches 表

- `ai_explanation` (TEXT) - AI 预测说明
- `media_analysis` (JSONB) - 媒体分析
  ```json
  {
    "summary": "分析内容...",
    "generated_at": "2026-04-08T10:00:00"
  }
  ```

## API 响应

### GET /api/predict

返回比赛列表，包含 `ai_explanation` 字段

### GET /api/match/{id}

返回比赛详情，包含：
- `prediction.ai_explanation` - AI 预测说明
- `media_analysis` - 媒体分析对象

## 成本估算

基于 Claude API 定价：

- **AI 预测说明**：~200 tokens/场 × $0.003/1K = $0.0006/场
- **媒体分析**：~1500 tokens/场 × $0.003/1K = $0.0045/场
- **总计**：约 $0.005/场

假设每天 50 场比赛：
- 日成本：$0.25
- 月成本：$7.5

## 故障排查

### AI 功能未生成

1. 检查配置：`config.py` 中 `ENABLE_AI_FEATURES = True`
2. 检查环境变量：`ANTHROPIC_API_KEY` 已设置
3. 检查定时任务：是否正常运行
4. 查看日志：`/tmp/ai_analysis.log`

### API 调用失败

- 检查 API 密钥是否有效
- 检查网络连接
- 查看错误日志

## 注意事项

1. **首次运行**：会为所有未来比赛生成分析，可能需要较长时间
2. **API 限流**：注意 Claude API 的速率限制
3. **成本控制**：建议定期检查 API 使用量
4. **数据更新**：媒体分析基于生成时的新闻，不会自动更新
