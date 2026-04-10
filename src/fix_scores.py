"""一次性脚本：修复 matches_live 中已存入的错误半场比分，改为全场比分"""
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

    # 取所有已有比分的 matches_live 记录
    db_matches = await conn.fetch("""
        SELECT id, home_team, away_team, home_goals, away_goals, date::date as match_date
        FROM matches_live
        WHERE status = 'finished' AND home_goals IS NOT NULL
        ORDER BY date DESC
    """)
    print(f"Found {len(db_matches)} finished matches in DB")

    # 从 500.com 列表页找 fid，覆盖最近 7 天
    today = date.today()
    fid_map = {}  # (home_team, away_team, match_date) -> fid

    async with httpx.AsyncClient(timeout=20.0) as client:
        for i in range(7):
            d = today - timedelta(days=i)
            date_str = d.strftime('%Y-%m-%d')
            url = f"https://live.500.com/?e={date_str}"
            try:
                resp = await client.get(url, headers={'User-Agent': 'Mozilla/5.0'})
                resp.encoding = 'gb2312'
                soup = BeautifulSoup(resp.text, 'html.parser')
                rows = soup.find_all('tr', id=re.compile(r'^a\d+'))
                for row in rows:
                    if row.get('status') != '4':
                        continue
                    fid = row.get('fid', '')
                    gy = row.get('gy', '')
                    parts = gy.split(',')
                    if len(parts) < 3 or not fid:
                        continue
                    home = parts[1].strip()
                    away = parts[2].strip()
                    # 取比赛实际日期（从 td 文本）
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
                print(f"  {date_str}: found {len([k for k in fid_map if k[2] == d or k[2] == d + timedelta(days=1)])} finished matches")
            except Exception as e:
                print(f"  {date_str}: {e}")

        print(f"\nTotal fid mappings: {len(fid_map)}")

        # 匹配 DB 记录和 fid
        to_fix = []
        for row in db_matches:
            key = (row['home_team'], row['away_team'], row['match_date'])
            fid = fid_map.get(key)
            if fid:
                to_fix.append((row['id'], row['home_team'], row['away_team'],
                               row['home_goals'], row['away_goals'], fid))

        print(f"Matched {len(to_fix)} records to fix")

        # 并发取全场比分
        scores = await asyncio.gather(*[fetch_fulltime(client, fid) for _, _, _, _, _, fid in to_fix])

        fixed = 0
        for (match_id, home, away, old_h, old_a, fid), score in zip(to_fix, scores):
            if score is None:
                print(f"  SKIP {home} vs {away}: detail page failed")
                continue
            new_h, new_a = score
            if new_h == old_h and new_a == old_a:
                print(f"  OK   {home} vs {away}: {old_h}-{old_a} (unchanged)")
            else:
                print(f"  FIX  {home} vs {away}: {old_h}-{old_a} -> {new_h}-{new_a}")
                await conn.execute("""
                    UPDATE matches_live SET home_goals=$2, away_goals=$3, updated_at=NOW()
                    WHERE id=$1
                """, match_id, new_h, new_a)
                fixed += 1

    print(f"\nFixed {fixed} records")

    # 重新评估预测
    if fixed > 0:
        print("Re-evaluating predictions...")
        result = await conn.fetchrow("SELECT * FROM batch_evaluate_predictions(200)")
        print(f"Evaluated: {result[0]}, Failed: {result[1]}")

    await conn.close()


asyncio.run(main())
