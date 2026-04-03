# 特征工程

import numpy as np
from typing import List, Dict, Optional
from collections import defaultdict


class FeatureEngineer:
    """
    特征工程类

    计算：
    - Pi-Ratings（进攻/防守评分）
    - 近期状态
    - 主客场战绩
    - 对阵历史
    """

    def __init__(self, k: float = 0.1, home_advantage: float = 0.3):
        """
        Args:
            k: Pi-Ratings 学习率
            home_advantage: 主场优势系数
        """
        self.k = k
        self.home_advantage = home_advantage

    def compute_pi_ratings(self, matches: List[dict]) -> Dict[str, Dict]:
        """
        计算球队 Pi-Ratings

        按时间顺序处理比赛，逐步更新评分

        Returns:
            {team_name: {'pi_attack': float, 'pi_defense': float}}
        """
        # 初始化评分
        ratings = defaultdict(lambda: {'pi_attack': 0.0, 'pi_defense': 0.0})

        # 按日期排序
        sorted_matches = sorted(matches, key=lambda x: x['date'])

        for match in sorted_matches:
            if match['home_goals'] is None:
                # 未开赛，跳过
                continue

            home = match['home_team']
            away = match['away_team']
            home_goals = match['home_goals']
            away_goals = match['away_goals']

            # 预期进球差
            expected_diff = (ratings[home]['pi_attack'] - ratings[away]['pi_defense']
                           + self.home_advantage)

            # 实际进球差
            actual_diff = home_goals - away_goals

            # 更新评分
            goal_diff = actual_diff - expected_diff

            ratings[home]['pi_attack'] += self.k * goal_diff
            ratings[home]['pi_defense'] -= self.k * goal_diff * 0.5  # 防守失分少更新

            ratings[away]['pi_attack'] -= self.k * goal_diff * 0.5
            ratings[away]['pi_defense'] += self.k * goal_diff

        return dict(ratings)

    def compute_recent_form(self, team_matches: List[dict],
                            n: int = 5) -> Dict[str, float]:
        """
        计算近期状态

        Args:
            team_matches: 该球队参与的比赛（已按日期排序）
            n: 最近 N 场

        Returns:
            {
                'win_rate_n': 胜率,
                'points_n': 积分,
                'goals_scored_n': 场均进球,
                'goals_conceded_n': 场均失球,
            }
        """
        # 取最近 n 场已完赛的比赛
        finished = [m for m in team_matches if m['home_goals'] is not None]
        recent = finished[-n:] if len(finished) >= n else finished

        if not recent:
            return {
                'win_rate_5': 0.0,
                'points_5': 0.0,
                'goals_scored_5': 0.0,
                'goals_conceded_5': 0.0,
            }

        wins = 0
        draws = 0
        losses = 0
        goals_scored = 0
        goals_conceded = 0

        for match in recent:
            is_home = match['home_team'] == team_matches[0].get('_team_name', '')

            if is_home:
                team_goals = match['home_goals']
                opp_goals = match['away_goals']
            else:
                team_goals = match['away_goals']
                opp_goals = match['home_goals']

            goals_scored += team_goals
            goals_conceded += opp_goals

            if team_goals > opp_goals:
                wins += 1
            elif team_goals == opp_goals:
                draws += 1
            else:
                losses += 1

        points = wins * 3 + draws
        total = len(recent)

        return {
            'win_rate_5': wins / total,
            'points_5': points,
            'goals_scored_5': goals_scored / total,
            'goals_conceded_5': goals_conceded / total,
        }

    def compute_h2h(self, home_matches: List[dict],
                    away_team: str) -> Dict[str, float]:
        """
        计算对阵历史

        Args:
            home_matches: 主队参与的比赛
            away_team: 客队名称

        Returns:
            {
                'h2h_home_win_rate': 主队历史胜率,
                'h2h_draw_rate': 平局率,
                'h2h_avg_goals': 场均进球,
            }
        """
        h2h_matches = [
            m for m in home_matches
            if ((m['home_team'] == away_team or m['away_team'] == away_team)
                and m['home_goals'] is not None)
        ]

        if not h2h_matches:
            return {
                'h2h_win_rate': 0.5,  # 无历史，默认
                'h2h_draw_rate': 0.0,
                'h2h_avg_goals': 2.5,
            }

        wins = 0
        draws = 0
        total_goals = 0

        for match in h2h_matches:
            total_goals += match['home_goals'] + match['away_goals']

            if match['home_goals'] > match['away_goals']:
                wins += 1
            elif match['home_goals'] == match['away_goals']:
                draws += 1

        total = len(h2h_matches)

        return {
            'h2h_win_rate': wins / total,
            'h2h_draw_rate': draws / total,
            'h2h_avg_goals': total_goals / total,
        }

    def build_features(self, match: dict, all_matches: List[dict],
                       pi_ratings: Dict[str, Dict]) -> Dict[str, float]:
        """
        为一场比赛构建完整特征向量

        Args:
            match: 当前比赛
            all_matches: 所有历史比赛
            pi_ratings: Pi-Ratings 字典

        Returns:
            特征字典
        """
        home = match['home_team']
        away = match['away_team']

        # 1. Pi-Ratings 特征
        features = {
            'pi_attack_home': pi_ratings.get(home, {}).get('pi_attack', 0.0),
            'pi_defense_home': pi_ratings.get(home, {}).get('pi_defense', 0.0),
            'pi_attack_away': pi_ratings.get(away, {}).get('pi_attack', 0.0),
            'pi_defense_away': pi_ratings.get(away, {}).get('pi_defense', 0.0),
            'pi_diff': (pi_ratings.get(home, {}).get('pi_attack', 0.0)
                       - pi_ratings.get(away, {}).get('pi_defense', 0.0)),
        }

        # 2. 主场优势
        features['home_advantage'] = self.home_advantage

        # 3. 联赛（类别特征，CatBoost 会处理）
        features['league'] = hash(match.get('league', '')) % 1000

        return features
