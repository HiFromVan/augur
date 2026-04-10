"""一次性脚本：
1. 修复 matches_live.source_match_id 为 500.com fid
2. 全量校正比分（从 detail 页取全场比分）
3. 重新评估预测结果
"""
import asyncio
import os
import re
import httpx
import asyncpg
from bs4 import BeautifulSoup
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()
DB = os.getenv('DATABASE_URL')


async def fetch_fulltime(client, fid):
    try:
        url = f"https://live.500.com/detail.php?fid={fid}&r=1"
        r = await client.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15.0)
        r.encoding = 'gb2312'
        soup = BeautifulSoup(r.text, 'html.parser')
        score_span = soup.find('span', class_='score')
        if not score_span:
            return None
        m = re.search(r'(\d+)\s*-\s*(\d+)', score_span.get_text())
        if not m:
            return None
        return int(m.group(1)), int(m.group(2))
    except Exception as e:
        print(f"  fid={fid} 失败: {e}")
        return None


async def main():
    conn = await asyncpg.connect(DB)

    # 取所有 matches_live 记录
    db_matches = await conn.fetch("""
        SELECT id, home_team, away_team, home_goals, away_goals, date::date as match_date, source_match_id
        FROM matches_live
        ORDER BY date DESC
    """)
    print(f"Total matches_live: {len(db_matches)}")

    # 从 500.com 列表页爬 fid，覆盖最近 14 天
    today = date.today()
    # key: (home, away, match_date) -> fid
    fid_map = {}

    async with httpx.AsyncClient(timeout=20.0) as client:
        for i in range(14):
            d = today - timedelta(days=i)
            date_str = d.strftime('%Y-%m-%d')
            url = f"https://live.500.com/?e={date_str}"
            try:
                resp = await client.get(url, headers={'User-Agent': 'Mozilla/5.0'})
                resp.encoding = 'gb2312'
                soup = BeautifulSoup(resp.text, 'html.parser')
                rows = soup.find_all('tr', id=re.compile(r'^a\d+'))
                cnt = 0
                for row in rows:
                    fid = row.get('fid', '')
                    gy = row.get('gy', '')
                    parts = gy.split(',')
                    if len(parts) < 3 or not fid:
                        continue
                    home = parts[1].strip()
                    away = parts[2].strip()
                    match_date_key = None
                    for td in row.find_all('td'):
                        td_text = td.get_text(strip=True)
                        dm = re.match(r'^(\d{2}-\d{2})\s+\d{2}:\d{2}$', td_text)
                        if dm:
                            match_date_key = date(d.year, int(dm.group(1).split('-')[0]), int(dm.group(1).split('-')[1]))
                            break
                    if match_date_key is None:
                        match_date_key = d
                    fid_map[(home, away, match_date_key)] = fid
                    cnt += 1
                print(f"  {date_str}: {cnt} matches")
            except Exception as e:
                print(f"  {date_str}: {e}")

        print(f"\nTotal fid mappings: {len(fid_map)}")

        # 匹配并更新 source_match_id
        fid_updated = 0
        for row in db_matches:
            key = (row['home_team'], row['away_team'], row['match_date'])
            fid = fid_map.get(key)
            if fid and row['source_match_id'] != fid:
                await conn.execute(
                    "UPDATE matches_live SET source_match_id=$2 WHERE id=$1",
                    row['id'], fid
                )
                fid_updated += 1
        print(f"Updated source_match_id for {fid_updated} records")

        # 全量校正比分（只处理有 fid 的已完赛比赛）
        finished = await conn.fetch("""
            SELECT id, home_team, away_team, home_goals, away_goals, source_match_id
            FROM matches_live
            WHERE status = 'finished' AND source_match_id ~ '^[0-9]+'
        """)
        # 也包含 status=finished 但 source_match_id 是旧格式的（用 fid_map 找）
        finished_old = await conn.fetch("""
            SELECT id, home_team, away_team, home_goals, away_goals, source_match_id, date::date as match_date
            FROM matches_live
            WHERE status = 'finished' AND (source_match_id NOT SIMILAR TO '[0-9]+' OR source_match_id IS NULL)
        """)

        to_fix = []
        for row in finished:
            to_fix.append((row['id'], row['home_team'], row['away_team'],
                          row['home_goals'], row['away_goals'], row['source_match_id']))
        for row in finished_old:
            key = (row['home_team'], row['away_team'], row['match_date'])
            fid = fid_map.get(key)
            if fid:
                to_fix.append((row['id'], row['home_team'], row['away_team'],
                              row['home_goals'], row['away_goals'], fid))

        print(f"\nVerifying {len(to_fix)} finished matches...")

        scores = await asyncio.gather(*[fetch_fulltime(client, fid) for _, _, _, _, _, fid in to_fix])

        fixed = 0
        for (match_id, home, away, old_h, old_a, fid), score in zip(to_fix, scores):
            if score is None:
                print(f"  SKIP {home} vs {away} (fid={fid}): detail page failed")
                continue
            new_h, new_a = score
            if old_h == new_h and old_a == new_a:
                print(f"  OK   {home} vs {away}: {old_h}-{old_a}")
            else:
                print(f"  FIX  {home} vs {away}: {old_h}-{old_a} -> {new_h}-{new_a}")
                await conn.execute("""
                    UPDATE matches_live SET home_goals=$2, away_goals=$3, updated_at=NOW()
                    WHERE id=$1
                """, match_id, new_h, new_a)
                fixed += 1

    print(f"\nFixed {fixed} score records")

    # 重新评估所有预测
    print("Re-evaluating all predictions...")
    result = await conn.fetchrow("SELECT * FROM batch_evaluate_predictions(500)")
    print(f"Evaluated: {result[0]}, Failed: {result[1]}")

    await conn.close()


asyncio.run(main())
