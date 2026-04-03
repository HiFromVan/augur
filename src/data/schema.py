# 核心数据模型定义

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Match:
    """统一比赛数据格式"""
    date: datetime
    league: str
    home_team: str
    away_team: str
    home_goals: Optional[int] = None  # None = 未开赛
    away_goals: Optional[int] = None
    odds_home: Optional[float] = None
    odds_draw: Optional[float] = None
    odds_away: Optional[float] = None
    source: str = "unknown"
    source_match_id: Optional[str] = None


@dataclass
class Team:
    """球队数据"""
    name: str
    league: str
    pi_attack: float = 0.0
    pi_defense: float = 0.0


@dataclass
class Prediction:
    """模型预测结果"""
    match_id: Optional[int]
    home_team: str
    away_team: str
    match_date: datetime
    pred_home_win: float
    pred_draw: float
    pred_away_win: float
    model_name: str
    predicted_at: datetime = None

    def __post_init__(self):
        if self.predicted_at is None:
            self.predicted_at = datetime.now()
