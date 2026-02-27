"""
テキスト/Markdownファイル取り込みモジュール

ローカルのテキストファイルやMarkdownファイルを読み込み、
SourceContent オブジェクトに変換する。
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.ingester.base import ContentIngester
from src.scraper.models import SourceContent

logger = logging.getLogger(__name__)


class TextIngester(ContentIngester):
    """テキスト/Markdownファイルの取り込み。

    単一ファイルまたはディレクトリを指定して、
    対応する拡張子のファイルを再帰的に読み込む。
    """

    SUPPORTED_EXTENSIONS: set[str] = {".txt", ".md", ".markdown", ".text"}

    def ingest(self, source: str) -> list[SourceContent]:
        """テキストファイルを読み込み SourceContent のリストを返す。

        Args:
            source: ファイルパスまたはディレクトリパス。

        Returns:
            取り込まれた SourceContent のリスト。

        Raises:
            FileNotFoundError: 指定されたパスが存在しない場合。
        """
        path = Path(source)

        if not path.exists():
            raise FileNotFoundError(f"指定されたパスが見つかりません: {source}")

        results: list[SourceContent] = []

        if path.is_file():
            if path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                content = self._read_file(path)
                if content is not None:
                    results.append(content)
            else:
                logger.warning(
                    "サポートされていない拡張子です: %s (対応: %s)",
                    path.suffix,
                    ", ".join(sorted(self.SUPPORTED_EXTENSIONS)),
                )
        elif path.is_dir():
            results = self._read_directory(path)
        else:
            logger.warning("ファイルでもディレクトリでもありません: %s", source)

        logger.info("%d 件のテキストファイルを取り込みました", len(results))
        return results

    def _read_file(self, path: Path) -> SourceContent | None:
        """1ファイルを読み込んで SourceContent に変換する。

        UTF-8 でデコードを試み、失敗した場合は latin-1 でフォールバックする。

        Args:
            path: 読み込むファイルのパス。

        Returns:
            SourceContent オブジェクト。読み込み失敗時は None。
        """
        try:
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                logger.warning(
                    "UTF-8 デコード失敗。latin-1 で再読み込みします: %s", path
                )
                content = path.read_text(encoding="latin-1")

            if not content.strip():
                logger.warning("空のファイルです: %s", path)
                return None

            # タイトルの決定: Markdownの場合は最初の見出しを使用、なければファイル名
            title = self._extract_title(content, path)

            # 拡張子に応じた content_type を決定
            content_type = self._determine_content_type(path)

            return SourceContent(
                id=self._generate_id(),
                content_type=content_type,
                title=title,
                content=content,
                url=None,
                metadata={
                    "file_path": str(path.resolve()),
                    "file_size": path.stat().st_size,
                    "extension": path.suffix.lower(),
                },
            )

        except OSError as e:
            logger.error("ファイル読み込みエラー: %s - %s", path, e)
            return None

    def _read_directory(self, directory: Path) -> list[SourceContent]:
        """ディレクトリ内の対応ファイルを再帰的に読み込む。

        Args:
            directory: 探索するディレクトリパス。

        Returns:
            取り込まれた SourceContent のリスト。
        """
        results: list[SourceContent] = []

        for ext in sorted(self.SUPPORTED_EXTENSIONS):
            for file_path in sorted(directory.rglob(f"*{ext}")):
                content = self._read_file(file_path)
                if content is not None:
                    results.append(content)

        return results

    def _extract_title(self, content: str, path: Path) -> str:
        """コンテンツまたはファイル名からタイトルを抽出する。

        Markdown ファイルの場合、最初の見出し（# で始まる行）を
        タイトルとして使用する。見出しがなければファイル名（拡張子なし）を返す。

        Args:
            content: ファイルの内容。
            path: ファイルパス。

        Returns:
            タイトル文字列。
        """
        if path.suffix.lower() in {".md", ".markdown"}:
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("# ") and not stripped.startswith("## "):
                    return stripped.lstrip("# ").strip()

        return path.stem

    def _determine_content_type(self, path: Path) -> str:
        """ファイル拡張子に応じた content_type を返す。

        Args:
            path: ファイルパス。

        Returns:
            content_type 文字列（"text" または "markdown"）。
        """
        if path.suffix.lower() in {".md", ".markdown"}:
            return "markdown"
        return "text"
