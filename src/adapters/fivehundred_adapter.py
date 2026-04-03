# 500彩票网 爬虫适配器

import httpx
from bs4 import BeautifulSoup
from datetime import datetime, date
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class MatchOdds:
    """单场比赛及赔率数据"""
    match_num: str        # 周四003
    league: str           # 英甲
    home_team: str        # 维冈
    away_team: str        # 莱顿东方
    match_date: str       # 2026-04-03
    match_time: str       # 02:45
    # 竞彩赔率
    odds_home: float     # 2.20
    odds_draw: float     # 3.05
    odds_away: float     # 2.88


class FiveHundredAdapter:
    """
    500彩票网 爬虫

    URL: https://trade.500.com/jczq/?playid=312&g=2&date=YYYY-MM-DD
    数据：当日足球竞彩比赛 + 胜平负赔率
    """

    BASE_URL = "https://trade.500.com/jczq/"

    def __init__(self):
        self.session = httpx.Client(timeout=30)

    def fetch_odds(self, target_date: date) -> List[MatchOdds]:
        """
        获取指定日期的比赛和赔率

        Args:
            target_date: 日期

        Returns:
            比赛列表
        """
        url = f"{self.BASE_URL}?playid=312&g=2&date={target_date.strftime('%Y-%m-%d')}"

        resp = self.session.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': 'https://trade.500.com/',
        })
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'html.parser')
        rows = soup.find_all('tr', class_='bet-tb-tr')

        matches = []
        for row in rows:
            try:
                match = self._parse_row(row)
                if match:
                    matches.append(match)
            except Exception as e:
                print(f"Error parsing row: {e}")
                continue

        return matches

    def _parse_row(self, row) -> Optional[MatchOdds]:
        """解析一行比赛数据"""
        # 基本信息
        match_num = row.get('data-matchnum', '')
        league = row.get('data-simpleleague', '')
        home_team = row.get('data-homesxname', '')
        away_team = row.get('data-awaysxname', '')
        match_date = row.get('data-matchdate', '')
        match_time = row.get('data-matchtime', '')

        if not home_team or not away_team:
            return None

        # 赔率在 td-betbtn 里
        odds_cell = row.find('td', class_='td-betbtn')
        if not odds_cell:
            return None

        odds_home = odds_draw = odds_away = None

        # data-type="nspf" 是竞彩胜平负
        nspf_spans = odds_cell.find_all('p', attrs={'data-type': 'nspf'})
        for span in nspf_spans:
            value = span.get('data-value', '')
            sp = span.get('data-sp', '')
            try:
                sp = float(sp)
                if value == '3':      # 主胜
                    odds_home = sp
                elif value == '1':    # 平局
                    odds_draw = sp
                elif value == '0':    # 客胜
                    odds_away = sp
            except (ValueError, TypeError):
                pass

        # 过滤掉没有赔率或比赛已结束的行
        if odds_home is None:
            return None

        return MatchOdds(
            match_num=match_num,
            league=league,
            home_team=home_team,
            away_team=away_team,
            match_date=match_date,
            match_time=match_time,
            odds_home=odds_home,
            odds_draw=odds_draw,
            odds_away=odds_away,
        )

    def get_today_matches(self) -> List[MatchOdds]:
        """获取今日比赛"""
        return self.fetch_odds(date.today())

    def get_date_matches(self, date_str: str) -> List[MatchOdds]:
        """获取指定日期比赛（YYYY-MM-DD）"""
        return self.fetch_odds(datetime.strptime(date_str, '%Y-%m-%d').date())


# 测试
if __name__ == '__main__':
    adapter = FiveHundredAdapter()
    matches = adapter.get_today_matches()

    print(f"今日 {len(matches)} 场比赛：")
    for m in matches:
        implied = (1/m.odds_home + 1/m.odds_draw + 1/m.odds_away)
        print(f"  {m.match_num} | {m.home_team} vs {m.away_team}")
        print(f"           | 赔率: {m.odds_home} / {m.odds_draw} / {m.odds_away}")
        print(f"           | 隐含概率: {1/m.odds_home*100:.1f}% / {1/m.odds_draw*100:.1f}% / {1/m.odds_away*100:.1f}%")
        print()
