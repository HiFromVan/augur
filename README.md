# Augur · 识机

> 足球比赛智能预测系统 — AI 驱动的足球结果预测平台

**线上地址：[https://zooming-cat-production.up.railway.app](https://zooming-cat-production.up.railway.app)**

## 项目简介

Augur（识机）是一个针对国内足球赛事（中超、中甲、亚冠、世界杯亚预赛等）的机器学习预测系统，结合学术界最新研究成果与工程实践，提供胜平负概率、比分预测及 AI 赛事分析。

> Augur，古罗马占卜师，通过观察自然规律预判未来。识机，识别时机，在变化发生前洞察先机。

## 功能

- **胜平负预测**：基于 CatBoost + Pi-Ratings 特征工程，输出主胜/平局/客胜概率
- **比分预测**：泊松回归模型预测进球数
- **AI 赛事分析**：接入 Claude API，生成赛前分析文字
- **历史预测记录**：查看待评估、已命中、未命中的历史预测
- **实力对比**：展示双方 Pi-Ratings 实力差值
- **自动更新**：Scheduler 定时抓取赛程、比分，更新预测

## 技术栈

| 层级 | 选型 |
|------|------|
| 数据采集 | Python + 自定义爬虫（足球数据、球探网） |
| 数据存储 | PostgreSQL |
| 特征工程 | Pi-Ratings + 近期状态 + 赔率隐含概率 |
| 预测模型 | CatBoost（胜平负）+ 泊松回归（比分） |
| AI 分析 | Anthropic Claude API |
| 后端 API | FastAPI |
| 前端 | Next.js + Tailwind CSS |
| 部署 | Railway（后端 + 前端 + 定时任务） |

## 项目结构

```
augur/
├── src/
│   ├── api/
│   │   ├── main.py              # FastAPI 后端入口
│   │   └── score_predictor.py   # 比分预测接口
│   ├── data/
│   │   ├── schema.py            # 数据模型
│   │   ├── database.py          # PostgreSQL 操作
│   │   ├── scraper_zqcf.py      # 足球数据爬虫
│   │   └── scraper_footballdata_co.py
│   ├── models/
│   │   ├── predictor.py         # CatBoost 预测器
│   │   ├── poisson_predictor.py # 泊松比分预测
│   │   └── feature_engineer.py  # 特征工程
│   ├── adapters/                # 数据源适配器
│   ├── scheduler.py             # 定时任务
│   ├── train.py                 # 模型训练
│   └── generate_ai_analysis.py  # AI 分析生成
├── web/                         # Next.js 前端
│   └── app/
│       ├── page.tsx             # 首页（今日赛程）
│       ├── match/               # 比赛详情页
│       ├── history/             # 历史预测页
│       ├── account/             # 用户账户
│       └── pricing/             # 订阅定价
├── models/                      # 训练好的模型文件
├── Dockerfile
├── Dockerfile.scheduler
└── railway.toml
```

## 本地开发

### 1. 安装依赖

```bash
pip install -r requirements.txt
cd web && npm install
```

### 2. 配置环境变量

```bash
export DATABASE_URL="postgresql://localhost:5432/augur"
export ANTHROPIC_API_KEY="your_key"
```

### 3. 启动后端

```bash
uvicorn src.api.main:app --reload
```

### 4. 启动前端

```bash
cd web && npm run dev
```

## 项目状态

- [x] FastAPI 后端
- [x] Next.js 前端
- [x] CatBoost 胜平负预测
- [x] 泊松回归比分预测
- [x] Pi-Ratings 特征工程
- [x] 自动抓取赛程与比分
- [x] 历史预测记录与评估
- [x] AI 赛事分析（Claude）
- [x] 用户账户与订阅系统
- [x] Railway 部署上线

## 文档

- [产品交互设计](docs/design/product-design.md)
- [模型设计方案](docs/design/model-design.md)
- [数据获取策略](docs/design/data-strategy.md)
- [系统架构设计](docs/design/system-architecture.md)

## 参考资源

- [arXiv:2403.07669](https://arxiv.org/abs/2403.07669) — ML for Soccer Match Result Prediction (2024 综述)
- [arXiv:2309.14807](https://arxiv.org/abs/2309.14807) — CatBoost + pi-ratings benchmark
- [lucasmaystre/kickscore](https://github.com/lucasmaystre/kickscore) — Bayesian 动态评分引擎
- [soccerdata](https://github.com/probberechts/soccerdata) — 足球数据爬虫封装

## 许可证

[AGPL-3.0](LICENSE)
