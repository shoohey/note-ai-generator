"""
scraper パッケージ

note.com の記事取得・解析・トレンド分析機能を提供する。
"""

from .article_parser import ArticleParser
from .models import ArticleMetrics, NoteArticle, SourceContent, WritingPattern
from .note_client import NoteClient
from .trend_analyzer import TrendAnalyzer

__all__ = [
    "ArticleMetrics",
    "ArticleParser",
    "NoteArticle",
    "NoteClient",
    "SourceContent",
    "TrendAnalyzer",
    "WritingPattern",
]
