"""
Augur 定时任务调度器

任务：
- 每小时：爬取 500.com 今日赛程 + 赔率，存入 odds_history
- 每天 06:00：爬取 football-data.org 最新比赛结果，更新 matches
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
FOOTBALL_DATA_API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "acf9e170e02f4679a5ae76c3dd1f2621")
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
                    # 先 upsert match 记录
                    match_id = await conn.fetchval("""
                        INSERT INTO matches (
                            date, league, home_team, away_team,
                            odds_home, odds_draw, odds_away,
                            source, source_match_id, status
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'fivehundred', $8, 'scheduled')
                        ON CONFLICT (source, source_match_id) DO UPDATE SET
                            odds_home = EXCLUDED.odds_home,
                            odds_draw = EXCLUDED.odds_draw,
                            odds_away = EXCLUDED.odds_away,
                            updated_at = NOW()
                        RETURNING id
                    """, match_dt, league_cn, home, away,
                        odds_home, odds_draw, odds_away, match_num)

                    # 存赔率快照（每次爬取都插入新记录，用时间戳区分）
                    await conn.execute("""
                        INSERT INTO odds_history (
                            match_id, source, odds_home, odds_draw, odds_away,
                            odds_type, scraped_at, match_time
                        ) VALUES ($1, 'fivehundred', $2, $3, $4, 'main', NOW(), $5)
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
                                    INSERT INTO matches (
                                        date, league, home_team, away_team,
                                        home_goals, away_goals,
                                        source, source_match_id, status, result
                                    ) VALUES ($1, $2, $3, $4, $5, $6, 'footballdata', $7, 'finished',
                                        CASE WHEN $5::int > $6::int THEN 'home_win'
                                             WHEN $5::int = $6::int THEN 'draw'
                                             ELSE 'away_win' END)
                                    ON CONFLICT (source, source_match_id) DO UPDATE SET
                                        home_goals = EXCLUDED.home_goals,
                                        away_goals = EXCLUDED.away_goals,
                                        status = 'finished',
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
                FROM matches
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


# ============ 主入口 ============

async def main():
    print("=" * 50)
    print("Augur 定时任务调度器启动")
    print("=" * 50)

    scheduler = AsyncIOScheduler()

    # 每小时爬取 500.com
    scheduler.add_job(
        task_scrape_fivehundred,
        IntervalTrigger(hours=1),
        id='fivehundred',
        name='500.com 赔率爬取',
        next_run_time=datetime.now(),  # 立即执行一次
    )

    # 每天 06:00 爬取 football-data.org
    scheduler.add_job(
        task_fetch_football_data,
        CronTrigger(hour=6, minute=0),
        id='footballdata',
        name='football-data.org 结果更新',
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
    print("  - 500.com 赔率：每小时")
    print("  - football-data.org：每天 06:00")
    print("  - Pi-Ratings 更新：每天 07:00")
    print()

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("调度器已停止")


if __name__ == '__main__':
    asyncio.run(main())
