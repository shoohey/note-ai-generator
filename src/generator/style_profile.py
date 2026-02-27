"""
スタイルプロファイル管理モジュール

著者の文体を分析し、プロファイルとして保持・活用するための
クラス群を提供する。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# StyleProfile: 著者の文体プロファイル
# ---------------------------------------------------------------------------


class StyleProfile:
    """著者のスタイルプロファイルを管理する。

    JSON 形式でシリアライズ/デシリアライズが可能であり、
    記事生成時にスタイル指示文として利用する。
    """

    def __init__(self, name: str, profile_data: dict | None = None) -> None:
        """StyleProfile を初期化する。

        Args:
            name: 著者名またはプロファイル名。
            profile_data: プロファイルデータ辞書。None の場合は空辞書。
        """
        self.name = name
        self.profile_data = profile_data or {}

    # ------------------------------------------------------------------
    # シリアライズ / デシリアライズ
    # ------------------------------------------------------------------

    @classmethod
    def from_json(cls, name: str, json_str: str) -> StyleProfile:
        """JSON 文字列からプロファイルを復元する。

        Args:
            name: 著者名またはプロファイル名。
            json_str: プロファイルデータの JSON 文字列。

        Returns:
            復元された StyleProfile インスタンス。

        Raises:
            json.JSONDecodeError: JSON 文字列のパースに失敗した場合。
        """
        data = json.loads(json_str)
        return cls(name=name, profile_data=data)

    def to_json(self) -> str:
        """プロファイルを JSON 文字列に変換する。

        Returns:
            インデント付きの JSON 文字列。
        """
        return json.dumps(self.profile_data, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # スタイル指示文の生成
    # ------------------------------------------------------------------

    def get_writing_instructions(self) -> str:
        """記事生成用のスタイル指示文を返す。

        profile_data に ``writing_instructions`` キーがあればその値を返し、
        なければ各フィールドからスタイル指示文を自動生成する。

        Returns:
            スタイル指示文の文字列。プロファイルが空の場合は空文字列。
        """
        if not self.profile_data:
            return ""

        # writing_instructions が明示的に設定されている場合はそちらを優先
        if "writing_instructions" in self.profile_data:
            return self.profile_data["writing_instructions"]

        # 各フィールドから指示文を組み立てる
        parts: list[str] = []

        if self.tone:
            parts.append(f"語調: {self.tone}")

        if self.characteristic_expressions:
            expressions = "、".join(self.characteristic_expressions)
            parts.append(f"特徴的な表現: {expressions}")

        sentence_style = self.profile_data.get("sentence_style", "")
        if sentence_style:
            parts.append(f"文体: {sentence_style}")

        development = self.profile_data.get("development_pattern", "")
        if development:
            parts.append(f"展開パターン: {development}")

        emotional = self.profile_data.get("emotional_expression", "")
        if emotional:
            parts.append(f"感情表現: {emotional}")

        engagement = self.profile_data.get("reader_engagement", "")
        if engagement:
            parts.append(f"読者への呼びかけ: {engagement}")

        unique_features = self.profile_data.get("unique_features", [])
        if unique_features:
            features = "、".join(unique_features)
            parts.append(f"独自の特徴: {features}")

        if not parts:
            return ""

        return "以下のスタイルで記事を書いてください：\n" + "\n".join(
            f"- {p}" for p in parts
        )

    # ------------------------------------------------------------------
    # プロパティ
    # ------------------------------------------------------------------

    @property
    def tone(self) -> str:
        """語調（フォーマル/カジュアル/語りかけ調 等）を返す。"""
        return self.profile_data.get("tone", "")

    @property
    def characteristic_expressions(self) -> list[str]:
        """特徴的な表現のリストを返す。"""
        return self.profile_data.get("characteristic_expressions", [])

    def __repr__(self) -> str:
        return f"StyleProfile(name={self.name!r}, keys={list(self.profile_data.keys())})"


# ---------------------------------------------------------------------------
# StyleAnalyzer: Claude API を使った文体分析
# ---------------------------------------------------------------------------


class StyleAnalyzer:
    """Claude API を使って著者のスタイルを分析する。

    複数の記事テキストを入力として受け取り、文体プロファイルを生成する。
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5-20250514",
    ) -> None:
        """StyleAnalyzer を初期化する。

        Args:
            api_key: Anthropic API キー。
            model: 使用する Claude モデルの ID。
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # プロンプトテンプレートの読み込み
        prompts_dir = Path(__file__).resolve().parent.parent.parent / "prompts"
        template_path = prompts_dir / "style_analysis.txt"
        if template_path.exists():
            self._template = template_path.read_text(encoding="utf-8")
        else:
            logger.warning(
                "スタイル分析テンプレートが見つかりません: %s", template_path
            )
            self._template = (
                "以下の記事群を分析し、著者の文体プロファイルをJSON形式で"
                "生成してください。\n\n{articles}"
            )

    # ------------------------------------------------------------------
    # 分析メソッド（非同期版 - シグネチャ互換のため残す）
    # ------------------------------------------------------------------

    async def analyze(
        self, articles: list[str], author_name: str
    ) -> StyleProfile:
        """複数の記事からスタイルプロファイルを生成する（非同期版）。

        内部的には同期版の :meth:`analyze_sync` を呼び出す。

        Args:
            articles: 分析対象の記事テキストのリスト。
            author_name: 著者名。

        Returns:
            生成された StyleProfile。
        """
        return self.analyze_sync(articles, author_name)

    # ------------------------------------------------------------------
    # 分析メソッド（同期版）
    # ------------------------------------------------------------------

    def analyze_sync(
        self, articles: list[str], author_name: str
    ) -> StyleProfile:
        """複数の記事からスタイルプロファイルを生成する（同期版）。

        Args:
            articles: 分析対象の記事テキストのリスト。
            author_name: 著者名。

        Returns:
            生成された StyleProfile。

        Raises:
            anthropic.APIError: API 呼び出しに失敗した場合。
            json.JSONDecodeError: レスポンスの JSON パースに失敗した場合。
        """
        if not articles:
            logger.warning("分析対象の記事が0件です。空のプロファイルを返します。")
            return StyleProfile(name=author_name)

        # 記事テキストを番号付きで結合
        articles_text = "\n\n".join(
            f"--- 記事 {i + 1} ---\n{article}"
            for i, article in enumerate(articles)
        )

        # テンプレートに値を埋め込み（JSON 例示中の波括弧を保護）
        user_prompt = self._render_template(
            self._template, articles=articles_text
        )

        logger.info(
            "スタイル分析を開始: 著者=%s, 記事数=%d", author_name, len(articles)
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system="あなたは文体分析の専門家です。与えられた記事群から著者の文体的特徴を正確に抽出してください。必ずJSON形式で回答してください。",
                messages=[{"role": "user", "content": user_prompt}],
            )
        except anthropic.APIError as e:
            logger.error("Claude API 呼び出しに失敗しました: %s", e)
            raise

        response_text = response.content[0].text

        # JSON 部分を抽出（コードブロックで囲まれている場合に対応）
        profile_data = self._extract_json(response_text)

        logger.info("スタイル分析が完了しました: 著者=%s", author_name)
        return StyleProfile(name=author_name, profile_data=profile_data)

    # ------------------------------------------------------------------
    # 内部ヘルパー
    # ------------------------------------------------------------------

    @staticmethod
    def _render_template(template: str, **kwargs: object) -> str:
        """テンプレート文字列にパラメータを安全に埋め込む。

        既知のプレースホルダーのみを置換し、JSON 例示中の波括弧は残す。

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
            return match.group(0)

        return re.sub(r"\{(\w+)\}", _replacer, template)

    @staticmethod
    def _extract_json(text: str) -> dict:
        """テキストから JSON オブジェクトを抽出してパースする。

        コードブロック (```json ... ```) で囲まれている場合にも対応する。

        Args:
            text: Claude API のレスポンステキスト。

        Returns:
            パースされた辞書。

        Raises:
            json.JSONDecodeError: JSON のパースに失敗した場合。
        """
        # ```json ... ``` ブロックの除去
        cleaned = text.strip()
        if cleaned.startswith("```"):
            # 最初の改行までを除去（```json 等）
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[: cleaned.rfind("```")]
        cleaned = cleaned.strip()

        # JSON の開始位置を探す（先頭テキストがある場合への対応）
        brace_start = cleaned.find("{")
        if brace_start > 0:
            cleaned = cleaned[brace_start:]

        return json.loads(cleaned)
