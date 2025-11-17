"""
Base class for GitHub repository insights.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseInsight(ABC):
    """
    Base class for all GitHub repository insights.

    Subclasses must implement:
    - insight_id: Unique identifier
    - name: Human-readable name
    - description: Brief description
    - category: One of: activity, health, security, ownership, technology
    - visualization_type: 'table', 'chart', or 'both'
    - chart_type: 'bar', 'pie', 'line', 'scatter', 'histogram' (if visualization_type includes 'chart')
    - calculate(): Returns insight data
    """

    insight_id: str = None
    name: str = None
    description: str = None
    category: str = None
    visualization_type: str = 'table'  # 'table', 'chart', 'both'
    chart_type: str = None  # 'bar', 'pie', 'line', 'scatter', 'histogram'
    cache_duration: int = 300  # seconds (5 minutes)

    def __init__(self):
        if not all([self.insight_id, self.name, self.description, self.category]):
            raise ValueError(f"Insight {self.__class__.__name__} missing required attributes")

    @abstractmethod
    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculate and return insight data.

        Args:
            filters: Optional filters (e.g., {'days': 14, 'product_type_id': 5})

        Returns:
            {
                'title': str,
                'data': List[Dict] or Dict,
                'metadata': {
                    'count': int,
                    'timestamp': datetime,
                    'filters_applied': Dict
                }
            }

        For chart visualizations, include 'chart_config':
            {
                'title': str,
                'data': {
                    'labels': List[str],
                    'values': List[int/float],
                    'colors': List[str] (optional)
                },
                'chart_config': {
                    'type': 'pie' | 'bar' | 'line' | 'scatter' | 'histogram',
                    'options': Dict  # Chart.js options
                },
                'metadata': {...}
            }
        """
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """Return insight metadata."""
        return {
            'insight_id': self.insight_id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'visualization_type': self.visualization_type,
            'chart_type': self.chart_type,
            'cache_duration': self.cache_duration,
        }
