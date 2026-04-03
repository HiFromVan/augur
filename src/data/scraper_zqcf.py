"""
足球财富 (zqcf918.com) 历史数据爬虫
抓取：历史比赛结果 + 赔率（胜平负/亚盘/大小球）
"""
import asyncio
import asyncpg
import httpx
import logging
from datetime import datetime
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

DATABASE_URL = 'postgresql://augur:augur@localhost:5432/augur'

TARGET_LEAGUES = {
    82:  'PL',   # 英超
    83:  'ELC',  # 英冠
    108: 'SA',   # 意甲
    120: 'PD',   # 西甲
    129: 'BL1',  # 德甲
    142: 'FL1',  # 法甲
    46:  'CL',   # 欧冠
    47:  'EL',   # 欧联
    151: 'PPL',  # 葡超
    168: 'DED',  # 荷甲
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://www.zqcf918.com/',
    'Content-Type': 'application/x-www-form-urlencoded',
}


def parse_float(val) -> Optional[float]:
    try:
        f = float(val)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def parse_match_time(time_str: str, season_name: str) -> Optional[datetime]:
    try:
        # Full datetime: "2024-08-17 03:00:00" or "2024-08-17 03:00"
        if len(time_str) >= 16 and time_str[4] == '-':
            return datetime.strptime(time_str[:16], '%Y-%m-%d %H:%M')
        # Short format: "08-17 03:00" — infer year from season e.g. "2024-2025"
        parts = season_name.split('-')
        start_year = int(parts[0])
        end_year = int(parts[1]) if len(parts) > 1 else start_year + 1
        month = int(time_str[:2])
        # Aug-Dec belongs to start_year, Jan-Jul belongs to end_year
        year = start_year if month >= 7 else end_year
        return datetime.strptime(f'{year}-{time_str}', '%Y-%m-%d %H:%M')
    except Exception:
        return None


async def get_seasons(client: httpx.AsyncClient, league_id: int) -> list:
    r = await client.post(
        'https://www.zqcf918.com/new/zlk/getLeagueInfo',
        data={'leagueId': league_id},
        headers=HEADERS,
    )
    data = r.json()
    if data.get('code') != 1:
        return []
    return data['data'].get('matchSeasonList', [])


async def get_matches(client: httpx.AsyncClient, league_id: int, season_id: int) -> list:
    r = await client.post(
        'https://www.zqcf918.com/new/zlk/schedules',
        data={'leagueId': league_id, 'seasonId': season_id},
        headers=HEADERS,
    )
    data = r.json()
    if data.get('code') != 1:
        return []
    matches = []
    for stage in data.get('data', []):
        for round_matches in stage.get('schedules', []):
            if isinstance(round_matches, list):
                matches.extend(round_matches)
            elif isinstance(round_matches, dict):
                matches.append(round_matches)
    return matches


async def upsert_match(conn, m: dict, league_code: str, season_name: str) -> bool:
    schedule_id = str(m.get('scheduleId', ''))
    if not schedule_id:
        return False

    time_str = m.get('matchTime', '')
    match_dt = parse_match_time(time_str, season_name)
    if not match_dt:
        return False

    home_score = m.get('homeScore')
    guest_score = m.get('guestScore')
    state = m.get('matchState', 0)
    is_finished = state == -1 and home_score is not None and guest_score is not None
    if not is_finished:
        return False

    if home_score > guest_score:
        result = 'home_win'
    elif home_score == guest_score:
        result = 'draw'
    else:
        result = 'away_win'

    await conn.execute('''
        INSERT INTO matches (
            date, league, home_team, away_team,
            home_goals, away_goals,
            odds_home, odds_draw, odds_away,
            odds_asian_home, odds_asian_handicap, odds_asian_away,
            odds_ou_line, odds_ou_over, odds_ou_under,
            source, source_match_id, zqcf_match_id,
            status, result
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,
                  'zqcf',$16,$16,'finished',$17)
        ON CONFLICT (source, source_match_id) DO UPDATE SET
            home_goals        = EXCLUDED.home_goals,
            away_goals        = EXCLUDED.away_goals,
            odds_home         = COALESCE(EXCLUDED.odds_home, matches.odds_home),
            odds_draw         = COALESCE(EXCLUDED.odds_draw, matches.odds_draw),
            odds_away         = COALESCE(EXCLUDED.odds_away, matches.odds_away),
            odds_asian_home   = COALESCE(EXCLUDED.odds_asian_home, matches.odds_asian_home),
            odds_asian_handicap = COALESCE(EXCLUDED.odds_asian_handicap, matches.odds_asian_handicap),
            odds_asian_away   = COALESCE(EXCLUDED.odds_asian_away, matches.odds_asian_away),
            odds_ou_line      = COALESCE(EXCLUDED.odds_ou_line, matches.odds_ou_line),
            odds_ou_over      = COALESCE(EXCLUDED.odds_ou_over, matches.odds_ou_over),
            odds_ou_under     = COALESCE(EXCLUDED.odds_ou_under, matches.odds_ou_under),
            status            = 'finished',
            result            = EXCLUDED.result,
            updated_at        = NOW()
    ''',
        match_dt, league_code, m.get('homeTeam', ''), m.get('guestTeam', ''),
        int(home_score), int(guest_score),
        parse_float(m.get('opHome')), parse_float(m.get('opPk')), parse_float(m.get('opAway')),
        parse_float(m.get('ypHome')), parse_float(m.get('ypPk')), parse_float(m.get('ypAway')),
        parse_float(m.get('ballPk')), parse_float(m.get('ballBig')), parse_float(m.get('ballSmall')),
        schedule_id, result,
    )
    return True


async def scrape_league(pool, client: httpx.AsyncClient, league_id: int, league_code: str):
    seasons = await get_seasons(client, league_id)
    log.info(f'[{league_code}] {len(seasons)} seasons')

    total = 0
    for season in seasons:
        season_id = season['id']
        season_name = season['seasonName']
        matches = await get_matches(client, league_id, season_id)

        count = 0
        async with pool.acquire() as conn:
            for m in matches:
                try:
                    ok = await upsert_match(conn, m, league_code, season_name)
                    if ok:
                        count += 1
                except Exception as e:
                    log.debug(f'  skip match: {e}')

        log.info(f'  [{league_code}] {season_name}: {count}/{len(matches)} inserted')
        total += count
        await asyncio.sleep(0.5)

    log.info(f'[{league_code}] total: {total}')
    return total


async def main():
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)

    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        grand_total = 0
        for league_id, league_code in TARGET_LEAGUES.items():
            try:
                n = await scrape_league(pool, client, league_id, league_code)
                grand_total += n
            except Exception as e:
                log.error(f'[{league_code}] failed: {e}')

    await pool.close()

    # Final count
    conn = await asyncpg.connect(DATABASE_URL)
    total_db = await conn.fetchval("SELECT COUNT(*) FROM matches WHERE source='zqcf'")
    await conn.close()
    log.info(f'Done. Inserted {grand_total} matches. DB total zqcf: {total_db}')


if __name__ == '__main__':
    asyncio.run(main())
