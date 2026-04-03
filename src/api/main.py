"""
Augur FastAPI 后端
提供比赛预测 API
"""

import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import asyncio
import asyncpg
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup
import numpy as np

# ============ 配置 ============

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://augur:augur@localhost:5432/augur"
)

MODEL_DIR = Path(PROJECT_ROOT) / "models"
MODEL_PATH = str(MODEL_DIR / "catboost_v1.cbm")
FEATURES_PATH = str(MODEL_DIR / "features_v1.json")
PI_RATINGS_PATH = str(MODEL_DIR / "pi_ratings_v1.json")

# ============ Pydantic 模型 ============

class MatchPrediction(BaseModel):
    id: int
    date: str
    league: str
    league_cn: str
    home_team: str
    away_team: str
    home_team_cn: str
    away_team_cn: str
    home_goals: Optional[int]
    away_goals: Optional[int]

    # 赔率
    odds_home: float
    odds_draw: float
    odds_away: float

    # 市场隐含概率
    implied_home: float
    implied_draw: float
    implied_away: float

    # 模型预测
    pred_home: float
    pred_draw: float
    pred_away: float

    # 价值信号
    value_home: float
    value_draw: float
    value_away: float
    has_value: bool

    model_name: str


class PredictResponse(BaseModel):
    matches: List[MatchPrediction]
    fetched_at: str
    source: str


# ============ 数据库 ============

pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return pool


async def close_pool():
    global pool
    if pool:
        await pool.close()
        pool = None


async def fetch_historical_matches(limit: int = 500) -> List[dict]:
    """从数据库获取历史比赛（含结果）用于计算 Pi-Ratings"""
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""
            SELECT date, league, home_team, away_team,
                   home_goals, away_goals, odds_home, odds_draw, odds_away
            FROM matches
            WHERE home_goals IS NOT NULL
            ORDER BY date DESC
            LIMIT $1
        """, limit)
        return [dict(r) for r in rows]


# ============ Pi-Ratings + 特征工程（与 train.py 一致）============

def compute_pi_ratings(matches: List[dict], init: float = 0.0) -> dict:
    """
    计算 Pi-Ratings（与 train.py 完全一致的算法）
    """
    from collections import defaultdict
    ratings = defaultdict(lambda: {'attack': 0.0, 'defense': 0.0})
    k = 0.05
    home_advantage = 0.25

    sorted_matches = sorted(matches, key=lambda x: x['date'])

    for match in sorted_matches:
        if match['home_goals'] is None:
            continue

        home = match['home_team']
        away = match['away_team']
        hg = float(match['home_goals'])
        ag = float(match['away_goals'])

        expected_home = ratings[home]['attack'] + home_advantage - ratings[away]['defense']
        expected_away = ratings[away]['attack'] - ratings[home]['defense']

        err_home = hg - expected_home
        err_away = ag - expected_away

        ratings[home]['attack'] += k * err_home
        ratings[away]['attack'] += k * err_away
        ratings[home]['defense'] -= k * err_away
        ratings[away]['defense'] -= k * err_home

    return dict(ratings)


def _recent_form(team: str, all_matches: List[dict],
                 match_date, n: int = 5):
    """主/客队近5场战绩"""
    team_matches = [
        m for m in all_matches
        if (m['home_team'] == team or m['away_team'] == team)
        and m['home_goals'] is not None
        and m['date'] < match_date
    ]
    team_matches.sort(key=lambda x: x['date'], reverse=True)
    recent = team_matches[:n]

    if not recent:
        return 0.33, 1.0, 1.0, 1.0

    wins = draws = goals_s = goals_c = 0
    for m in recent:
        is_home = m['home_team'] == team
        tg = m['home_goals'] if is_home else m['away_goals']
        og = m['away_goals'] if is_home else m['home_goals']
        goals_s += tg
        goals_c += og
        if tg > og:
            wins += 1
        elif tg == og:
            draws += 1

    total = len(recent)
    return (
        wins / total,
        goals_s / total,
        goals_c / total,
        (wins * 3 + draws) / total,
    )


def _h2h(home_team: str, away_team: str, all_matches: List[dict], match_date, n: int = 10):
    """两队历史交锋"""
    h2h_ms = [
        m for m in all_matches
        if {m['home_team'], m['away_team']} == {home_team, away_team}
        and m['home_goals'] is not None
        and m['date'] < match_date
    ]
    h2h_ms.sort(key=lambda x: x['date'], reverse=True)
    recent = h2h_ms[:n]

    if not recent:
        return 0.33, 0.0, 2.5

    hw = sum(1 for m in recent if m['home_goals'] > m['away_goals'])
    dr = sum(1 for m in recent if m['home_goals'] == m['away_goals'])
    gl = sum(m['home_goals'] + m['away_goals'] for m in recent) / len(recent)
    return (hw + dr * 0.5) / len(recent), dr / len(recent), gl


def build_features(match: dict, all_matches: List[dict]) -> dict:
    """
    构建完整特征向量（与 train.py build_features 完全一致）
    """
    home = match['home_team']
    away = match['away_team']
    # 确保是 datetime 对象用于比较
    if isinstance(match['date'], str):
        match_dt = datetime.fromisoformat(match['date'].replace('Z', '+00:00'))
    else:
        match_dt = match['date']

    # Pi-Ratings
    hr = pi_ratings_cache.get(home, {'attack': 0.0, 'defense': 0.0})
    ar = pi_ratings_cache.get(away, {'attack': 0.0, 'defense': 0.0})

    pi_diff = (hr['attack'] - ar['defense']) - (ar['attack'] - hr['defense'])

    hw, hs, hc, hp = _recent_form(home, all_matches, match_dt)
    aw, a_s, a_c, ap = _recent_form(away, all_matches, match_dt)
    h2h_rate, h2h_draw, h2h_goals = _h2h(home, away, all_matches, match_dt)

    return {
        'pi_attack_home': hr['attack'],
        'pi_defense_home': hr['defense'],
        'pi_attack_away': ar['attack'],
        'pi_defense_away': ar['defense'],
        'pi_diff': pi_diff,
        'home_advantage': 0.25,
        'league': hash(match.get('league', '')) % 1000,
        'win_rate_home_5': hw,
        'goals_scored_home_5': hs,
        'goals_conceded_home_5': hc,
        'points_home_5': hp,
        'win_rate_away_5': aw,
        'goals_scored_away_5': a_s,
        'goals_conceded_away_5': a_c,
        'points_away_5': ap,
        'h2h_win_rate': h2h_rate,
        'h2h_draw_rate': h2h_draw,
        'h2h_avg_goals': h2h_goals,
    }


# ============ 球队别名映射 ============

# 常见中文 → 英文映射（500.com 专用）
# 完整映射表应存 team_aliases 表，这里放内存缓存用于快速查找
CHINESE_TO_ENGLISH = {
    # 英超 — 对应数据库名
    '阿森纳': 'Arsenal', '阿仙奴': 'Arsenal',
    '切尔西': 'Chelsea', '曼联': 'Man United', '曼城': 'Man City',
    '利物浦': 'Liverpool', '热刺': 'Tottenham', '纽卡斯尔': 'Newcastle',
    '阿斯顿维拉': 'Aston Villa', '西汉姆': 'West Ham', '狼队': 'Wolverhampton',
    '布莱顿': 'Brighton Hove', '水晶宫': 'Crystal Palace', '富勒姆': 'Fulham',
    '布伦特福德': 'Brentford', '伯恩利': 'Burnley', '埃弗顿': 'Everton',
    '伯恩茅斯': 'Bournemouth', '诺丁汉': 'Nottingham', '莱斯特': 'Leicester City',
    # 英冠 — 对应数据库名
    '米堡': 'Middlesbrough', '米尔沃尔': 'Millwall',
    '伯明翰': 'Birmingham', '布莱克本': 'Blackburn',
    '女王巡游': 'QPR', '沃特福德': 'Watford',
    '诺维奇': 'Norwich', '朴次茅斯': 'Portsmouth',
    '西布罗姆': 'West Brom', '雷克斯': 'Luton Town',
    '考文垂': 'Coventry City', '德比郡': 'Derby County',
    '谢菲尔德联': 'Sheffield Utd', '谢菲尔德周三': 'Sheffield Wed',
    '斯旺西': 'Swansea', '桑德兰': 'Sunderland', '斯托克': 'Stoke',
    '普利茅斯': 'Plymouth Arg', '普雷斯顿': 'Preston NE',
    '卡迪夫': 'Cardiff', '布里斯托城': 'Bristol City', '查尔顿': 'Charlton',
    '赫尔城': 'Hull City', '伊普斯维奇': 'Ipswich Town', '利兹联': 'Leeds United',
    '莱斯特城': 'Leicester City', '牛津联': 'Oxford United', '雷克瑟姆': 'Wrexham',
    '南安普顿': 'Southampton',
    # 英甲
    '维冈': 'Wigan Athletic', '莱顿东方': 'Leyton Orient',
    # 欧冠/欧联（补充非五大联赛球队）
    '皇马': 'Real Madrid', '巴萨': 'Barça',
    # 西甲 — 对应数据库名
    '巴列卡诺': 'Rayo Vallecano', '埃尔切': 'Elche',
    '塞维利亚': 'Sevilla FC', '毕尔巴鄂': 'Athletic', '皇家社会': 'Real Sociedad',
    '贝蒂斯': 'Real Betis', '瓦伦西亚': 'Valencia', '比利亚雷亚尔': 'Villarreal',
    '马德里竞技': 'Atleti', '赫罗纳': 'Girona', '奥萨苏纳': 'Osasuna',
    '赫塔费': 'Getafe', '西班牙人': 'Espanyol', '阿拉维斯': 'Alavés',
    '塞尔塔': 'Celta', '马洛卡': 'Mallorca', '莱加内斯': 'Leganés',
    '巴拉多利德': 'Valladolid', '拉斯帕尔马斯': 'Las Palmas',
    # 意甲 — 对应数据库名
    '亚特兰大': 'Atalanta', '国际米兰': 'Inter', '尤文图斯': 'Juventus',
    '那不勒斯': 'Napoli', '罗马': 'Roma', '拉齐奥': 'Lazio',
    '佛罗伦萨': 'Fiorentina', '米兰': 'Milan', '都灵': 'Torino',
    '博洛尼亚': 'Bologna', '热那亚': 'Genoa', '乌迪内斯': 'Udinese',
    '萨索洛': 'Sassuolo', '莱切': 'Lecce', '卡利亚里': 'Cagliari',
    '帕尔马': 'Parma', '维罗纳': 'Verona', '科莫': 'Como 1907',
    '蒙扎': 'Monza', '威尼斯': 'Venezia',
    # 德甲 — 对应数据库名
    '拜仁': 'Bayern', '多特蒙德': 'Dortmund', '莱比锡': 'RB Leipzig',
    '勒沃库森': 'Leverkusen', '法兰克福': 'Frankfurt', '弗莱堡': 'Freiburg',
    '霍芬海姆': 'Hoffenheim', '门兴': "M'gladbach", '沃尔夫斯堡': 'Wolfsburg',
    '斯图加特': 'Stuttgart', '柏林联合': 'Union Berlin', '美因茨': 'Mainz',
    '奥格斯堡': 'Augsburg', '不来梅': 'Bremen', '科隆': '1. FC Köln',
    '海登海姆': 'Heidenheim', '圣保利': 'St. Pauli', '汉堡': 'HSV',
    # 法甲 — 对应数据库名
    '巴黎圣曼': 'PSG', '图卢兹': 'Toulouse', '里尔': 'Lille',
    '里昂': 'Olympique Lyon', '马赛': 'Marseille', '摩纳哥': 'Monaco',
    '朗斯': 'RC Lens', '雷恩': 'Stade Rennais', '尼斯': 'Nice',
    '南特': 'Nantes', '布雷斯特': 'Brest', '斯特拉斯堡': 'Strasbourg',
    '昂热': 'Angers SCO', '勒阿弗尔': 'Le Havre', '欧塞尔': 'Auxerre',
    '圣旺红星': 'Red Star',
    # 法乙
    '拉瓦勒': 'Laval',
    # 葡超 — 对应数据库名
    '里斯本竞技': 'Sporting CP', '圣克拉拉': 'Santa Clara',
    '本菲卡': 'SL Benfica', '波尔图': 'Porto', '布拉加': 'Braga',
    '吉尔维森特': 'Gil Vicente', '阿罗卡': 'Arouca', '法马利康': 'Famalicão',
    '维多利亚': 'Vitória SC', '里奥阿维': 'Rio Ave', '卡萨皮亚': 'Casa Pia',
    # 荷甲 — 对应数据库名
    '阿贾克斯': 'Ajax', '费耶诺德': 'Feyenoord', '埃因霍温': 'PSV',
    '阿尔克马尔': 'AZ', '特温特': 'Twente', '乌得勒支': 'Utrecht',
    '海伦芬': 'Heerenveen', '斯巴达': 'Sparta', '格罗宁根': 'Groningen',
    # 澳超
    '阿德莱德': 'Adelaide United', '奥克兰FC': 'Auckland FC',
    # 沙特
    '吉达联合': 'Al-Ittihad', '拉斯决心': 'Al-Riyadh',
}


def normalize_team_name(name: str) -> str:
    """规范化球队名：优先用英文名，没有则原样返回"""
    return CHINESE_TO_ENGLISH.get(name.strip(), name.strip())


# 英文 → 中文反向映射
ENGLISH_TO_CHINESE = {v: k for k, v in CHINESE_TO_ENGLISH.items()}

def to_chinese_name(name: str) -> str:
    return ENGLISH_TO_CHINESE.get(name.strip(), name.strip())


# ============ 500.com 爬虫 ============

async def scrape_fivehundred(target_date: date) -> List[dict]:
    """爬取 500.com 当日比赛 + 赔率"""
    url = f"https://trade.500.com/jczq/?playid=312&g=2&date={target_date.strftime('%Y-%m-%d')}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': 'https://trade.500.com/',
        })
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, 'html.parser')
    rows = soup.find_all('tr', class_='bet-tb-tr')

    LEAGUE_NAMES = {
        'PL': 'Premier League', 'ELC': 'Championship', 'EL1': 'League One',
        'ESP1': 'La Liga', 'ESP2': 'La Liga 2', 'ITA1': 'Serie A', 'ITA2': 'Serie B',
        'GER1': 'Bundesliga', 'GER2': '2. Bundesliga', 'FRA1': 'Ligue 1', 'FRA2': 'Ligue 2',
        'POR1': 'Primeira Liga', 'NED1': 'Eredivisie', 'NED2': 'Eerste Divisie',
        'AUS1': 'A-League', 'CL': 'Champions League', 'EL': 'Europa League',
        'SAU1': 'Saudi Pro League', 'BSA': 'Brasileirão',
    }

    matches = []
    for idx, row in enumerate(rows):
        try:
            home = row.get('data-homesxname', '')
            away = row.get('data-awaysxname', '')
            match_date = row.get('data-matchdate', '')
            match_time = row.get('data-matchtime', '')
            league_cn = row.get('data-simpleleague', '')
            match_num = row.get('data-matchnum', '')

            # 规范化球队名（中文 → 英文）
            home_en = normalize_team_name(home)
            away_en = normalize_team_name(away)

            if not home_en or not away_en:
                continue

            odds_cell = row.find('td', class_='td-betbtn')
            if not odds_cell:
                continue

            odds_home = odds_draw = odds_away = None
            nspf_spans = odds_cell.find_all('p', attrs={'data-type': 'nspf'})
            for span in nspf_spans:
                value = span.get('data-value', '')
                sp_str = span.get('data-sp', '')
                try:
                    sp = float(sp_str)
                    if value == '3':
                        odds_home = sp
                    elif value == '1':
                        odds_draw = sp
                    elif value == '0':
                        odds_away = sp
                except (ValueError, TypeError):
                    pass

            if odds_home is None:
                continue

            matches.append({
                'id': idx + 1,
                'home_team': home_en,   # 用英文名
                'away_team': away_en,   # 用英文名
                'home_team_cn': home,   # 保留中文用于显示
                'away_team_cn': away,
                'date': f"{match_date}T{match_time}:00",
                'league_cn': league_cn,
                'match_num': match_num,
                'odds_home': odds_home,
                'odds_draw': odds_draw if odds_draw else (odds_home + odds_away) / 2 * 0.95,
                'odds_away': odds_away,
                'home_goals': None,
                'away_goals': None,
            })
        except Exception as e:
            print(f"Parse error: {e}")
            continue

    return matches


catboost_model = None
feature_names: list = []
pi_ratings_cache: dict = {}


def load_assets():
    """加载模型 + 特征名 + Pi-Ratings（全局缓存）"""
    global catboost_model, feature_names, pi_ratings_cache

    # 加载 Pi-Ratings（训练时保存的）
    if not pi_ratings_cache and os.path.exists(PI_RATINGS_PATH):
        import json
        with open(PI_RATINGS_PATH) as f:
            pi_ratings_cache = json.load(f)
        print(f"Loaded Pi-Ratings for {len(pi_ratings_cache)} teams")

    # 加载特征名
    if not feature_names and os.path.exists(FEATURES_PATH):
        import json
        with open(FEATURES_PATH) as f:
            feature_names = json.load(f)
        print(f"Loaded {len(feature_names)} feature names")

    if catboost_model is not None:
        return catboost_model

    if not os.path.exists(MODEL_PATH):
        print(f"Model not found, using baseline")
        return None

    try:
        from catboost import CatBoostClassifier
        catboost_model = CatBoostClassifier()
        catboost_model.load_model(MODEL_PATH)
        print(f"Loaded CatBoost model: {MODEL_PATH}")
        return catboost_model
    except Exception as e:
        print(f"Failed to load model: {e}")
        return None


def predict_proba(features: dict, match: dict) -> dict:
    """用 CatBoost 模型预测概率"""
    model = load_assets()

    if model is None or not feature_names:
        return _baseline_predict(features)

    try:
        feature_vector = [features.get(k, 0.0) for k in feature_names]
        probs = model.predict_proba([feature_vector])[0]
        return {'home': float(probs[0]), 'draw': float(probs[1]), 'away': float(probs[2])}
    except Exception as e:
        print(f"Model prediction failed: {e}")
        return _baseline_predict(features)


def _baseline_predict(features: dict) -> dict:
    """Pi-Ratings 基线预测（模型不可用时降级）"""
    pi_diff = features.get('pi_diff', 0.0) + 0.25
    raw_home = 1 / (1 + np.exp(-pi_diff))
    draw = max(0.15, min(0.35, 0.25 - abs(pi_diff) * 0.05))
    raw_away = 1 - raw_home - draw
    total = raw_home + draw + raw_away
    return {'home': raw_home / total, 'draw': draw / total, 'away': raw_away / total}


# ============ API 端点 ============

app = FastAPI(
    title="Augur API",
    description="足球价值投注预测 API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    load_assets()
    return {"status": "ok", "model_loaded": catboost_model is not None}


@app.get("/api/predict", response_model=PredictResponse)
async def predict_today():
    """
    获取今日比赛 + 模型预测 + 价值信号
    """
    load_assets()  # 确保模型已加载

    today = date.today()

    # 1. 爬取 500.com 今日比赛
    raw_matches = await scrape_fivehundred(today)

    if not raw_matches:
        return PredictResponse(matches=[], fetched_at=datetime.now().isoformat(), source="fivehundred")

    # 2. 获取历史比赛用于计算特征
    hist_matches = await fetch_historical_matches(limit=500)
    model_name = "catboost_v1" if catboost_model else "pi_baseline"

    # 3. 预测 + Value 信号
    predictions = []

    for m in raw_matches:
        # 赔率 → 隐含概率
        implied_home = 1 / m['odds_home']
        implied_draw = 1 / m['odds_draw']
        implied_away = 1 / m['odds_away']
        total_impl = implied_home + implied_draw + implied_away
        implied_home /= total_impl
        implied_draw /= total_impl
        implied_away /= total_impl

        # 构建特征 + 预测
        features = build_features(m, hist_matches)
        pred = predict_proba(features, m)

        # 价值信号
        value_home = pred['home'] - implied_home
        value_draw = pred['draw'] - implied_draw
        value_away = pred['away'] - implied_away
        has_value = value_home > 0.03 or value_draw > 0.03 or value_away > 0.03

        predictions.append(MatchPrediction(
            id=m['id'],
            date=m['date'],
            league=m.get('league', ''),
            league_cn=m['league_cn'],
            home_team=m['home_team'],
            away_team=m['away_team'],
            home_team_cn=m.get('home_team_cn', m['home_team']),
            away_team_cn=m.get('away_team_cn', m['away_team']),
            home_goals=m['home_goals'],
            away_goals=m['away_goals'],
            odds_home=m['odds_home'],
            odds_draw=m['odds_draw'],
            odds_away=m['odds_away'],
            implied_home=round(implied_home, 4),
            implied_draw=round(implied_draw, 4),
            implied_away=round(implied_away, 4),
            pred_home=round(pred['home'], 4),
            pred_draw=round(pred['draw'], 4),
            pred_away=round(pred['away'], 4),
            value_home=round(value_home, 4),
            value_draw=round(value_draw, 4),
            value_away=round(value_away, 4),
            has_value=has_value,
            model_name=model_name,
        ))

    return PredictResponse(
        matches=predictions,
        fetched_at=datetime.now().isoformat(),
        source="fivehundred"
    )


@app.get("/api/predict/date/{date_str}")
async def predict_by_date(date_str: str):
    """获取指定日期的比赛预测"""
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return {"error": "Invalid date format, use YYYY-MM-DD"}

    load_assets()
    raw_matches = await scrape_fivehundred(target)
    hist_matches = await fetch_historical_matches(limit=500)
    model_name = "catboost_v1" if catboost_model else "pi_baseline"

    predictions = []
    for m in raw_matches:
        implied_home = 1 / m['odds_home']
        implied_draw = 1 / m['odds_draw']
        implied_away = 1 / m['odds_away']
        total_impl = implied_home + implied_draw + implied_away
        implied_home /= total_impl
        implied_draw /= total_impl
        implied_away /= total_impl

        features = build_features(m, hist_matches)
        pred = predict_proba(features, m)

        value_home = pred['home'] - implied_home
        value_draw = pred['draw'] - implied_draw
        value_away = pred['away'] - implied_away

        predictions.append({
            **m,
            'implied': {
                'home': round(implied_home, 4),
                'draw': round(implied_draw, 4),
                'away': round(implied_away, 4),
            },
            'pred': {
                'home': round(pred['home'], 4),
                'draw': round(pred['draw'], 4),
                'away': round(pred['away'], 4),
            },
            'value': {
                'home': round(value_home, 4),
                'draw': round(value_draw, 4),
                'away': round(value_away, 4),
            },
            'model_name': model_name,
        })

    return {
        "date": date_str,
        "matches": predictions,
        "fetched_at": datetime.now().isoformat(),
    }


@app.get("/api/match/{match_id}")
async def match_detail(match_id: int):
    """比赛详情：预测 + 历史交锋 + 近期战绩 + 模型特征"""
    load_assets()
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id, date, league, home_team, away_team,
                   home_goals, away_goals,
                   odds_home, odds_draw, odds_away,
                   odds_asian_home, odds_asian_handicap, odds_asian_away,
                   odds_ou_line, odds_ou_over, odds_ou_under,
                   source, result
            FROM matches WHERE id = $1
        """, match_id)
        if not row:
            return {"error": "not found"}
        m = dict(row)
        m['date'] = m['date'].isoformat()

        m['home_team_cn'] = to_chinese_name(m['home_team'])
        m['away_team_cn'] = to_chinese_name(m['away_team'])

        home = m['home_team']
        away = m['away_team']
        match_dt = datetime.fromisoformat(m['date'])
        h2h_rows = await conn.fetch("""
            SELECT date, home_team, away_team, home_goals, away_goals
            FROM matches
            WHERE ((home_team = $1 AND away_team = $2) OR (home_team = $2 AND away_team = $1))
              AND home_goals IS NOT NULL AND date < $3
            ORDER BY date DESC LIMIT 10
        """, home, away, match_dt)
        h2h_list = [dict(r) for r in h2h_rows]
        for r in h2h_list:
            r['date'] = r['date'].isoformat()
            r['home_team'] = to_chinese_name(r['home_team'])
            r['away_team'] = to_chinese_name(r['away_team'])

        hw = sum(1 for r in h2h_list if r['home_team'] == home and r['home_goals'] > r['away_goals'])
        dr = sum(1 for r in h2h_list if r['home_goals'] == r['away_goals'])
        aw = sum(1 for r in h2h_list if r['home_team'] == away and r['home_goals'] > r['away_goals'])
        avg_goals = sum(r['home_goals'] + r['away_goals'] for r in h2h_list) / len(h2h_list) if h2h_list else 0

        # 近期战绩
        async def recent_form(team: str, n=5):
            rows = await conn.fetch("""
                SELECT date, home_team, away_team, home_goals, away_goals
                FROM matches
                WHERE (home_team = $1 OR away_team = $1)
                  AND home_goals IS NOT NULL AND date < $2
                ORDER BY date DESC LIMIT $3
            """, team, match_dt, n)
            results = []
            for r in rows:
                is_home = r['home_team'] == team
                tg = r['home_goals'] if is_home else r['away_goals']
                og = r['away_goals'] if is_home else r['home_goals']
                opp = r['away_team'] if is_home else r['home_team']
                results.append({
                    'date': r['date'].isoformat(),
                    'opponent': to_chinese_name(opp),
                    'goals_for': tg,
                    'goals_against': og,
                    'result': 'W' if tg > og else ('D' if tg == og else 'L'),
                    'is_home': is_home,
                })
            return results

        home_form = await recent_form(home)
        away_form = await recent_form(away)

        # 模型预测
        hist = await fetch_historical_matches(limit=500)
        features = build_features(m, hist)
        pred = predict_proba(features, m)

        implied_home = implied_draw = implied_away = 1/3
        if m['odds_home'] and m['odds_draw'] and m['odds_away']:
            ih = 1 / m['odds_home']
            id_ = 1 / m['odds_draw']
            ia = 1 / m['odds_away']
            t = ih + id_ + ia
            implied_home, implied_draw, implied_away = ih/t, id_/t, ia/t

        def safe_pi(val, default=1000.0):
            try:
                v = float(val)
                if abs(v) > 9999 or v != v:
                    return default
                return round(v, 1)
            except Exception:
                return default

        home_pi = pi_ratings_cache.get(home, {'attack': 1000, 'defense': 1000})
        away_pi = pi_ratings_cache.get(away, {'attack': 1000, 'defense': 1000})

        return {
            "match": m,
            "prediction": {
                "pred_home": round(pred['home'], 4),
                "pred_draw": round(pred['draw'], 4),
                "pred_away": round(pred['away'], 4),
                "implied_home": round(implied_home, 4),
                "implied_draw": round(implied_draw, 4),
                "implied_away": round(implied_away, 4),
                "value_home": round(pred['home'] - implied_home, 4),
                "value_draw": round(pred['draw'] - implied_draw, 4),
                "value_away": round(pred['away'] - implied_away, 4),
                "model_name": "catboost_v1" if catboost_model else "pi_baseline",
            },
            "features": {
                "pi_attack_home": safe_pi(home_pi['attack']),
                "pi_defense_home": safe_pi(home_pi['defense']),
                "pi_attack_away": safe_pi(away_pi['attack']),
                "pi_defense_away": safe_pi(away_pi['defense']),
                "pi_diff": safe_pi(features.get('pi_diff', 0), 0),
                "win_rate_home_5": round(features.get('win_rate_home_5', 0), 3),
                "win_rate_away_5": round(features.get('win_rate_away_5', 0), 3),
                "goals_scored_home_5": round(features.get('goals_scored_home_5', 0), 2),
                "goals_scored_away_5": round(features.get('goals_scored_away_5', 0), 2),
                "h2h_win_rate": round(features.get('h2h_win_rate', 0), 3),
                "h2h_avg_goals": round(features.get('h2h_avg_goals', 0), 2),
            },
            "h2h": {
                "total": len(h2h_list),
                "home_wins": hw,
                "draws": dr,
                "away_wins": aw,
                "avg_goals": round(avg_goals, 2),
                "recent": h2h_list[:5],
            },
            "home_form": home_form,
            "away_form": away_form,
            "media": None,  # 预留：大模型媒体分析
        }


@app.on_event("startup")
async def startup():
    await get_pool()


@app.on_event("shutdown")
async def shutdown():
    await close_pool()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
