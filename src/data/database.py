# PostgreSQL 数据库连接和操作

import asyncpg
from typing import List, Optional
from datetime import datetime
import asyncio

from .schema import Match, Team, Prediction


class Database:
    """PostgreSQL 数据库操作类"""

    def __init__(self, connection_string: str):
        self.conn_string = connection_string
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """建立连接池"""
        self.pool = await asyncpg.create_pool(self.conn_string)
        print(f"Connected to PostgreSQL: {self.conn_string.split('@')[1].split('/')[0]}")

    async def disconnect(self):
        """关闭连接池"""
        if self.pool:
            await self.pool.close()
            print("Database connection closed")

    async def init_tables(self):
        """初始化表结构"""
        async with self.pool.acquire() as conn:
            # 球队表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS teams (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    league VARCHAR(50) NOT NULL,
                    pi_attack FLOAT DEFAULT 0,
                    pi_defense FLOAT DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(name, league)
                )
            """)

            # 比赛表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    id SERIAL PRIMARY KEY,
                    date TIMESTAMP NOT NULL,
                    league VARCHAR(50) NOT NULL,
                    home_team VARCHAR(100) NOT NULL,
                    away_team VARCHAR(100) NOT NULL,
                    home_goals INT,
                    away_goals INT,
                    odds_home FLOAT,
                    odds_draw FLOAT,
                    odds_away FLOAT,
                    source VARCHAR(50),
                    source_match_id VARCHAR(100),
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(date, home_team, away_team, source)
                )
            """)

            # 特征表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS match_features (
                    match_id INT PRIMARY KEY,
                    feature_version VARCHAR(20) NOT NULL,
                    features JSONB NOT NULL,
                    computed_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # 预测表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id SERIAL PRIMARY KEY,
                    match_id INT,
                    home_team VARCHAR(100) NOT NULL,
                    away_team VARCHAR(100) NOT NULL,
                    match_date TIMESTAMP NOT NULL,
                    pred_home_win FLOAT NOT NULL,
                    pred_draw FLOAT NOT NULL,
                    pred_away_win FLOAT NOT NULL,
                    model_name VARCHAR(50) NOT NULL,
                    predicted_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # 创建索引
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date);
                CREATE INDEX IF NOT EXISTS idx_matches_league ON matches(league);
                CREATE INDEX IF NOT EXISTS idx_predictions_match ON predictions(match_id);
            """)

            print("Database tables initialized")

    # ========== Match 操作 ==========

    async def insert_match(self, match: Match) -> Optional[int]:
        """插入或更新一场比赛"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO matches (date, league, home_team, away_team,
                                     home_goals, away_goals,
                                     odds_home, odds_draw, odds_away,
                                     source, source_match_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (date, home_team, away_team, source)
                DO UPDATE SET
                    home_goals = EXCLUDED.home_goals,
                    away_goals = EXCLUDED.away_goals,
                    odds_home = EXCLUDED.odds_home,
                    odds_draw = EXCLUDED.odds_draw,
                    odds_away = EXCLUDED.odds_away
                RETURNING id
            """, match.date, match.league, match.home_team, match.away_team,
                match.home_goals, match.away_goals,
                match.odds_home, match.odds_draw, match.odds_away,
                match.source, match.source_match_id)
            return row['id']

    async def insert_matches(self, matches: List[Match]) -> int:
        """批量插入比赛"""
        count = 0
        for match in matches:
            result = await self.insert_match(match)
            if result:
                count += 1
        return count

    async def get_matches(self, league: Optional[str] = None,
                          from_date: Optional[datetime] = None,
                          to_date: Optional[datetime] = None,
                          status: str = 'all') -> List[dict]:
        """查询比赛

        status: 'all' | 'finished' | 'scheduled'
        """
        async with self.pool.acquire() as conn:
            query = "SELECT * FROM matches_history WHERE 1=1"
            params = []
            param_count = 0

            if league:
                param_count += 1
                query += f" AND league = ${param_count}"
                params.append(league)

            if from_date:
                param_count += 1
                query += f" AND date >= ${param_count}"
                params.append(from_date)

            if to_date:
                param_count += 1
                query += f" AND date <= ${param_count}"
                params.append(to_date)

            if status == 'finished':
                query += " AND home_goals IS NOT NULL"
            elif status == 'scheduled':
                query += " AND home_goals IS NULL"

            query += " ORDER BY date DESC"

            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    # ========== Team 操作 ==========

    async def get_or_create_team(self, name: str, league: str) -> int:
        """获取或创建球队"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO teams (name, league)
                VALUES ($1, $2)
                ON CONFLICT (name, league) DO NOTHING
                RETURNING id
            """, name, league)

            if row:
                return row['id']

            row = await conn.fetchrow("""
                SELECT id FROM teams WHERE name = $1 AND league = $2
            """, name, league)

            return row['id']

    async def update_pi_ratings(self, name: str, league: str,
                                pi_attack: float, pi_defense: float):
        """更新球队 Pi-Ratings"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE teams
                SET pi_attack = $3, pi_defense = $4, updated_at = NOW()
                WHERE name = $1 AND league = $2
            """, name, league, pi_attack, pi_defense)

    # ========== Prediction 操作 ==========

    async def insert_prediction(self, pred: Prediction) -> Optional[int]:
        """插入预测结果"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO predictions (match_id, home_team, away_team, match_date,
                                         pred_home_win, pred_draw, pred_away_win, model_name)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """, pred.match_id, pred.home_team, pred.away_team, pred.match_date,
                pred.pred_home_win, pred.pred_draw, pred.pred_away_win, pred.model_name)
            return row['id']

    async def get_latest_prediction(self, match_id: int,
                                    model_name: Optional[str] = None) -> Optional[dict]:
        """获取最新预测"""
        async with self.pool.acquire() as conn:
            if model_name:
                row = await conn.fetchrow("""
                    SELECT * FROM predictions
                    WHERE match_id = $1 AND model_name = $2
                    ORDER BY predicted_at DESC LIMIT 1
                """, match_id, model_name)
            else:
                row = await conn.fetchrow("""
                    SELECT * FROM predictions
                    WHERE match_id = $1
                    ORDER BY predicted_at DESC LIMIT 1
                """, match_id)

            return dict(row) if row else None

    # ========== 特征表操作 ==========

    async def save_features(self, match_id: int, version: str, features: dict):
        """保存特征"""
        async with self.pool.acquire() as conn:
            import json
            await conn.execute("""
                INSERT INTO match_features (match_id, feature_version, features)
                VALUES ($1, $2, $3)
                ON CONFLICT (match_id) DO UPDATE SET
                    features = EXCLUDED.features,
                    feature_version = EXCLUDED.feature_version,
                    computed_at = NOW()
            """, match_id, version, json.dumps(features))

    async def get_features(self, match_id: int,
                           version: Optional[str] = None) -> Optional[dict]:
        """获取特征"""
        import json
        async with self.pool.acquire() as conn:
            if version:
                row = await conn.fetchrow("""
                    SELECT features FROM match_features
                    WHERE match_id = $1 AND feature_version = $2
                """, match_id, version)
            else:
                row = await conn.fetchrow("""
                    SELECT features FROM match_features
                    WHERE match_id = $1
                    ORDER BY computed_at DESC LIMIT 1
                """, match_id)

            return json.loads(row['features']) if row else None
