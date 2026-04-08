# 泊松回归预测器 - 预测比分

from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy.stats import poisson


class PoissonScorePredictor:
    """
    泊松回归预测器

    分别预测主队和客队的预期进球数，然后用泊松分布计算各种比分的概率
    """

    def __init__(self, home_model_path: Optional[str] = None, away_model_path: Optional[str] = None):
        """
        Args:
            home_model_path: 主队进球数模型路径
            away_model_path: 客队进球数模型路径
        """
        self.home_model = None
        self.away_model = None

        if home_model_path:
            try:
                from catboost import CatBoostRegressor
                self.home_model = CatBoostRegressor()
                self.home_model.load_model(home_model_path)
                print(f"Loaded home goals model from {home_model_path}")
            except Exception as e:
                print(f"Failed to load home model: {e}")

        if away_model_path:
            try:
                from catboost import CatBoostRegressor
                self.away_model = CatBoostRegressor()
                self.away_model.load_model(away_model_path)
                print(f"Loaded away goals model from {away_model_path}")
            except Exception as e:
                print(f"Failed to load away model: {e}")

    def predict_goals(self, features: Dict) -> Tuple[float, float]:
        """
        预测主队和客队的预期进球数

        Returns:
            (expected_home_goals, expected_away_goals)
        """
        if self.home_model is None or self.away_model is None:
            return self._baseline_predict_goals(features)

        feature_vector = self._extract_features(features)

        home_goals = float(self.home_model.predict([feature_vector])[0])
        away_goals = float(self.away_model.predict([feature_vector])[0])

        # 确保非负
        home_goals = max(0.1, home_goals)
        away_goals = max(0.1, away_goals)

        return home_goals, away_goals

    def _baseline_predict_goals(self, features: Dict) -> Tuple[float, float]:
        """基线预测：基于 Pi-Ratings"""
        pi_attack_home = features.get('pi_attack_home', 0.0)
        pi_defense_home = features.get('pi_defense_home', 0.0)
        pi_attack_away = features.get('pi_attack_away', 0.0)
        pi_defense_away = features.get('pi_defense_away', 0.0)
        home_adv = features.get('home_advantage', 0.3)

        # 预期进球 = 进攻评分 + 主场优势 - 对方防守评分 + 基础值
        base_goals = 1.5  # 平均进球数
        home_goals = base_goals + pi_attack_home + home_adv - pi_defense_away
        away_goals = base_goals + pi_attack_away - pi_defense_home

        # 确保合理范围
        home_goals = max(0.3, min(4.0, home_goals))
        away_goals = max(0.3, min(4.0, away_goals))

        return home_goals, away_goals

    def predict_score_probabilities(self, features: Dict, max_goals: int = 5) -> Dict:
        """
        预测各种比分的概率

        Args:
            features: 特征字典
            max_goals: 最大进球数（用于计算）

        Returns:
            {
                'expected_home_goals': float,
                'expected_away_goals': float,
                'most_likely_score': (int, int),
                'score_probs': {(h, a): prob, ...},
                'home_win': float,
                'draw': float,
                'away_win': float,
            }
        """
        lambda_home, lambda_away = self.predict_goals(features)

        # 计算各种比分的概率
        score_probs = {}
        for h in range(max_goals + 1):
            for a in range(max_goals + 1):
                prob_h = poisson.pmf(h, lambda_home)
                prob_a = poisson.pmf(a, lambda_away)
                score_probs[(h, a)] = prob_h * prob_a

        # 找出最可能的比分
        most_likely_score = max(score_probs.items(), key=lambda x: x[1])[0]

        # 计算胜平负概率
        home_win_prob = sum(prob for (h, a), prob in score_probs.items() if h > a)
        draw_prob = sum(prob for (h, a), prob in score_probs.items() if h == a)
        away_win_prob = sum(prob for (h, a), prob in score_probs.items() if h < a)

        return {
            'expected_home_goals': lambda_home,
            'expected_away_goals': lambda_away,
            'most_likely_score': most_likely_score,
            'score_probs': score_probs,
            'home_win': home_win_prob,
            'draw': draw_prob,
            'away_win': away_win_prob,
        }

    def _extract_features(self, features: Dict) -> List[float]:
        """提取模型需要的特征向量"""
        required = self.required_features()
        return [features.get(key, 0.0) for key in required]

    def required_features(self) -> List[str]:
        return [
            'pi_attack_home',
            'pi_defense_home',
            'pi_attack_away',
            'pi_defense_away',
            'pi_diff',
            'home_advantage',
            'league',
        ]

    def train(self, X: List[Dict], y_home: List[float], y_away: List[float],
              cat_features: Optional[List[int]] = None):
        """
        训练模型

        Args:
            X: 特征列表
            y_home: 主队进球数
            y_away: 客队进球数
            cat_features: 类别特征索引
        """
        from catboost import CatBoostRegressor, Pool

        X_array = np.array(X)

        # 训练主队进球模型
        home_pool = Pool(X_array, y_home, cat_features=cat_features)
        self.home_model = CatBoostRegressor(
            iterations=1000,
            learning_rate=0.05,
            depth=6,
            loss_function='RMSE',
            eval_metric='RMSE',
            early_stopping_rounds=50,
            verbose=100,
        )
        print("\n=== Training Home Goals Model ===")
        self.home_model.fit(home_pool)

        # 训练客队进球模型
        away_pool = Pool(X_array, y_away, cat_features=cat_features)
        self.away_model = CatBoostRegressor(
            iterations=1000,
            learning_rate=0.05,
            depth=6,
            loss_function='RMSE',
            eval_metric='RMSE',
            early_stopping_rounds=50,
            verbose=100,
        )
        print("\n=== Training Away Goals Model ===")
        self.away_model.fit(away_pool)

        print("\nBoth models training completed")

    def save(self, home_path: str, away_path: str):
        """保存模型"""
        if self.home_model:
            self.home_model.save_model(home_path)
            print(f"Home goals model saved to {home_path}")
        if self.away_model:
            self.away_model.save_model(away_path)
            print(f"Away goals model saved to {away_path}")
