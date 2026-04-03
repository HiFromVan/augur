# SoccerData 适配器 - 封装 https://github.com/probberechts/soccerdata

import soccerdata as sd
import pandas as pd
from datetime import datetime
from typing import List, Optional
import asyncio

from .base import BaseAdapter
from src.data.schema import Match


# 联赛代码映射
LEAGUE_MAP = {
    'EPL': 'ENG-Premier League',      # 英超
    'ELC': 'ENG-Championship',        # 英冠
    'ESP1': 'ESP-La Liga',            # 西甲
    'ESP2': 'ESP-La Liga 2',          # 西乙
    'ITA1': 'ITA-Serie A',            # 意甲
    'ITA2': 'ITA-Serie B',            # 意乙
    'GER1': 'GER-Bundesliga',         # 德甲
    'GER2': 'GER-2. Bundesliga',      # 德乙
    'FRA1': 'FRA-Ligue 1',            # 法甲
    'FRA2': 'FRA-Ligue 2',            # 法乙
    'CL': 'UEFA-Champions League',    # 欧冠
}


class SoccerDataAdapter(BaseAdapter):
    """
    SoccerData 适配器

    数据源：FBref, WhoScored, Transfermarkt, ClubElo
    文档：https://github.com/probberechts/soccerdata
    """

    def __init__(self, data_source: str = 'FBref'):
        """
        Args:
            data_source: 数据源类型
                - 'FBref': 比赛结果、xG、球员统计（推荐）
                - 'WhoScored': 球员评分、详细事件
                - 'Transfermarkt': 球员身价、转会
                - 'ClubElo': 球队 Elo 评分
        """
        self.data_source = data_source
        self._fbref: Optional[sd.FBref] = None
        self._whoscored: Optional[sd.WhoScored] = None
        self._elo: Optional[sd.Elo] = None

    @property
    def source_name(self) -> str:
        return f"soccerdata.{self.data_source}"

    def _get_fbref(self) -> sd.FBref:
        """懒加载 FBref 实例"""
        if self._fbref is None:
            self._fbref = sd.FBref(verbose=False)
        return self._fbref

    def _get_elo(self) -> sd.Elo:
        """懒加载 Elo 实例"""
        if self._elo is None:
            self._elo = sd.Elo()
        return self._elo

    def _normalize_league(self, league_code: str) -> str:
        """将联赛代码转换为 soccerdata 格式"""
        return LEAGUE_MAP.get(league_code, league_code)

    def _parse_fbref_row(self, row: pd.Series, source_league: str) -> Optional[Match]:
        """解析 FBref 数据行"""
        try:
            # 解析日期
            date_str = row.get('Date', row.get('match_date', ''))
            if not date_str:
                return None
            date = datetime.strptime(str(date_str), '%Y-%m-%d')

            # 获取比分（None 表示未开赛）
            home_goals = row.get('HG')
            away_goals = row.get('AG')

            # 处理空值
            if pd.isna(home_goals):
                home_goals = None
            else:
                home_goals = int(home_goals)

            if pd.isna(away_goals):
                away_goals = None
            else:
                away_goals = int(away_goals)

            return Match(
                date=date,
                league=source_league,
                home_team=str(row.get('Home', row.get('home_team', ''))),
                away_team=str(row.get('Away', row.get('away_team', ''))),
                home_goals=home_goals,
                away_goals=away_goals,
                odds_home=None,  # FBref 没有赔率
                odds_draw=None,
                odds_away=None,
                source=self.source_name,
                source_match_id=None
            )
        except Exception as e:
            print(f"Error parsing row: {e}")
            return None

    async def fetch_matches(self, leagues: List[str]) -> List[Match]:
        """
        获取近期比赛数据

        Args:
            leagues: 联赛代码列表，如 ['EPL', 'ESP1']

        Returns:
            比赛列表
        """
        return await self.fetch_historical(leagues, seasons=['2425'])

    async def fetch_historical(self, leagues: List[str],
                               seasons: Optional[List[str]] = None) -> List[Match]:
        """
        获取历史比赛数据

        Args:
            leagues: 联赛代码列表
            seasons: 赛季列表，格式：
                - '2425' = 2024-25 赛季
                - '2324' = 2023-24 赛季
                - '2223' = 2022-23 赛季
                - 默认 ['2324', '2425']

        Returns:
            比赛列表
        """
        if seasons is None:
            seasons = ['2324', '2425']

        all_matches = []

        if self.data_source == 'FBref':
            fbref = self._get_fbref()

            for league in leagues:
                league_name = self._normalize_league(league)
                print(f"Fetching {league_name} ({league}) for seasons: {seasons}")

                for season in seasons:
                    try:
                        # 获取比赛数据
                        matches = fbref.read_matches(
                            leagues=league_name,
                            seasons=season
                        )

                        if matches is not None and len(matches) > 0:
                            for _, row in matches.iterrows():
                                match = self._parse_fbref_row(row, league)
                                if match:
                                    all_matches.append(match)

                            print(f"  {season}: {len(matches)} matches")

                    except Exception as e:
                        print(f"Error fetching {league} {season}: {e}")
                        continue

        elif self.data_source == 'ClubElo':
            # Elo 评分数据，不是比赛数据
            elo = self._get_elo()
            elo_ratings = elo.get_elos()
            print(f"Fetched Elo ratings: {len(elo_ratings)} entries")

        # 去重
        seen = set()
        unique_matches = []
        for m in all_matches:
            key = (m.date, m.home_team, m.away_team, m.source)
            if key not in seen:
                seen.add(key)
                unique_matches.append(m)

        print(f"Total matches fetched: {len(unique_matches)}")
        return unique_matches

    async def fetch_team_ratings(self, league: str) -> dict:
        """
        获取球队 Elo 评分

        Returns:
            {team_name: elo_rating}
        """
        elo = self._get_elo()
        ratings = elo.get_elos()

        # 过滤指定联赛
        league_ratings = {}
        for _, row in ratings.iterrows():
            if row.get('league') == league:
                league_ratings[row['club']] = row['elo']

        return league_ratings
