# 适配器基类

from abc import ABC, abstractmethod
from typing import List
from src.data.schema import Match


class BaseAdapter(ABC):
    """数据适配器基类"""

    @abstractmethod
    async def fetch_matches(self, leagues: List[str]) -> List[Match]:
        """获取比赛列表"""
        pass

    @abstractmethod
    async def fetch_historical(self, leagues: List[str],
                               seasons: List[str]) -> List[Match]:
        """获取历史比赛数据"""
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """数据源名称"""
        pass
