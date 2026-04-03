# 足球财富 (zqcf918.com) 数据分析文档

## 概述

足球财富是一个综合性足球数据平台，覆盖全球 200+ 联赛，数据从 2003 年至今。
后端为 Spring Boot + Next.js，数据通过 POST API 返回 JSON，无需登录即可访问。

---

## 已确认可用的 API 接口

### 1. 联赛信息
```
POST /new/zlk/getLeagueInfo
params: leagueId={id}
```
返回字段：`leagueId, leagueName, leagueNameJs, leaguePic, leagueType, teamNum, matchSeasonList`

`matchSeasonList` 包含所有历史赛季：`[{seasonName: "2024-2025", id: 12387}, ...]`

---

### 2. 赛程 + 赔率（核心接口）
```
POST /new/zlk/schedules
params: leagueId={id}&seasonId={id}
```
返回嵌套结构：`stages[] -> rounds[][] -> matches[]`

**比赛字段（对模型最有价值）：**
| 字段 | 含义 | 模型价值 |
|------|------|---------|
| `scheduleId` | 比赛ID | 去重用 |
| `matchTime` | 比赛时间 | 时序特征 |
| `homeTeam/guestTeam` | 主客队名 | 基础 |
| `homeTeamId/guestTeamId` | 球队ID | 关联用 |
| `homeScore/guestScore` | 比分 | 训练标签 |
| `score` | 比分字符串 | 备用 |
| `matchState` | 状态(-1=完场) | 过滤用 |
| `opHome/opPk/opAway` | **胜平负赔率** | ⭐⭐⭐ 极高 |
| `ypHome/ypPk/ypAway` | **亚盘赔率** | ⭐⭐⭐ 极高 |
| `ballBig/ballSmall/ballPk` | **大小球/让球** | ⭐⭐ 高 |
| `roundNum` | 轮次 | 中 |
| `leagueId` | 联赛ID | 分层特征 |

---

### 3. 球队历史赛程（分页）
```
POST /new/zlk/team/getTeamScheduleList
params: teamId={id}&pageSize=100&pageNum=1
```
返回：`{total, list[], pages}` — 曼城有 1475 场历史记录

字段同赛程接口，额外有 `leagueShortName, grouping, neutrality`

---

### 4. 球队未来赛程
```
POST /new/zlk/team/getTeamFourFutureSchedule
params: teamId={id}
```
返回未来 4 场比赛，用于预测当前赛事

---

### 5. 球员信息（SSR）
```
GET /playerDetail?playerId={id}
window.__NEXT_DATA__.props.pageProps
```
返回：
- `playerInfo`: `{nameChs, nameEn, birthday, height, weight, expectedValue, countryCn, feetCn}`
- `transferRecord`: 转会历史
- `teamEffect`: 当前球队、号码、位置

---

### 6. 球队基础信息（SSR）
```
GET /teamDetail?teamId={id}
window.__NEXT_DATA__.props.pageProps.teamInfo
```
返回：`{nameChs, nameEn, areaEn, capacity, foundingDate, coachCn, gymCn}`

---

## 主要联赛 ID 对照表

| leagueId | 联赛 | 赛季数 |
|----------|------|--------|
| 82 | 英格兰超级联赛（英超） | 23 |
| 83 | 英格兰冠军联赛（英冠） | 22 |
| 108 | 意大利甲级联赛（意甲） | 22 |
| 120 | 西班牙甲级联赛（西甲） | 23 |
| 129 | 德国甲级联赛（德甲） | 22 |
| 142 | 法国甲级联赛（法甲） | 22 |
| 46 | 欧洲冠军联赛（欧冠） | 23 |
| 47 | 欧足联欧洲联赛（欧联） | 22 |
| 151 | 葡萄牙超级联赛（葡超） | 22 |
| 168 | 荷兰甲级联赛（荷甲） | 23 |
| 158 | 苏格兰超级联赛 | 23 |
| 175 | 比利时甲级联赛 | 22 |

---

## 数据规模估算

| 联赛 | 赛季数 | 每赛季场数 | 总场数 |
|------|--------|-----------|--------|
| 英超 | 23 | 380 | ~8740 |
| 西甲 | 23 | 380 | ~8740 |
| 意甲 | 22 | 380 | ~8360 |
| 德甲 | 22 | 306 | ~6732 |
| 法甲 | 22 | 380 | ~8360 |
| 欧冠 | 23 | ~125 | ~2875 |
| **合计** | | | **~43800 场** |

---

## 对模型训练的价值分析

### 当前模型缺失的关键数据

1. **历史赔率** — 最重要！赔率隐含了市场对比赛的综合判断（伤病、阵容、主客场等）
   - `opHome/opAway` 胜负赔率 → 转换为隐含概率作为特征
   - `ypHome/ypAway` 亚盘 → 亚盘走势反映资金流向
   - 当前 RPS=0.146，加入赔率特征预计可降至 0.12-0.13

2. **更多历史数据** — 当前只有 5290 场，加入后可达 ~50000 场
   - 更多数据 → Pi-Ratings 更准确 → 模型更稳定

3. **大小球数据** — `ballBig/ballSmall` 可用于预测进球数分布

### 暂未找到的数据
- 积分榜（API 端点未确认）
- 首发阵容（最有价值，暂无）
- 球员出场统计（进球/助攻/黄牌）
- xG 数据（该网站无）

---

## 爬取策略

### 优先级 1：历史比赛 + 赔率
```
for league in [82, 108, 120, 129, 142, 46]:
    for season in all_seasons:
        POST /new/zlk/schedules
        → 存入 matches 表，补充 odds 字段
```

### 优先级 2：球队历史赛程（补缺）
```
for team_id in all_teams:
    POST /new/zlk/team/getTeamScheduleList (分页)
    → 与 matches 表去重合并
```

### 去重策略
- 主键：`(scheduleId)` 或 `(matchTime, homeTeamId, guestTeamId)`
- football-data.org 数据用 `source_match_id` 区分
- zqcf918 数据用 `scheduleId` 区分

---

## 注意事项

- 无需登录，直接 POST 即可
- 建议请求间隔 0.5-1s，避免被限速
- 赔率字段为 `-` 表示无数据（老赛季可能缺失）
- 球队名为中文，需建立中文→英文映射表
