"""
トレンド分析モジュール

複数の note.com 記事を分析し、人気記事に共通する
書き方パターンを抽出する。
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from rich.console import Console

from .article_parser import ArticleParser
from .models import NoteArticle, WritingPattern

console = Console()


class TrendAnalyzer:
    """人気 note 記事の書き方パターンを分析するクラス。

    使い方:
        1. ``add_articles()`` で分析対象の記事を蓄積
        2. ``analyze()`` で書き方パターンを集約して取得
    """

    def __init__(self) -> None:
        """TrendAnalyzer を初期化する。"""
        self.articles: list[NoteArticle] = []

    # ------------------------------------------------------------------
    # 記事の追加
    # ------------------------------------------------------------------

    def add_articles(self, articles: list[NoteArticle]) -> None:
        """分析対象の記事を追加する。

        Args:
            articles: 追加する NoteArticle のリスト。
        """
        self.articles.extend(articles)
        console.log(
            f"[green]記事 {len(articles)} 件を追加 "
            f"(合計 {len(self.articles)} 件)[/green]"
        )

    # ------------------------------------------------------------------
    # パターン分析
    # ------------------------------------------------------------------

    def analyze(self) -> WritingPattern:
        """蓄積された記事群から書き方パターンを分析する。

        Returns:
            WritingPattern: 分析結果を集約したデータクラス。

        Raises:
            ValueError: 分析対象の記事が 0 件の場合。
        """
        if not self.articles:
            raise ValueError("分析対象の記事がありません。add_articles() で記事を追加してください。")

        console.log(f"[blue]{len(self.articles)} 件の記事を分析中...[/blue]")

        # 各記事の構造を解析
        structures: list[dict[str, Any]] = []
        for article in self.articles:
            try:
                structure = ArticleParser.extract_structure(article)
                structures.append(structure)
            except Exception as exc:
                console.log(
                    f"[yellow]構造解析スキップ ({article.title[:20]}...): {exc}[/yellow]"
                )

        # 1. 平均段落文字数
        avg_paragraph_length = self._calc_avg(
            [s["avg_paragraph_length"] for s in structures if s.get("avg_paragraph_length")]
        )

        # 2. 見出し数の平均
        avg_heading_count = self._calc_avg(
            [s["heading_count"] for s in structures]
        )

        # 3. 冒頭パターンの集計
        opening_styles = [s["opening_style"] for s in structures if s.get("opening_style")]
        common_opening_styles = self._top_n(opening_styles, n=5)

        # 4. 締めパターンの集計
        closing_styles = [s["closing_style"] for s in structures if s.get("closing_style")]
        common_closing_styles = self._top_n(closing_styles, n=5)

        # 5. 平均文字数
        word_counts = [article.word_count for article in self.articles if article.word_count > 0]
        avg_word_count = self._calc_avg(word_counts)

        # 6. ハッシュタグ頻度
        hashtag_frequency = self._count_hashtags()

        # 7. 構造パターン
        structural_patterns = self._identify_structural_patterns(structures)

        result = WritingPattern(
            avg_paragraph_length=round(avg_paragraph_length, 1),
            avg_heading_count=round(avg_heading_count, 1),
            common_opening_styles=common_opening_styles,
            common_closing_styles=common_closing_styles,
            avg_word_count=round(avg_word_count, 1),
            hashtag_frequency=hashtag_frequency,
            structural_patterns=structural_patterns,
        )

        console.log("[green]分析完了[/green]")
        self._print_summary(result)

        return result

    # ------------------------------------------------------------------
    # 冒頭・締めスタイル分類
    # ------------------------------------------------------------------

    def _classify_opening(self, text: str) -> str:
        """冒頭スタイルを分類する。

        ArticleParser の静的メソッドに委譲する。

        Args:
            text: 記事のプレーンテキスト。

        Returns:
            分類ラベル文字列。
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return ArticleParser._classify_opening(lines)

    def _classify_closing(self, text: str) -> str:
        """締めスタイルを分類する。

        ArticleParser の静的メソッドに委譲する。

        Args:
            text: 記事のプレーンテキスト。

        Returns:
            分類ラベル文字列。
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return ArticleParser._classify_closing(lines)

    # ------------------------------------------------------------------
    # 内部ヘルパー
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_avg(values: list[float | int]) -> float:
        """数値リストの平均値を計算する。空リストの場合は 0.0 を返す。"""
        if not values:
            return 0.0
        return sum(values) / len(values)

    @staticmethod
    def _top_n(items: list[str], n: int = 5) -> list[str]:
        """頻度上位 n 件のラベルを返す。"""
        if not items:
            return []
        counter = Counter(items)
        return [label for label, _ in counter.most_common(n)]

    def _count_hashtags(self) -> dict[str, int]:
        """全記事のハッシュタグ出現頻度を集計する。"""
        counter: Counter[str] = Counter()
        for article in self.articles:
            counter.update(article.hashtags)
        return dict(counter.most_common(30))

    def _identify_structural_patterns(
        self, structures: list[dict[str, Any]]
    ) -> list[str]:
        """構造データ群から特徴的な構造パターンを特定する。

        Args:
            structures: ArticleParser.extract_structure() の結果リスト。

        Returns:
            パターンラベルのリスト（例: "冒頭に問いかけ", "リスト活用"）。
        """
        if not structures:
            return []

        patterns: list[str] = []
        total = len(structures)

        # 問いかけ冒頭の割合
        opening_question_ratio = sum(
            1 for s in structures if s.get("opening_style") == "問いかけ"
        ) / total
        if opening_question_ratio >= 0.3:
            patterns.append("冒頭に問いかけ")

        # 体験談冒頭
        opening_experience_ratio = sum(
            1 for s in structures if s.get("opening_style") == "体験談"
        ) / total
        if opening_experience_ratio >= 0.3:
            patterns.append("体験談から始める")

        # 行動喚起による締め
        closing_cta_ratio = sum(
            1 for s in structures if s.get("closing_style") == "行動喚起"
        ) / total
        if closing_cta_ratio >= 0.3:
            patterns.append("行動喚起で締める")

        # リスト活用
        list_ratio = sum(1 for s in structures if s.get("has_list")) / total
        if list_ratio >= 0.4:
            patterns.append("リスト活用")

        # 引用活用
        quote_ratio = sum(1 for s in structures if s.get("has_quote")) / total
        if quote_ratio >= 0.3:
            patterns.append("引用活用")

        # 見出し多用（平均 3 以上）
        avg_headings = self._calc_avg(
            [s["heading_count"] for s in structures]
        )
        if avg_headings >= 3:
            patterns.append("見出しで構造化")

        # 短い段落（平均 100 文字以下）
        avg_para = self._calc_avg(
            [s["avg_paragraph_length"] for s in structures if s.get("avg_paragraph_length")]
        )
        if 0 < avg_para <= 100:
            patterns.append("短い段落でテンポよく")
        elif avg_para > 200:
            patterns.append("じっくり長文段落")

        # 画像活用
        image_ratio = sum(1 for s in structures if s.get("has_image")) / total
        if image_ratio >= 0.5:
            patterns.append("画像を多用")

        if not patterns:
            patterns.append("特定パターンなし（多様なスタイル）")

        return patterns

    # ------------------------------------------------------------------
    # サマリー表示
    # ------------------------------------------------------------------

    def _print_summary(self, pattern: WritingPattern) -> None:
        """分析結果のサマリーをコンソールに表示する。"""
        console.rule("[bold blue]トレンド分析結果[/bold blue]")
        console.print(f"  平均文字数      : {pattern.avg_word_count:,.1f} 文字")
        console.print(f"  平均段落文字数  : {pattern.avg_paragraph_length:,.1f} 文字")
        console.print(f"  平均見出し数    : {pattern.avg_heading_count:.1f}")
        console.print(f"  冒頭スタイル    : {', '.join(pattern.common_opening_styles)}")
        console.print(f"  締めスタイル    : {', '.join(pattern.common_closing_styles)}")
        console.print(f"  構造パターン    : {', '.join(pattern.structural_patterns)}")

        if pattern.hashtag_frequency:
            top_tags = list(pattern.hashtag_frequency.items())[:10]
            tag_str = ", ".join(f"#{tag}({count})" for tag, count in top_tags)
            console.print(f"  人気ハッシュタグ: {tag_str}")

        console.rule()
