# Augur · 识机

> 足球比赛智能预测系统 — 面向国内市场的 AI 驱动足球结果预测平台

## 项目简介

Augur（识机）是一个针对国内足球赛事（中超、中甲、亚冠、世界杯亚预赛等）的机器学习预测系统，结合学术界最新研究成果与工程实践，提供胜平负概率、进球数预测及价值投注提示。

> Augur，古罗马占卜师，通过观察自然规律预判未来。识机，识别时机，在变化发生前洞察先机。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置数据库

```bash
# 创建数据库
createdb augur

# 设置环境变量
export DATABASE_URL="postgresql://localhost:5432/augur"
```

### 3. 获取数据并训练模型

```bash
cd src
python main.py
```

这会：
1. 从 FBref 抓取欧洲五大联赛历史数据（最近 5 个赛季）
2. 计算 Pi-Ratings 和特征
3. 训练 CatBoost baseline 模型
4. 保存模型到 `models/catboost_baseline.cbm`

## 项目结构

```
augur/
├── src/
│   ├── data/
│   │   ├── schema.py       # 数据模型定义
│   │   ├── database.py     # PostgreSQL 操作
│   │   └── __init__.py
│   ├── adapters/
│   │   ├── base.py              # 适配器基类
│   │   ├── soccerdata_adapter.py # SoccerData 适配器
│   │   └── __init__.py
│   ├── models/
│   │   ├── predictor.py         # 模型预测器
│   │   ├── feature_engineer.py  # 特征工程
│   │   └── __init__.py
│   ├── api/                     # FastAPI 接口 (TODO)
│   └── main.py                  # 主入口
├── models/                      # 训练好的模型
├── docs/                        # 文档
└── requirements.txt
```

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
- [系统架构设计](docs/design/system-architecture.md) — 完整系统架构

## 技术栈概览

| 层级 | 选型 |
|------|------|
| 数据采集 | Python + SoccerData / 爬虫 |
| 数据存储 | PostgreSQL |
| 特征工程 | 自定义 Pi-Ratings + 近期状态 |
| 模型训练 | CatBoost + scikit-learn |
| 后端 API | FastAPI (TODO) |
| 前端 | Next.js / 微信小程序 (TODO) |
| 部署 | Docker + 云服务器 (TODO) |

## 项目状态

- [x] 项目框架搭建
- [x] 数据适配器（SoccerData）
- [x] PostgreSQL 数据存储
- [x] 特征工程（Pi-Ratings）
- [ ] 历史数据入库
- [ ] baseline 模型训练
- [ ] 回测框架
- [ ] 球探网赔率爬虫
- [ ] Web 界面 MVP
- [ ] 微信小程序

## 参考资源

- [arXiv:2403.07669](https://arxiv.org/abs/2403.07669) — ML for Soccer Match Result Prediction (2024 综述)
- [arXiv:2309.14807](https://arxiv.org/abs/2309.14807) — CatBoost + pi-ratings benchmark
- [lucasmaystre/kickscore](https://github.com/lucasmaystre/kickscore) — Bayesian 动态评分引擎
- [Mg30/footixify](https://github.com/Mg30/footixify) — 开源预测 Web app
- [fivethirtyeight/data](https://github.com/fivethirtyeight/data/tree/master/soccer-spi) — SPI 评分体系
- [soccerdata](https://github.com/probberechts/soccerdata) — 足球数据爬虫封装
