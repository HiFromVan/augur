# Augur · 识机

> 足球比赛智能预测系统 — 面向国内市场的 AI 驱动足球结果预测平台

## 项目简介

Augur（识机）是一个针对国内足球赛事（中超、中甲、亚冠、世界杯亚预赛等）的机器学习预测系统，结合学术界最新研究成果与工程实践，提供胜平负概率、进球数预测及价值投注提示。

> Augur，古罗马占卜师，通过观察自然规律预判未来。识机，识别时机，在变化发生前洞察先机。

## 文档索引

### 调研资料

- [现有平台分析](docs/research/existing-platforms.md) — 国内外已有预测产品对比
- [开源模型盘点](docs/research/open-source-models.md) — 可复用的开源项目与引擎
- [论文观点整理](docs/research/papers-summary.md) — 关键学术论文方法与结论

### 设计文档

- [产品交互设计](docs/design/product-design.md) — UX 形态、用户旅程、界面方向
- [模型设计方案](docs/design/model-design.md) — 特征工程、模型选型、评估指标
- [数据获取策略](docs/design/data-strategy.md) — 数据源、采集方案、更新频率
- [技术选型](docs/design/tech-stack.md) — 前后端、ML 框架、部署方案

## 快速了解

```
国内赛事数据  →  特征工程（pi-ratings + 球队状态 + 联赛特征）
                    ↓
              CatBoost / XGBoost 集成模型
                    ↓
         概率输出 + 与赔率对比 → 价值投注信号
                    ↓
              Web / 小程序 产品界面
```

## 技术栈概览

| 层级 | 选型 |
|------|------|
| 数据采集 | Python + Scrapy / API |
| 特征存储 | PostgreSQL + Redis |
| 模型训练 | CatBoost, XGBoost, scikit-learn |
| 后端 API | FastAPI |
| 前端 | Next.js / 微信小程序 |
| 部署 | Docker + 云服务器 |

## 项目状态

- [ ] 数据源调研与接入
- [ ] 基础特征工程 pipeline
- [ ] baseline 模型（CatBoost + pi-ratings）
- [ ] 回测框架
- [ ] Web 界面 MVP
- [ ] 微信小程序

## 参考资源

- [arXiv:2403.07669](https://arxiv.org/abs/2403.07669) — ML for Soccer Match Result Prediction (2024 综述)
- [arXiv:2309.14807](https://arxiv.org/abs/2309.14807) — CatBoost + pi-ratings benchmark
- [lucasmaystre/kickscore](https://github.com/lucasmaystre/kickscore) — Bayesian 动态评分引擎
- [Mg30/footixify](https://github.com/Mg30/footixify) — 开源预测 Web app
- [fivethirtyeight/data](https://github.com/fivethirtyeight/data/tree/master/soccer-spi) — SPI 评分体系
