# 比分预测辅助函数

from typing import Tuple, Optional
import numpy as np
from scipy.stats import poisson


def predict_score_from_models(home_model, away_model, features: dict, feature_names: list) -> Tuple[int, int, float, float]:
    """
    使用泊松回归模型预测比分

    Args:
        home_model: 主队进球模型
        away_model: 客队进球模型
        features: 特征字典
        feature_names: 特征名列表

    Returns:
        (pred_score_home, pred_score_away, expected_home, expected_away)
    """
    if home_model is None or away_model is None:
        return predict_score_baseline(features)

    try:
        feature_vector = [features.get(k, 0.0) for k in feature_names]

        # 预测预期进球数
        expected_home = float(home_model.predict([feature_vector])[0])
        expected_away = float(away_model.predict([feature_vector])[0])

        # 确保非负
        expected_home = max(0.1, expected_home)
        expected_away = max(0.1, expected_away)

        # 使用泊松分布找出最可能的比分
        max_goals = 5
        max_prob = 0
        best_score = (1, 1)

        for h in range(max_goals + 1):
            for a in range(max_goals + 1):
                prob_h = poisson.pmf(h, expected_home)
                prob_a = poisson.pmf(a, expected_away)
                prob = prob_h * prob_a

                if prob > max_prob:
                    max_prob = prob
                    best_score = (h, a)

        return best_score[0], best_score[1], expected_home, expected_away

    except Exception as e:
        print(f"Score prediction failed: {e}")
        return predict_score_baseline(features)


def predict_score_baseline(features: dict) -> Tuple[int, int, float, float]:
    """
    基线比分预测（基于 Pi-Ratings）

    Returns:
        (pred_score_home, pred_score_away, expected_home, expected_away)
    """
    pi_attack_home = features.get('pi_attack_home', 0.0)
    pi_defense_home = features.get('pi_defense_home', 0.0)
    pi_attack_away = features.get('pi_attack_away', 0.0)
    pi_defense_away = features.get('pi_defense_away', 0.0)
    home_adv = features.get('home_advantage', 0.3)

    # 预期进球 = 进攻评分 + 主场优势 - 对方防守评分 + 基础值
    base_goals = 1.5
    expected_home = base_goals + pi_attack_home + home_adv - pi_defense_away
    expected_away = base_goals + pi_attack_away - pi_defense_home

    # 确保合理范围
    expected_home = max(0.3, min(4.0, expected_home))
    expected_away = max(0.3, min(4.0, expected_away))

    # 使用泊松分布找出最可能的比分
    max_goals = 5
    max_prob = 0
    best_score = (1, 1)

    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            prob_h = poisson.pmf(h, expected_home)
            prob_a = poisson.pmf(a, expected_away)
            prob = prob_h * prob_a

            if prob > max_prob:
                max_prob = prob
                best_score = (h, a)

    return best_score[0], best_score[1], expected_home, expected_away
