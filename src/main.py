# 主程序 - 数据获取和模型训练入口

import asyncio
import os

from src.adapters import FootballDataAdapter
from src.data import Database


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://augur:augur@localhost:5432/augur")
API_KEY = os.getenv("FOOTBALL_DATA_KEY", "")


async def fetch_historical_data():
    """从 football-data.org 获取历史数据并入库"""
    db = Database(DATABASE_URL)
    await db.connect()
    await db.init_tables()

    adapter = FootballDataAdapter(API_KEY)

    # 免费版支持的联赛和赛季（超出范围的返回403）
    leagues = {
        'PL': [2023, 2024, 2025],
        'CL': [2023, 2024, 2025],
        'BSA': [2023, 2024, 2025],
        'ELC': [2024, 2025],
    }

    total = 0
    for league, seasons in leagues.items():
        for season in seasons:
            print(f"[{league} {season}] Fetching...", end=' ')
            try:
                matches = adapter.get_historical_matches(league, [season])
                count = await db.insert_matches(matches)
                total += count
                print(f"inserted {count} matches")
            except Exception as e:
                print(f"Error: {e}")

    print(f"\nTotal inserted: {total} matches")
    await db.disconnect()


async def show_stats():
    """查看数据统计"""
    db = Database(DATABASE_URL)
    await db.connect()

    matches = await db.get_matches(status='finished')
    print(f"\n=== 数据统计 ===")
    print(f"总比赛数: {len(matches)}")

    from collections import Counter
    leagues = Counter(m['league'] for m in matches)
    for league, count in sorted(leagues.items()):
        print(f"  {league}: {count}")

    await db.disconnect()


async def main():
    print("=" * 50)
    print("Augur - 数据拉取")
    print("=" * 50)

    print("\n[Step 1] 拉取历史数据...")
    await fetch_historical_data()

    print("\n[Step 2] 数据统计...")
    await show_stats()


if __name__ == "__main__":
    asyncio.run(main())
