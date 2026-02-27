"""
データモデル定義

note.com記事、書き方パターン、ソースコンテンツの
データ構造を定義するモジュール。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# 記事メトリクス
# ---------------------------------------------------------------------------

@dataclass
class ArticleMetrics:
    """記事のエンゲージメント指標。

    note.comでは閲覧数 (PV) はクリエイター本人にしか表示されないため、
    外部から取得できるスキ数・コメント数のみを保持する。
    """

    like_count: int = 0
    comment_count: int = 0


# ---------------------------------------------------------------------------
# note 記事
# ---------------------------------------------------------------------------

@dataclass
class NoteArticle:
    """note.com の個別記事を表すデータクラス。

    API v2 レスポンスまたは HTML スクレイピング結果から生成される。
    """

    id: str
    title: str
    body: str  # HTML またはプレーンテキスト
    author: str
    url: str
    published_at: str  # ISO 8601 形式
    metrics: ArticleMetrics
    hashtags: list[str] = field(default_factory=list)
    note_type: str = "TextNote"  # TextNote, ImageNote, MovieNote, SoundNote, etc.

    # ------------------------------------------------------------------
    # プロパティ
    # ------------------------------------------------------------------

    @property
    def plain_text(self) -> str:
        """HTMLタグを除去してプレーンテキストを返す。

        body が既にプレーンテキストの場合はそのまま返却する。
        """
        if not self.body:
            return ""
        soup = BeautifulSoup(self.body, "html.parser")
        return soup.get_text(separator="\n", strip=True)

    @property
    def word_count(self) -> int:
        """プレーンテキストの文字数を返す。"""
        return len(self.plain_text)


# ---------------------------------------------------------------------------
# 書き方パターン
# ---------------------------------------------------------------------------

@dataclass
class WritingPattern:
    """複数記事から抽出した書き方パターンの集約結果。

    TrendAnalyzer.analyze() の戻り値として使用する。
    """

    avg_paragraph_length: float
    avg_heading_count: float
    common_opening_styles: list[str]
    common_closing_styles: list[str]
    avg_word_count: float
    hashtag_frequency: dict[str, int]
    structural_patterns: list[str]  # 例: "冒頭に問いかけ", "具体例→教訓"


# ---------------------------------------------------------------------------
# ソースコンテンツ
# ---------------------------------------------------------------------------

@dataclass
class SourceContent:
    """記事生成の元ネタとなるソースコンテンツ。

    書籍、ブログ、PDF、テキストなど多様な入力を統一的に扱う。
    """

    id: str  # UUID v4
    content_type: str  # "book", "blog", "text", "pdf"
    title: str
    content: str
    url: str | None = None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        content_type: str,
        title: str,
        content: str,
        url: str | None = None,
        metadata: dict | None = None,
    ) -> SourceContent:
        """UUIDを自動生成してインスタンスを作成するファクトリメソッド。"""
        return cls(
            id=str(uuid.uuid4()),
            content_type=content_type,
            title=title,
            content=content,
            url=url,
            metadata=metadata or {},
        )
