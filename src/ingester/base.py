"""
コンテンツ取り込みの抽象基底クラス

多様な入力ソース（テキスト、URL、PDFなど）を
統一的に扱うためのインターフェースを定義する。
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from src.scraper.models import SourceContent


class ContentIngester(ABC):
    """コンテンツ取り込みの抽象基底クラス。

    すべてのコンテンツ取り込みクラスはこのクラスを継承し、
    ingest メソッドを実装する。
    """

    @abstractmethod
    def ingest(self, source: str) -> list[SourceContent]:
        """ソースからコンテンツを取り込む。

        Args:
            source: ファイルパスまたはURL。

        Returns:
            取り込まれた SourceContent のリスト。
        """
        pass

    def _generate_id(self) -> str:
        """一意な ID を生成する。

        Returns:
            UUID v4 文字列。
        """
        return str(uuid.uuid4())
