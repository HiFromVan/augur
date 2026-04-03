# football-data.org API 适配器

import requests
from datetime import datetime, timedelta
from typing import List, Optional

from src.data.schema import Match


class FootballDataAdapter:
    """
    football-data.org API 适配器

    文档: https://www.football-data.org/documentation
    免费 Key: 每天 1000 次请求
    """

    BASE_URL = "https://api.football-data.org/v4"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'X-Auth-Token': api_key,
            'Accept': 'application/json'
        })

    @property
    def source_name(self) -> str:
        return "football-data.org"

    def _get(self, path: str, params: dict = None) -> dict:
        """发送 GET 请求"""
        resp = self.session.get(f"{self.BASE_URL}{path}", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_competitions(self) -> List[dict]:
        """获取可用联赛列表"""
        data = self._get("/competitions")
        return data.get('competitions', [])

    def get_matches(self, competition: str,
                    season: int = None,
                    matchday: int = None,
                    status: str = None) -> List[dict]:
        """
        获取比赛列表

        Args:
            competition: 联赛代码，如 'PL', 'CL', 'BSA'
            season: 赛季年份，如 2023
            matchday: 比赛周
            status: 'SCHEDULED', 'FINISHED', 'IN_PLAY' 等
        """
        params = {}
        if season:
            params['season'] = season
        if matchday:
            params['matchday'] = matchday
        if status:
            params['status'] = status

        data = self._get(f"/competitions/{competition}/matches", params)
        return data.get('matches', [])

    def get_match(self, match_id: int) -> dict:
        """获取单场比赛详情"""
        return self._get(f"/matches/{match_id}")

    def get_team_matches(self, team_id: int,
                         season: int = None) -> List[dict]:
        """获取某球队的比赛列表"""
        params = {}
        if season:
            params['season'] = season

        data = self._get(f"/teams/{team_id}/matches", params)
        return data.get('matches', [])

    def _parse_match(self, raw: dict) -> Optional[Match]:
        """解析 API 返回的比赛数据"""
        try:
            status = raw.get('status', '')
            score = raw.get('score', {})
            ft = score.get('fullTime', {})

            # 只有已完成的比赛有比分
            home_goals = ft.get('home')
            away_goals = ft.get('away')

            # 解析日期，去掉时区（转成 naive datetime 兼容 PostgreSQL）
            utc_date = raw['utcDate'].replace('Z', '+00:00')
            dt = datetime.fromisoformat(utc_date)
            dt = dt.replace(tzinfo=None)  # 去掉时区信息

            return Match(
                date=dt,
                league=raw.get('competition', {}).get('code', ''),
                home_team=raw.get('homeTeam', {}).get('shortName', ''),
                away_team=raw.get('awayTeam', {}).get('shortName', ''),
                home_goals=home_goals,
                away_goals=away_goals,
                source=self.source_name,
                source_match_id=str(raw.get('id', '')),
            )
        except Exception as e:
            print(f"Error parsing match: {e}")
            return None

    async def fetch_matches(self, competitions: List[str],
                           season: int = None) -> List[Match]:
        """获取指定联赛的比赛"""
        all_matches = []

        for comp in competitions:
            if season:
                matches = self.get_matches(comp, season=season)
            else:
                # 获取当前赛季所有比赛
                matches = self.get_matches(comp, status='FINISHED')

            for raw in matches:
                match = self._parse_match(raw)
                if match:
                    all_matches.append(match)

        return all_matches

    def get_historical_matches(self, competition: str,
                               seasons: List[int]) -> List[Match]:
        """
        获取历史赛季比赛数据

        Args:
            competition: 联赛代码
            seasons: 赛季列表，如 [2021, 2022, 2023, 2024, 2025]
        """
        all_matches = []

        for s in seasons:
            print(f"  Fetching {competition} {s}...", end=' ')
            try:
                matches = self.get_matches(competition, season=s, status='FINISHED')
                parsed = [self._parse_match(m) for m in matches]
                parsed = [p for p in parsed if p is not None]
                all_matches.extend(parsed)
                print(f"{len(parsed)} matches")
            except Exception as e:
                print(f"Error: {e}")

        return all_matches
