"""
API-Football (api-sports.io) 适配器
用于获取伤病/停赛数据，辅助预测概率调整

免费额度：100 次/天
文档：https://www.api-football.com/documentation-v3
"""
import httpx
from datetime import date, timedelta
from typing import Optional

BASE_URL = "https://v3.football.api-sports.io"

# API-Football league ID -> 我们的 league code
LEAGUE_MAP = {
    "PL":  39,   # Premier League
    "BL1": 78,   # Bundesliga
    "SA":  135,  # Serie A
    "PD":  140,  # La Liga
    "FL1": 61,   # Ligue 1
    "CL":  2,    # Champions League
    "EL":  3,    # Europa League
    "ELC": 40,   # Championship
    "PPL": 94,   # Primeira Liga
    "DED": 88,   # Eredivisie
}

# API-Football 球队名 -> 我们 DB 的 canonical_name
TEAM_NAME_MAP = {
    "Manchester United":        "Man United",
    "Manchester City":          "Man City",
    "Nottingham Forest":        "Nott'm Forest",
    "Borussia Dortmund":        "Dortmund",
    "Bayer Leverkusen":         "Leverkusen",
    "Bayern München":           "Bayern Munich",
    "Borussia Mönchengladbach": "M'gladbach",
    "Athletic Club":            "Ath Bilbao",
    "Atletico Madrid":          "Ath Madrid",
    "Paris Saint Germain":      "Paris SG",
    "AC Milan":                 "Milan",
    "AS Roma":                  "Roma",
    "Eintracht Frankfurt":      "Ein Frankfurt",
    "FSV Mainz 05":             "Mainz",
    "1899 Hoffenheim":          "Hoffenheim",
    "1. FC Heidenheim":         "Heidenheim",
    "FC St. Pauli":             "St Pauli",
    "Stade Brestois 29":        "Brest",
    "FK Crvena Zvezda":         "Red Star",
    "VfL Wolfsburg":            "Wolfsburg",
    "VfB Stuttgart":            "Stuttgart",
    "VfL Bochum":               "Bochum",
    "Werder Bremen":            "Werder Bremen",
    "SC Freiburg":              "Freiburg",
    "FC Augsburg":              "Augsburg",
    "Celta Vigo":               "Celta",
    "Real Betis":               "Betis",
    "Real Sociedad":            "Sociedad",
    "Rayo Vallecano":           "Vallecano",
    "Espanyol":                 "Espanol",
    "RB Leipzig":               "RB Leipzig",
    "Union Berlin":             "Union Berlin",
    "Holstein Kiel":            "Kiel",
    "FC Koln":                  "FC Koln",
    "PSV Eindhoven":            "PSV Eindhoven",
    "Sporting CP":              "Sporting CP",
    "Benfica":                  "Benfica",
    "Porto":                    "Porto",
    "Feyenoord":                "Feyenoord",
    "Twente":                   "Twente",
    "Como":                     "Como 1907",
}

# 反向映射：DB canonical_name -> API-Football 球队名（用于查询）
_REVERSE_MAP = {v: k for k, v in TEAM_NAME_MAP.items()}


def normalize_team_name(api_name: str) -> str:
    """API-Football 球队名 -> DB canonical_name"""
    return TEAM_NAME_MAP.get(api_name, api_name)


def get_api_team_name(canonical: str) -> str:
    """DB canonical_name -> API-Football 球队名"""
    return _REVERSE_MAP.get(canonical, canonical)


class ApiFootballAdapter:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"x-apisports-key": api_key}

    async def get_team_id(self, team_canonical: str, league_code: str) -> Optional[int]:
        """根据球队名和联赛获取 API-Football team_id"""
        league_id = LEAGUE_MAP.get(league_code)
        if not league_id:
            return None
        api_name = get_api_team_name(team_canonical)
        # 尝试当前赛季和上赛季
        for season in [date.today().year, date.today().year - 1]:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    f"{BASE_URL}/teams",
                    headers=self.headers,
                    params={"league": league_id, "season": season, "search": api_name[:10]},
                )
                data = r.json()
                for t in data.get("response", []):
                    if normalize_team_name(t["team"]["name"]) == team_canonical or \
                       t["team"]["name"] == api_name:
                        return t["team"]["id"]
        return None

    async def get_injuries_for_fixture(self, fixture_id: int) -> list[dict]:
        """按 fixture_id 获取伤病名单（最精确）"""
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{BASE_URL}/injuries",
                headers=self.headers,
                params={"fixture": fixture_id},
            )
            data = r.json()
        return [
            {
                "team": normalize_team_name(item["team"]["name"]),
                "player_name": item["player"]["name"],
                "injury_type": item["player"]["type"],
                "reason": item["player"]["reason"],
            }
            for item in data.get("response", [])
        ]

    async def get_injuries_for_team(
        self, team_id: int, season: int, from_date: date, to_date: date
    ) -> list[dict]:
        """按球队+赛季获取伤病，过滤日期范围"""
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{BASE_URL}/injuries",
                headers=self.headers,
                params={"team": team_id, "season": season},
            )
            data = r.json()
        results = []
        for item in data.get("response", []):
            fixture_date_str = item["fixture"]["date"][:10]
            try:
                fd = date.fromisoformat(fixture_date_str)
            except ValueError:
                continue
            if from_date <= fd <= to_date:
                results.append({
                    "team": normalize_team_name(item["team"]["name"]),
                    "player_name": item["player"]["name"],
                    "injury_type": item["player"]["type"],
                    "reason": item["player"]["reason"],
                    "fixture_date": fd,
                })
        return results

    async def find_fixture_id(
        self, home_team_canonical: str, away_team_canonical: str,
        match_date: date, league_code: str
    ) -> Optional[int]:
        """根据主客队名和日期查找 fixture_id"""
        league_id = LEAGUE_MAP.get(league_code)
        if not league_id:
            return None
        season = match_date.year if match_date.month >= 7 else match_date.year - 1
        date_from = match_date - timedelta(days=1)
        date_to = match_date + timedelta(days=1)
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{BASE_URL}/fixtures",
                headers=self.headers,
                params={
                    "league": league_id,
                    "season": season,
                    "from": date_from.isoformat(),
                    "to": date_to.isoformat(),
                },
            )
            data = r.json()
        home_api = get_api_team_name(home_team_canonical)
        away_api = get_api_team_name(away_team_canonical)
        for f in data.get("response", []):
            h = f["teams"]["home"]["name"]
            a = f["teams"]["away"]["name"]
            if (normalize_team_name(h) == home_team_canonical or h == home_api) and \
               (normalize_team_name(a) == away_team_canonical or a == away_api):
                return f["fixture"]["id"]
        return None
