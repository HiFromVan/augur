"""
Augur 定时任务调度器

任务：
- 每 5 分钟：更新实时比分 + 比赛状态
- 每小时：爬取 500.com 赔率，存入 odds_history
- 每小时：运行预测模型，结果存入 prediction_records
- 每天 07:00：重新计算 Pi-Ratings，更新 pi_ratings_v1.json
"""

import asyncio
import asyncpg
import httpx
import json
import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://augur:augur@localhost:5432/augur")
FOOTBALL_DATA_API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")
MODEL_DIR = PROJECT_ROOT / "models"

# ============ 数据库 ============

pool: asyncpg.Pool = None


async def get_pool():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)
    return pool


# ============ 任务1：爬取 500.com 赔率 ============

async def task_scrape_fivehundred():
    """每小时爬取 500.com 今日赛程 + 赔率，存入 odds_history"""
    started = datetime.now()
    print(f"[{started:%H:%M:%S}] 开始爬取 500.com...")

    try:
        from bs4 import BeautifulSoup

        today = date.today()
        url = f"https://trade.500.com/jczq/?playid=312&g=2&date={today}"

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Referer': 'https://trade.500.com/',
            })
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'html.parser')
        rows = soup.find_all('tr', class_='bet-tb-tr')

        p = await get_pool()
        count = 0

        for row in rows:
            try:
                home = row.get('data-homesxname', '')
                away = row.get('data-awaysxname', '')
                match_date = row.get('data-matchdate', '')
                match_time = row.get('data-matchtime', '')
                league_cn = row.get('data-simpleleague', '')
                match_num = row.get('data-matchnum', '')

                if not home or not away:
                    continue

                odds_cell = row.find('td', class_='td-betbtn')
                if not odds_cell:
                    continue

                odds_home = odds_draw = odds_away = None
                for span in odds_cell.find_all('p', attrs={'data-type': 'nspf'}):
                    val = span.get('data-value', '')
                    try:
                        sp = float(span.get('data-sp', ''))
                        if val == '3': odds_home = sp
                        elif val == '1': odds_draw = sp
                        elif val == '0': odds_away = sp
                    except (ValueError, TypeError):
                        pass

                if odds_home is None:
                    continue

                match_dt = datetime.fromisoformat(f"{match_date}T{match_time}:00")

                async with p.acquire() as conn:
                    # upsert → matches_live
                    match_id = await conn.fetchval("""
                        INSERT INTO matches_live (
                            date, league, home_team, away_team,
                            odds_home, odds_draw, odds_away,
                            source, source_match_id, status
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'fivehundred', $8, 'scheduled')
                        ON CONFLICT (home_team, away_team, date) DO UPDATE SET
                            odds_home = EXCLUDED.odds_home,
                            odds_draw = EXCLUDED.odds_draw,
                            odds_away = EXCLUDED.odds_away,
                            source_match_id = COALESCE(EXCLUDED.source_match_id, matches_live.source_match_id),
                            updated_at = NOW()
                        RETURNING id
                    """, match_dt, league_cn, home, away,
                        odds_home, odds_draw, odds_away, match_num)

                    # 存赔率快照
                    await conn.execute("""
                        INSERT INTO odds_history (
                            match_id, match_live_id, source, odds_home, odds_draw, odds_away,
                            odds_type, scraped_at, match_time
                        ) VALUES ($1, $1, 'fivehundred', $2, $3, $4, 'main', NOW(), $5)
                    """, match_id, odds_home, odds_draw, odds_away, match_dt)

                    count += 1

            except Exception as e:
                print(f"  解析行失败: {e}")
                continue

        duration = (datetime.now() - started).total_seconds()
        print(f"  500.com 爬取完成：{count} 场比赛，耗时 {duration:.1f}s")
        await _log_run('fivehundred', started, 'success', count)

    except Exception as e:
        print(f"  500.com 爬取失败: {e}")
        await _log_run('fivehundred', started, 'error', 0, str(e))


# ============ 任务2：爬取 football-data.org 结果 ============

LEAGUES = {
    'PL': 'PL',
    'ELC': 'ELC',
    'CL': 'CL',
    'BSA': 'BSA',
    'PD': 'PD',    # La Liga
    'SA': 'SA',    # Serie A
    'BL1': 'BL1',  # Bundesliga
    'FL1': 'FL1',  # Ligue 1
    'PPL': 'PPL',  # Primeira Liga
    'DED': 'DED',  # Eredivisie
}


async def task_fetch_football_data():
    """每天 06:00 爬取 football-data.org 最新比赛结果"""
    started = datetime.now()
    print(f"[{started:%H:%M:%S}] 开始爬取 football-data.org...")

    try:
        p = await get_pool()
        total = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            for league_code, fd_code in LEAGUES.items():
                try:
                    resp = await client.get(
                        f"https://api.football-data.org/v4/competitions/{fd_code}/matches",
                        headers={'X-Auth-Token': FOOTBALL_DATA_API_KEY},
                        params={'status': 'FINISHED', 'limit': 100},
                    )
                    if resp.status_code != 200:
                        print(f"  {league_code}: HTTP {resp.status_code}")
                        continue

                    data = resp.json()
                    matches = data.get('matches', [])

                    for m in matches:
                        try:
                            home = m['homeTeam']['shortName'] or m['homeTeam']['name']
                            away = m['awayTeam']['shortName'] or m['awayTeam']['name']
                            match_date = m['utcDate'][:19]
                            home_goals = m['score']['fullTime']['home']
                            away_goals = m['score']['fullTime']['away']
                            source_id = str(m['id'])

                            if home_goals is None:
                                continue

                            async with p.acquire() as conn:
                                await conn.execute("""
                                    INSERT INTO matches_history (
                                        date, league, home_team, away_team,
                                        home_goals, away_goals,
                                        source, source_match_id, result
                                    ) VALUES ($1, $2, $3, $4, $5, $6, 'footballdata', $7,
                                        CASE WHEN $5::int > $6::int THEN 'home_win'
                                             WHEN $5::int = $6::int THEN 'draw'
                                             ELSE 'away_win' END)
                                    ON CONFLICT (home_team, away_team, date) DO UPDATE SET
                                        home_goals = EXCLUDED.home_goals,
                                        away_goals = EXCLUDED.away_goals,
                                        result = EXCLUDED.result,
                                        updated_at = NOW()
                                """, match_date, league_code, home, away,
                                    home_goals, away_goals, source_id)
                                total += 1

                        except Exception as e:
                            print(f"  解析比赛失败: {e}")
                            continue

                    print(f"  {league_code}: {len(matches)} 场")
                    await asyncio.sleep(1)  # 避免频率限制

                except Exception as e:
                    print(f"  {league_code} 失败: {e}")
                    continue

        duration = (datetime.now() - started).total_seconds()
        print(f"  football-data 爬取完成：{total} 场，耗时 {duration:.1f}s")
        await _log_run('footballdata', started, 'success', total)

        # 自动评估预测
        if total > 0:
            print(f"  开始自动评估预测...")
            eval_started = datetime.now()
            try:
                async with p.acquire() as conn:
                    result = await conn.fetchrow("SELECT * FROM batch_evaluate_predictions(100)")
                    eval_count = result['evaluated_count']
                    fail_count = result['failed_count']
                    eval_duration = (datetime.now() - eval_started).total_seconds()
                    print(f"  预测评估完成：成功 {eval_count} 场，失败 {fail_count} 场，耗时 {eval_duration:.1f}s")
            except Exception as eval_error:
                print(f"  预测评估失败: {eval_error}")

    except Exception as e:
        print(f"  football-data 爬取失败: {e}")
        await _log_run('footballdata', started, 'error', 0, str(e))


# ============ 任务3：重新计算 Pi-Ratings ============

async def task_update_pi_ratings():
    """每天 07:00 重新计算 Pi-Ratings，更新缓存文件"""
    started = datetime.now()
    print(f"[{started:%H:%M:%S}] 重新计算 Pi-Ratings...")

    try:
        p = await get_pool()
        async with p.acquire() as conn:
            rows = await conn.fetch("""
                SELECT date, league, home_team, away_team, home_goals, away_goals
                FROM matches_history
                WHERE home_goals IS NOT NULL
                ORDER BY date ASC
            """)

        matches = [dict(r) for r in rows]
        print(f"  加载 {len(matches)} 场历史比赛")

        from collections import defaultdict
        ratings = defaultdict(lambda: {'attack': 1000.0, 'defense': 1000.0})
        k = 0.05
        home_adv = 0.25

        for m in matches:
            home = m['home_team']
            away = m['away_team']
            hg = m['home_goals']
            ag = m['away_goals']

            expected_home = ratings[home]['attack'] + home_adv - ratings[away]['defense']
            expected_away = ratings[away]['attack'] - ratings[home]['defense']

            ratings[home]['attack'] += k * (hg - expected_home)
            ratings[away]['attack'] += k * (ag - expected_away)
            ratings[home]['defense'] += k * (ag - expected_away)
            ratings[away]['defense'] += k * (hg - expected_home)

        pi_dict = {k: dict(v) for k, v in ratings.items()}

        with open(MODEL_DIR / 'pi_ratings_v1.json', 'w') as f:
            json.dump(pi_dict, f)

        print(f"  Pi-Ratings 更新完成：{len(pi_dict)} 支球队")
        await _log_run('pi_ratings', started, 'success', len(pi_dict))

    except Exception as e:
        print(f"  Pi-Ratings 更新失败: {e}")
        await _log_run('pi_ratings', started, 'error', 0, str(e))


# ============ 辅助：记录运行日志 ============

async def _log_run(name: str, started: datetime, status: str,
                   records: int, error: str = None):
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            await conn.execute("""
                INSERT INTO scraper_runs (scraper_name, started_at, finished_at, status,
                                          records_fetched, error_message, duration_secs)
                VALUES ($1, $2, NOW(), $3, $4, $5, $6)
            """, name, started, status, records, error,
                (datetime.now() - started).total_seconds())
    except Exception as e:
        print(f"  日志记录失败: {e}")


# ============ 任务4：更新实时比分（每5分钟）============

async def task_update_live_scores():
    """每 5 分钟从 500.com 拉实时比分，更新 matches_live 表"""
    started = datetime.now()
    print(f"[{started:%H:%M:%S}] 更新实时比分...")

    try:
        from bs4 import BeautifulSoup
        import re

        today = date.today()
        targets = [today - timedelta(days=i) for i in range(3)]  # 今天、昨天、前天

        async with httpx.AsyncClient(timeout=15.0) as client:
            for target in targets:
                date_str = target.strftime('%Y-%m-%d')
                url = f"https://live.500.com/?e={date_str}"

                try:
                    resp = await client.get(url, headers={'User-Agent': 'Mozilla/5.0'})
                    if resp.status_code != 200:
                        continue
                    resp.encoding = 'gb2312'

                    soup = BeautifulSoup(resp.text, 'html.parser')
                    rows = soup.find_all('tr', id=re.compile(r'^a\d+'))
                    p = await get_pool()
                    updated = 0

                    async with p.acquire() as conn:
                        for row in rows:
                            gy = row.get('gy', '')
                            status_val = row.get('status', '')
                            if status_val != '4':  # 只处理已完赛
                                continue

                            parts = gy.split(',')
                            if len(parts) < 3:
                                continue
                            home_team = parts[1].strip()
                            away_team = parts[2].strip()

                            # 比分在 class="red" 的 td 里，格式 "1 - 1"
                            score_td = row.find('td', class_='red')
                            if not score_td:
                                continue
                            score_text = score_td.get_text(strip=True)
                            score_match = re.match(r'^(\d+)\s*-\s*(\d+)$', score_text)
                            if not score_match:
                                continue
                            home_goals = int(score_match.group(1))
                            away_goals = int(score_match.group(2))

                            # 比赛日期从 td 文本提取，格式 "04-10 00:00"
                            match_date = None
                            for td in row.find_all('td'):
                                td_text = td.get_text(strip=True)
                                dm = re.match(r'^(\d{2}-\d{2})\s+\d{2}:\d{2}$', td_text)
                                if dm:
                                    match_date = date(today.year, int(dm.group(1).split('-')[0]), int(dm.group(1).split('-')[1]))
                                    break

                            result = await conn.execute("""
                                UPDATE matches_live
                                SET home_goals = $3, away_goals = $4,
                                    status = 'finished', updated_at = NOW()
                                WHERE home_team = $1 AND away_team = $2
                                  AND ($5::date IS NULL OR date::date = $5)
                            """, home_team, away_team, home_goals, away_goals, match_date)
                            if result != 'UPDATE 0':
                                updated += 1

                    print(f"  {date_str}: 更新 {updated} 场")
                except Exception as e:
                    print(f"  {date_str} 比分获取失败: {e}")
                    continue

        duration = (datetime.now() - started).total_seconds()
        print(f"  实时比分更新完成，耗时 {duration:.1f}s")
        await _log_run('live_scores', started, 'success', 0)

    except Exception as e:
        print(f"  实时比分更新失败: {e}")
        await _log_run('live_scores', started, 'error', 0, str(e))


# ============ 任务5：运行预测模型（每1小时）============

MODEL_DIR_S = PROJECT_ROOT / "models"
PI_RATINGS_PATH_S = MODEL_DIR_S / "pi_ratings_v1.json"
MODEL_PATH_S = MODEL_DIR_S / "catboost_v1.cbm"
HOME_GOALS_MODEL_PATH_S = MODEL_DIR_S / "home_goals_v1.cbm"
AWAY_GOALS_MODEL_PATH_S = MODEL_DIR_S / "away_goals_v1.cbm"
FEATURES_PATH_S = MODEL_DIR_S / "features_v1.json"

_s_model = None
_s_poisson_home = None
_s_poisson_away = None
_s_feature_names = []
_s_pi_ratings = {}
_s_loaded = False


def _s_load_models():
    """加载模型（全局缓存）"""
    global _s_model, _s_poisson_home, _s_poisson_away, _s_feature_names, _s_pi_ratings, _s_loaded
    if _s_loaded:
        return
    import json
    if PI_RATINGS_PATH_S.exists():
        with open(PI_RATINGS_PATH_S) as f:
            _s_pi_ratings = json.load(f)
    if FEATURES_PATH_S.exists():
        with open(FEATURES_PATH_S) as f:
            _s_feature_names = json.load(f)
    if MODEL_PATH_S.exists():
        try:
            from catboost import CatBoostClassifier
            _s_model = CatBoostClassifier()
            _s_model.load_model(MODEL_PATH_S)
        except Exception as e:
            print(f"  CatBoost 加载失败: {e}")
    if HOME_GOALS_MODEL_PATH_S.exists():
        try:
            import pickle
            with open(HOME_GOALS_MODEL_PATH_S, 'rb') as f:
                _s_poisson_home = pickle.load(f)
            with open(AWAY_GOALS_MODEL_PATH_S, 'rb') as f:
                _s_poisson_away = pickle.load(f)
        except Exception as e:
            print(f"  泊松模型加载失败: {e}")
    _s_loaded = True


def _s_compute_pi_ratings(matches):
    from collections import defaultdict
    ratings = defaultdict(lambda: {'attack': 0.0, 'defense': 0.0})
    k = 0.05
    home_adv = 0.25
    sorted_m = sorted(matches, key=lambda x: x['date'])
    for m in sorted_m:
        if m.get('home_goals') is None:
            continue
        home, away = m['home_team'], m['away_team']
        hg, ag = float(m['home_goals']), float(m['away_goals'])
        exp_h = ratings[home]['attack'] + home_adv - ratings[away]['defense']
        exp_a = ratings[away]['attack'] - ratings[home]['defense']
        ratings[home]['attack'] += k * (hg - exp_h)
        ratings[away]['attack'] += k * (ag - exp_a)
        ratings[home]['defense'] -= k * (ag - exp_a)
        ratings[away]['defense'] -= k * (hg - exp_h)
    return dict(ratings)


def _s_build_indices(all_matches):
    from collections import defaultdict
    team_idx = defaultdict(list)
    h2h_idx = defaultdict(list)
    sorted_m = sorted([m for m in all_matches if m.get('home_goals') is not None],
                      key=lambda x: x['date'], reverse=True)
    for m in sorted_m:
        team_idx[m['home_team']].append(m)
        team_idx[m['away_team']].append(m)
        h2h_idx[(m['home_team'], m['away_team'])].append(m)
    return team_idx, h2h_idx


def _s_recent_form(team, team_idx, match_date, n=5):
    recent = [m for m in team_idx.get(team, []) if m['date'] < match_date][:n]
    if not recent:
        return 0.33, 1.0, 1.0, 1.0
    wins = draws = gs = gc = 0
    for m in recent:
        is_home = m['home_team'] == team
        tg = m['home_goals'] if is_home else m['away_goals']
        og = m['away_goals'] if is_home else m['home_goals']
        gs += tg
        gc += og
        if tg > og:
            wins += 1
        elif tg == og:
            draws += 1
    t = len(recent)
    return wins / t, gs / t, gc / t, (wins * 3 + draws) / t


def _s_h2h(home, away, h2h_idx, match_date, n=10):
    recent = [m for m in h2h_idx.get((home, away), []) if m['date'] < match_date][:n]
    if not recent:
        return 0.33, 0.0, 2.5
    hw = sum(1 for m in recent if m['home_goals'] > m['away_goals'])
    dr = sum(1 for m in recent if m['home_goals'] == m['away_goals'])
    gl = sum(m['home_goals'] + m['away_goals'] for m in recent) / len(recent)
    return (hw + dr * 0.5) / len(recent), dr / len(recent), gl


def _s_build_features(match, team_idx, h2h_idx, pi_ratings):
    home = match['home_team']
    away = match['away_team']
    match_dt = datetime.fromisoformat(match['date'].replace('Z', '+00:00')) \
        if isinstance(match['date'], str) else match['date']

    hr = pi_ratings.get(home, {'attack': 0.0, 'defense': 0.0})
    ar = pi_ratings.get(away, {'attack': 0.0, 'defense': 0.0})
    pi_diff = (hr['attack'] - ar['defense']) - (ar['attack'] - hr['defense'])

    hw, hs, hc, hp = _s_recent_form(home, team_idx, match_dt)
    aw, a_s, a_c, ap = _s_recent_form(away, team_idx, match_dt)
    h2h_rate, h2h_draw, h2h_goals = _s_h2h(home, away, h2h_idx, match_dt)

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


def _s_predict_proba(features, feature_names):
    """纯 Python 预测"""
    if _s_model and feature_names:
        try:
            ordered = [features.get(fn, 0.0) for fn in feature_names]
            probs = _s_model.predict_proba([ordered])[0]
            return {'home': float(probs[1]), 'draw': float(probs[2]), 'away': float(probs[0])}
        except Exception:
            pass
    # fallback
    return {'home': 0.33, 'draw': 0.33, 'away': 0.34}


def _s_predict_score(features, feature_names, pred_proba):
    """泊松比分预测，结果与胜平负概率保持一致"""
    import math
    exp_home = features.get('goals_scored_home_5', 1.2)
    exp_away = features.get('goals_scored_away_5', 1.0)
    if _s_poisson_home:
        try:
            ordered = [features.get(fn, 0.0) for fn in feature_names]
            exp_home = max(_s_poisson_home.predict([ordered])[0], 0.1)
            exp_away = max(_s_poisson_away.predict([ordered])[0], 0.1)
        except Exception:
            pass

    # 确定概率最高的结果
    best = max(pred_proba, key=pred_proba.get)  # 'home' | 'draw' | 'away'

    # 泊松众数比分
    sh = max(round(exp_home), 0)
    sa = max(round(exp_away), 0)

    # 检查比分是否与概率结果一致
    def score_result(h, a):
        if h > a: return 'home'
        if h == a: return 'draw'
        return 'away'

    if score_result(sh, sa) != best:
        # 从泊松分布中找与 best 一致的最高概率比分
        max_goals = 6
        best_prob = -1
        best_sh, best_sa = sh, sa
        for h in range(max_goals + 1):
            ph = math.exp(-exp_home) * (exp_home ** h) / math.factorial(h)
            for a in range(max_goals + 1):
                if score_result(h, a) != best:
                    continue
                pa = math.exp(-exp_away) * (exp_away ** a) / math.factorial(a)
                p = ph * pa
                if p > best_prob:
                    best_prob = p
                    best_sh, best_sa = h, a
        sh, sa = best_sh, best_sa

    return sh, sa, round(exp_home, 2), round(exp_away, 2)


async def task_run_predictions():
    """每 1 小时：读取 DB 中待预测比赛，跑模型，结果存入 prediction_records"""
    started = datetime.now()
    print(f"[{started:%H:%M:%S}] 运行预测模型...")

    try:
        _s_load_models()

        p = await get_pool()

        # 读取历史（用于构建特征）
        async with p.acquire() as conn:
            hist_rows = await conn.fetch("""
                SELECT date, league, home_team, away_team,
                       home_goals, away_goals, odds_home, odds_draw, odds_away
                FROM matches_history WHERE home_goals IS NOT NULL
                ORDER BY date DESC LIMIT 500
            """)
        hist_matches = [dict(r) for r in hist_rows]
        team_idx, h2h_idx = _s_build_indices(hist_matches)

        # 如果没有本地 pi_ratings，从历史计算
        pi_ratings = _s_pi_ratings if _s_pi_ratings else _s_compute_pi_ratings(hist_matches)

        # 读取待预测比赛（今天+明天+昨天，避免遗漏跨天）
        today = date.today()
        date_from = today - timedelta(days=1)
        date_to = today + timedelta(days=2)
        async with p.acquire() as conn:
            matches = await conn.fetch("""
                SELECT id, date, league, home_team, away_team,
                       odds_home, odds_draw, odds_away, status
                FROM matches_live
                WHERE date::date >= $1
                  AND date::date <= $2
                  AND status IN ('scheduled', 'pending', 'live')
                  AND odds_home IS NOT NULL
                ORDER BY date
            """, date_from, date_to)

        model_name = 'catboost_v1' if _s_model else 'pi_baseline'
        saved = 0

        for row in matches:
            m = dict(row)
            features = _s_build_features(m, team_idx, h2h_idx, pi_ratings)
            pred = _s_predict_proba(features, _s_feature_names)
            sh, sa, eh, ea = _s_predict_score(features, _s_feature_names, pred)

            async with p.acquire() as conn:
                # 已有未评估记录则更新
                existing = await conn.fetchrow(
                    "SELECT id FROM prediction_records WHERE match_live_id = $1 AND evaluated_at IS NULL",
                    m['id']
                )
                if existing:
                    await conn.execute("""
                        UPDATE prediction_records
                        SET pred_home = $2, pred_draw = $3, pred_away = $4,
                            pred_score_home = $5, pred_score_away = $6,
                            expected_goals_home = $7, expected_goals_away = $8,
                            model_name = $9, predicted_at = NOW()
                        WHERE id = $1
                    """, existing['id'], pred['home'], pred['draw'], pred['away'],
                        sh, sa, eh, ea, model_name)
                else:
                    await conn.execute("""
                        INSERT INTO prediction_records (
                            match_id, match_live_id, pred_home, pred_draw, pred_away,
                            pred_score_home, pred_score_away,
                            expected_goals_home, expected_goals_away, model_name
                        ) VALUES ($1, $1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """, m['id'], pred['home'], pred['draw'], pred['away'],
                        sh, sa, eh, ea, model_name)
                saved += 1

        duration = (datetime.now() - started).total_seconds()
        print(f"  预测完成：{saved} 场，耗时 {duration:.1f}s")
        await _log_run('predictions', started, 'success', saved)

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  预测失败: {e}")
        await _log_run('predictions', started, 'error', 0, str(e))


# ============ 主入口 ============

async def main():
    print("=" * 50)
    print("Augur 定时任务调度器启动")
    print("=" * 50)

    scheduler = AsyncIOScheduler()

    # 每 5 分钟更新实时比分
    scheduler.add_job(
        task_update_live_scores,
        IntervalTrigger(minutes=5),
        id='live_scores',
        name='实时比分更新',
        next_run_time=datetime.now(),
    )

    # 每小时爬取 500.com 赔率
    scheduler.add_job(
        task_scrape_fivehundred,
        IntervalTrigger(hours=1),
        id='fivehundred',
        name='500.com 赔率爬取',
        next_run_time=datetime.now(),
    )

    # 每小时运行预测模型
    scheduler.add_job(
        task_run_predictions,
        IntervalTrigger(hours=1),
        id='predictions',
        name='预测模型计算',
        next_run_time=datetime.now(),
    )

    # 每天 07:00 更新 Pi-Ratings
    scheduler.add_job(
        task_update_pi_ratings,
        CronTrigger(hour=7, minute=0),
        id='pi_ratings',
        name='Pi-Ratings 更新',
    )

    scheduler.start()
    print("调度器已启动：")
    print("  - 实时比分：每 5 分钟")
    print("  - 500.com 赔率：每小时")
    print("  - 预测模型：每小时")
    print("  - Pi-Ratings：每天 07:00")
    print()

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("调度器已停止")


if __name__ == '__main__':
    asyncio.run(main())
