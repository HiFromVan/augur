"""
football-data.co.uk 历史赔率爬虫
提供 Bet365/平均赔率、亚盘、大小球，覆盖五大联赛 1993-今
"""
import asyncio
import asyncpg
import httpx
import csv
import io
import logging
from datetime import datetime
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

DATABASE_URL = 'postgresql://augur:augur@localhost:5432/augur'
BASE_URL = 'https://www.football-data.co.uk/mmz4281'

# league_code -> (file_code, league_name)
LEAGUES = {
    'PL':  ('E0', '英超'),
    'ELC': ('E1', '英冠'),
    'SA':  ('I1', '意甲'),
    'PD':  ('SP1', '西甲'),
    'BL1': ('D1', '德甲'),
    'FL1': ('F1', '法甲'),
    'PPL': ('P1', '葡超'),
    'DED': ('N1', '荷甲'),
}

# 2003-2004 to 2025-2026
SEASONS = [
    ('0304', 2003), ('0405', 2004), ('0506', 2005), ('0607', 2006),
    ('0708', 2007), ('0809', 2008), ('0910', 2009), ('1011', 2010),
    ('1112', 2011), ('1213', 2012), ('1314', 2013), ('1415', 2014),
    ('1516', 2015), ('1617', 2016), ('1718', 2017), ('1819', 2018),
    ('1920', 2019), ('2021', 2020), ('2122', 2021), ('2223', 2022),
    ('2324', 2023), ('2425', 2024), ('2526', 2025),
]


def parse_float(val: str) -> Optional[float]:
    try:
        f = float(val)
        return f if f > 0 else None
    except (ValueError, TypeError):
        return None


def parse_date(date_str: str) -> Optional[datetime]:
    for fmt in ('%d/%m/%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def parse_row(row: dict, league_code: str) -> Optional[dict]:
    date = parse_date(row.get('Date', ''))
    if not date:
        return None

    home = row.get('HomeTeam', '').strip()
    away = row.get('AwayTeam', '').strip()
    if not home or not away:
        return None

    fthg = row.get('FTHG', '')
    ftag = row.get('FTAG', '')
    try:
        home_goals = int(fthg)
        away_goals = int(ftag)
    except (ValueError, TypeError):
        return None

    # 赔率：优先用平均赔率，其次 Bet365
    odds_home = parse_float(row.get('AvgH') or row.get('B365H'))
    odds_draw = parse_float(row.get('AvgD') or row.get('B365D'))
    odds_away = parse_float(row.get('AvgA') or row.get('B365A'))

    # 亚盘
    asian_hcap = parse_float(row.get('AHh') or row.get('AHCh'))
    asian_home = parse_float(row.get('AvgAHH') or row.get('B365AHH'))
    asian_away = parse_float(row.get('AvgAHA') or row.get('B365AHA'))

    # 大小球
    ou_line = 2.5
    ou_over = parse_float(row.get('Avg>2.5') or row.get('B365>2.5'))
    ou_under = parse_float(row.get('Avg<2.5') or row.get('B365<2.5'))

    result = 'home_win' if home_goals > away_goals else ('draw' if home_goals == away_goals else 'away_win')

    return {
        'date': date,
        'league': league_code,
        'home_team': home,
        'away_team': away,
        'home_goals': home_goals,
        'away_goals': away_goals,
        'odds_home': odds_home,
        'odds_draw': odds_draw,
        'odds_away': odds_away,
        'odds_asian_home': asian_home,
        'odds_asian_handicap': asian_hcap,
        'odds_asian_away': asian_away,
        'odds_ou_line': ou_line if ou_over else None,
        'odds_ou_over': ou_over,
        'odds_ou_under': ou_under,
        'result': result,
    }


async def upsert_match(conn, m: dict):
    source_id = f"{m['date'].strftime('%Y%m%d')}_{m['home_team']}_{m['away_team']}_{m['league']}"
    await conn.execute('''
        INSERT INTO matches (
            date, league, home_team, away_team,
            home_goals, away_goals,
            odds_home, odds_draw, odds_away,
            odds_asian_home, odds_asian_handicap, odds_asian_away,
            odds_ou_line, odds_ou_over, odds_ou_under,
            source, source_match_id, status, result
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,
                  'fdco',$16,'finished',$17)
        ON CONFLICT (source, source_match_id) DO UPDATE SET
            odds_home         = COALESCE(EXCLUDED.odds_home, matches.odds_home),
            odds_draw         = COALESCE(EXCLUDED.odds_draw, matches.odds_draw),
            odds_away         = COALESCE(EXCLUDED.odds_away, matches.odds_away),
            odds_asian_home   = COALESCE(EXCLUDED.odds_asian_home, matches.odds_asian_home),
            odds_asian_handicap = COALESCE(EXCLUDED.odds_asian_handicap, matches.odds_asian_handicap),
            odds_asian_away   = COALESCE(EXCLUDED.odds_asian_away, matches.odds_asian_away),
            odds_ou_line      = COALESCE(EXCLUDED.odds_ou_line, matches.odds_ou_line),
            odds_ou_over      = COALESCE(EXCLUDED.odds_ou_over, matches.odds_ou_over),
            odds_ou_under     = COALESCE(EXCLUDED.odds_ou_under, matches.odds_ou_under),
            updated_at        = NOW()
    ''',
        m['date'], m['league'], m['home_team'], m['away_team'],
        m['home_goals'], m['away_goals'],
        m['odds_home'], m['odds_draw'], m['odds_away'],
        m['odds_asian_home'], m['odds_asian_handicap'], m['odds_asian_away'],
        m['odds_ou_line'], m['odds_ou_over'], m['odds_ou_under'],
        source_id, m['result'],
    )


async def scrape_league_season(client: httpx.AsyncClient, pool, league_code: str, file_code: str, season_code: str):
    url = f'{BASE_URL}/{season_code}/{file_code}.csv'
    try:
        r = await client.get(url)
        if r.status_code != 200:
            return 0
        content = r.text
        reader = csv.DictReader(io.StringIO(content))
        count = 0
        async with pool.acquire() as conn:
            for row in reader:
                m = parse_row(row, league_code)
                if m:
                    await upsert_match(conn, m)
                    count += 1
        return count
    except Exception as e:
        log.debug(f'  {league_code} {season_code}: {e}')
        return 0


async def main():
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    grand_total = 0

    async with httpx.AsyncClient(timeout=30) as client:
        for league_code, (file_code, name) in LEAGUES.items():
            league_total = 0
            for season_code, _ in SEASONS:
                n = await scrape_league_season(client, pool, league_code, file_code, season_code)
                if n > 0:
                    log.info(f'  [{league_code}] {season_code}: {n} matches')
                    league_total += n
                await asyncio.sleep(0.3)
            log.info(f'[{league_code}] {name} total: {league_total}')
            grand_total += league_total

    await pool.close()

    conn = await asyncpg.connect(DATABASE_URL)
    total_db = await conn.fetchval("SELECT COUNT(*) FROM matches WHERE source='fdco'")
    with_odds = await conn.fetchval("SELECT COUNT(*) FROM matches WHERE source='fdco' AND odds_home IS NOT NULL")
    await conn.close()
    log.info(f'Done. Inserted {grand_total}. DB fdco total: {total_db}, with odds: {with_odds}')


if __name__ == '__main__':
    asyncio.run(main())
