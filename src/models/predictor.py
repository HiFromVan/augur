# 模型预测器接口和 CatBoost 实现

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import numpy as np

from src.data.schema import Prediction


class BasePredictor(ABC):
    """模型预测器基类"""

    @abstractmethod
    def predict(self, features: Dict) -> Dict[str, float]:
        """
        预测比赛结果概率

        Args:
            features: 特征字典

        Returns:
            {'home_win': float, 'draw': float, 'away_win': float}
        """
        pass

    @abstractmethod
    def required_features(self) -> List[str]:
        """声明需要的特征 key"""
        pass

    @abstractmethod
    def feature_version(self) -> str:
        """需要的特征版本"""
        pass


class CatBoostPredictor(BasePredictor):
    """
    CatBoost 三分类预测器

    输出：主胜/平/客胜 概率
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Args:
            model_path: 模型文件路径，None 则使用基线预测
        """
        self.model_path = model_path
        self.model = None

        if model_path:
            try:
                from catboost import CatBoostClassifier
                self.model = CatBoostClassifier()
                self.model.load_model(model_path)
                print(f"Loaded CatBoost model from {model_path}")
            except Exception as e:
                print(f"Failed to load model: {e}")
                self.model = None

    def predict(self, features: Dict) -> Dict[str, float]:
        if self.model is None:
            # 无模型时使用基线预测（Pi-Ratings + 主场优势）
            return self._baseline_predict(features)

        # 有模型时用模型预测
        return self._model_predict(features)

    def _baseline_predict(self, features: Dict) -> Dict[str, float]:
        """
        基线预测：基于 Pi-Ratings 差值

        没有训练模型时的降级方案
        """
        pi_diff = features.get('pi_diff', 0.0)
        home_adv = features.get('home_advantage', 0.3)

        # 简单 sigmoid 转换
        combined = pi_diff + home_adv
        home_win = 1 / (1 + np.exp(-combined))

        # 平局概率固定 25% 左右，根据实力差调整
        draw = 0.25 - abs(combined) * 0.05
        draw = max(0.15, min(0.35, draw))

        away_win = 1 - home_win - draw

        # 归一化
        total = home_win + draw + away_win
        return {
            'home_win': home_win / total,
            'draw': draw / total,
            'away_win': away_win / total,
        }

    def _model_predict(self, features: Dict) -> Dict[str, float]:
        """用训练好的模型预测"""
        feature_vector = self._extract_features(features)

        # CatBoost 预测
        probs = self.model.predict_proba([feature_vector])[0]

        return {
            'home_win': float(probs[0]),
            'draw': float(probs[1]),
            'away_win': float(probs[2]),
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

    def feature_version(self) -> str:
        return 'v1'

    def train(self, X: List[Dict], y: List[int],
              cat_features: Optional[List[int]] = None):
        """
        训练模型

        Args:
            X: 特征列表
            y: 标签列表 (0=主胜，1=平，2=客胜)
            cat_features: 类别特征索引
        """
        from catboost import CatBoostClassifier, Pool

        X_array = np.array(X)

        train_pool = Pool(X_array, y, cat_features=cat_features)

        self.model = CatBoostClassifier(
            iterations=1000,
            learning_rate=0.05,
            depth=6,
            loss_function='MultiClass',
            eval_metric='MultiClass',
            early_stopping_rounds=50,
            verbose=100,
        )

        self.model.fit(train_pool)
        print("Model training completed")

    def save(self, path: str):
        """保存模型"""
        if self.model:
            self.model.save_model(path)
            print(f"Model saved to {path}")
