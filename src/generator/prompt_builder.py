"""
プロンプトビルダーモジュール

5層構造のプロンプトを組み立て、Claude API に渡す入力を構築する。

層構造:
    1. system_base.txt（基本システムプロンプト）
    2. スタイルプロファイル指示
    3. 書き方パターン指示
    4. 記事生成テンプレート（ユーザープロンプト）
    5. ソースコンテンツ・トピック（ユーザープロンプト内パラメータ）
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from src.scraper.models import WritingPattern

from .style_profile import StyleProfile

logger = logging.getLogger(__name__)


class PromptBuilder:
    """5層構造のプロンプトを組み立てるビルダー。

    プロンプトテンプレートを ``prompts/`` ディレクトリから読み込み、
    動的パラメータを埋め込んで最終的なプロンプト文字列を生成する。
    テンプレートは初回読み込み時にキャッシュされる。
    """

    def __init__(self, prompts_dir: str = "prompts") -> None:
        """PromptBuilder を初期化する。

        Args:
            prompts_dir: プロンプトテンプレートディレクトリへのパス。
                         相対パスの場合はプロジェクトルートからの相対と見なす。
        """
        self.prompts_dir = Path(prompts_dir)
        if not self.prompts_dir.is_absolute():
            # プロジェクトルート（src/ の親）からの相対パスとして解決
            project_root = Path(__file__).resolve().parent.parent.parent
            self.prompts_dir = project_root / self.prompts_dir
        self._cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # テンプレート読み込み
    # ------------------------------------------------------------------

    def _load_template(self, name: str) -> str:
        """テンプレートファイルを読み込む（キャッシュ付き）。

        Args:
            name: テンプレートファイル名（拡張子込み）。

        Returns:
            テンプレート文字列。

        Raises:
            FileNotFoundError: テンプレートファイルが存在しない場合。
        """
        if name in self._cache:
            return self._cache[name]

        template_path = self.prompts_dir / name
        if not template_path.exists():
            raise FileNotFoundError(
                f"プロンプトテンプレートが見つかりません: {template_path}"
            )

        content = template_path.read_text(encoding="utf-8")
        self._cache[name] = content
        logger.debug("テンプレートを読み込みました: %s", name)
        return content

    @staticmethod
    def _render_template(template: str, **kwargs: object) -> str:
        """テンプレート文字列にパラメータを安全に埋め込む。

        Python の ``str.format()`` と異なり、既知のプレースホルダーのみを
        置換し、JSON 例示中の波括弧はそのまま残す。
        プレースホルダーは ``{name}`` 形式で、``kwargs`` のキーと一致する
        もののみが対象となる。

        Args:
            template: テンプレート文字列。
            **kwargs: 置換パラメータ。

        Returns:
            パラメータが埋め込まれた文字列。
        """
        def _replacer(match: re.Match) -> str:
            key = match.group(1)
            if key in kwargs:
                return str(kwargs[key])
            # 既知のプレースホルダーでなければそのまま残す
            return match.group(0)

        # {word_chars} のパターンのみ対象（JSON の {"key": ...} は含まない）
        return re.sub(r"\{(\w+)\}", _replacer, template)

    # ------------------------------------------------------------------
    # システムプロンプト構築（層1-3）
    # ------------------------------------------------------------------

    def build_system_prompt(
        self,
        style_profile: StyleProfile | None = None,
        writing_pattern: WritingPattern | None = None,
    ) -> str:
        """システムプロンプトを組み立てる（層1-3）。

        層1: system_base.txt の基本指示
        層2: StyleProfile からのスタイル指示（オプション）
        層3: WritingPattern からの書き方パターン指示（オプション）

        Args:
            style_profile: 著者のスタイルプロファイル。None の場合はスキップ。
            writing_pattern: 書き方パターン。None の場合はスキップ。

        Returns:
            組み立てられたシステムプロンプト文字列。
        """
        parts: list[str] = []

        # --- 層1: 基本システムプロンプト ---
        base = self._load_template("system_base.txt")
        parts.append(base)

        # --- 層2: スタイルプロファイル ---
        if style_profile is not None:
            instructions = style_profile.get_writing_instructions()
            if instructions:
                parts.append(f"\n## 著者スタイル（{style_profile.name}）\n{instructions}")

        # --- 層3: 書き方パターン ---
        if writing_pattern is not None:
            pattern_text = self._format_writing_pattern(writing_pattern)
            if pattern_text:
                parts.append(f"\n## 書き方パターン\n{pattern_text}")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # 記事生成プロンプト構築（層4-5）
    # ------------------------------------------------------------------

    def build_generation_prompt(
        self,
        topic: str,
        source_content: str,
        target_length: int = 2000,
        min_length: int = 1500,
        max_length: int = 3000,
        style_instructions: str = "",
        writing_pattern: str = "",
    ) -> str:
        """記事生成プロンプトを組み立てる（層4-5）。

        article_generation.txt テンプレートにパラメータを埋め込む。

        Args:
            topic: 記事のトピック。
            source_content: 参考コンテンツ。
            target_length: 文字数目標。
            min_length: 最小文字数。
            max_length: 最大文字数。
            style_instructions: 追加のスタイル指示。
            writing_pattern: 構成パターンの説明。

        Returns:
            パラメータが埋め込まれた生成プロンプト文字列。
        """
        template = self._load_template("article_generation.txt")

        return self._render_template(
            template,
            topic=topic,
            target_length=target_length,
            min_length=min_length,
            max_length=max_length,
            style_instructions=style_instructions or "デフォルト（温かく語りかける文体）",
            source_content=source_content or "（参考コンテンツなし）",
            writing_pattern=writing_pattern or "PREP法（Point→Reason→Example→Point）",
        )

    # ------------------------------------------------------------------
    # トピック抽出プロンプト
    # ------------------------------------------------------------------

    def build_topic_extraction_prompt(
        self, content: str, count: int = 10
    ) -> str:
        """トピック抽出プロンプトを組み立てる。

        Args:
            content: 分析対象のコンテンツ。
            count: 抽出するトピック数。

        Returns:
            トピック抽出プロンプト文字列。
        """
        template = self._load_template("topic_extraction.txt")
        return self._render_template(template, content=content, count=count)

    # ------------------------------------------------------------------
    # レビュープロンプト
    # ------------------------------------------------------------------

    def build_review_prompt(
        self,
        article: str,
        min_length: int = 1500,
        max_length: int = 3000,
    ) -> str:
        """レビュープロンプトを組み立てる。

        Args:
            article: レビュー対象の記事本文。
            min_length: 最小文字数。
            max_length: 最大文字数。

        Returns:
            レビュープロンプト文字列。
        """
        template = self._load_template("content_review.txt")
        return self._render_template(
            template,
            article=article,
            min_length=min_length,
            max_length=max_length,
        )

    # ------------------------------------------------------------------
    # 内部ヘルパー
    # ------------------------------------------------------------------

    @staticmethod
    def _format_writing_pattern(pattern: WritingPattern) -> str:
        """WritingPattern を人間可読な指示文に変換する。

        Args:
            pattern: 書き方パターンデータ。

        Returns:
            フォーマットされた指示文文字列。
        """
        parts: list[str] = []

        parts.append(
            f"- 平均段落長: 約{pattern.avg_paragraph_length:.0f}文字"
        )
        parts.append(
            f"- 平均見出し数: 約{pattern.avg_heading_count:.0f}個"
        )
        parts.append(
            f"- 平均文字数: 約{pattern.avg_word_count:.0f}文字"
        )

        if pattern.common_opening_styles:
            openings = "、".join(pattern.common_opening_styles[:3])
            parts.append(f"- よくある冒頭パターン: {openings}")

        if pattern.common_closing_styles:
            closings = "、".join(pattern.common_closing_styles[:3])
            parts.append(f"- よくある結びパターン: {closings}")

        if pattern.structural_patterns:
            structures = "、".join(pattern.structural_patterns[:3])
            parts.append(f"- 構成パターン: {structures}")

        if pattern.hashtag_frequency:
            # 頻度順で上位5つ
            top_tags = sorted(
                pattern.hashtag_frequency.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5]
            tags_str = "、".join(f"#{tag}" for tag, _ in top_tags)
            parts.append(f"- よく使うハッシュタグ: {tags_str}")

        return "\n".join(parts)
