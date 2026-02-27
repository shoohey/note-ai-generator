"""
記事生成モジュール

Claude API を使って note.com 向け記事を生成するコアモジュール。
プロンプトキャッシングを活用してシステムプロンプトの再利用を効率化する。
"""

from __future__ import annotations

import json
import logging
import re
import time

import anthropic

from src.scraper.models import WritingPattern

from .prompt_builder import PromptBuilder
from .style_profile import StyleProfile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

_DEFAULT_MAX_TOKENS = 4096
_RETRY_BASE_DELAY = 2.0  # リトライ時の基本待機秒数
_MAX_RETRIES = 3


# ---------------------------------------------------------------------------
# ArticleGenerator
# ---------------------------------------------------------------------------


class ArticleGenerator:
    """Claude API を使って note.com 記事を生成する。

    プロンプトキャッシング（``cache_control``）を活用し、
    同一システムプロンプトを再利用することで API コストを削減する。
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5-20250514",
        prompts_dir: str = "prompts",
    ) -> None:
        """ArticleGenerator を初期化する。

        Args:
            api_key: Anthropic API キー。
            model: 使用する Claude モデルの ID。
            prompts_dir: プロンプトテンプレートのディレクトリパス。
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.prompt_builder = PromptBuilder(prompts_dir)

    # ------------------------------------------------------------------
    # 記事生成
    # ------------------------------------------------------------------

    def generate_article(
        self,
        topic: str,
        source_content: str,
        style_profile: StyleProfile | None = None,
        writing_pattern: WritingPattern | None = None,
        target_length: int = 2000,
        min_length: int = 1500,
        max_length: int = 3000,
    ) -> dict:
        """記事を1つ生成する。

        Args:
            topic: 記事のトピック。
            source_content: 参考コンテンツ。
            style_profile: 著者のスタイルプロファイル（オプション）。
            writing_pattern: 書き方パターン（オプション）。
            target_length: 文字数目標。
            min_length: 最小文字数。
            max_length: 最大文字数。

        Returns:
            生成結果の辞書::

                {
                    "title": str,
                    "body": str,
                    "hashtags": list[str],
                    "word_count": int,
                }

        Raises:
            anthropic.APIError: API 呼び出しに失敗した場合（リトライ超過後）。
            ValueError: レスポンスのパースに失敗した場合。
        """
        # 1. システムプロンプトを構築（層1-3）
        system_prompt = self.prompt_builder.build_system_prompt(
            style_profile=style_profile,
            writing_pattern=writing_pattern,
        )

        # 2. スタイル指示文を取得
        style_instructions = ""
        if style_profile is not None:
            style_instructions = style_profile.get_writing_instructions()

        # 3. 書き方パターンのテキスト化
        writing_pattern_text = ""
        if writing_pattern is not None:
            writing_pattern_text = PromptBuilder._format_writing_pattern(
                writing_pattern
            )

        # 4. ユーザープロンプトを構築（層4-5）
        user_prompt = self.prompt_builder.build_generation_prompt(
            topic=topic,
            source_content=source_content,
            target_length=target_length,
            min_length=min_length,
            max_length=max_length,
            style_instructions=style_instructions,
            writing_pattern=writing_pattern_text,
        )

        # 5. API 呼び出し
        logger.info("記事生成を開始: topic=%s", topic)
        response_text = self._call_api(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=_DEFAULT_MAX_TOKENS,
        )

        # 6. レスポンスをパース
        result = self._parse_article_response(response_text)
        logger.info(
            "記事生成が完了: title=%s, word_count=%d",
            result["title"],
            result["word_count"],
        )
        return result

    # ------------------------------------------------------------------
    # トピック抽出
    # ------------------------------------------------------------------

    def extract_topics(self, content: str, count: int = 10) -> list[dict]:
        """コンテンツからトピックを抽出する。

        Args:
            content: 分析対象のコンテンツ。
            count: 抽出するトピック数。

        Returns:
            トピック辞書のリスト。各辞書は以下のキーを含む::

                {
                    "topic": str,
                    "angle": str,
                    "hook": str,
                    "reason": str,
                    "suggested_title": str,
                }

        Raises:
            anthropic.APIError: API 呼び出しに失敗した場合。
            json.JSONDecodeError: レスポンスの JSON パースに失敗した場合。
        """
        user_prompt = self.prompt_builder.build_topic_extraction_prompt(
            content=content, count=count
        )

        system_prompt = (
            "あなたはnote.comのコンテンツ戦略の専門家です。"
            "読者に刺さるトピックを的確に見つけ出すことができます。"
            "必ずJSON配列形式で回答してください。"
        )

        logger.info("トピック抽出を開始: count=%d", count)
        response_text = self._call_api(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=2048,
        )

        topics = self._extract_json_array(response_text)
        logger.info("トピック抽出が完了: %d件", len(topics))
        return topics

    # ------------------------------------------------------------------
    # レスポンスパース
    # ------------------------------------------------------------------

    def _parse_article_response(self, response_text: str) -> dict:
        """生成結果をパースしてタイトル・本文・ハッシュタグを分離する。

        期待するフォーマット::

            TITLE: 記事タイトル
            HASHTAGS: ハッシュタグ1, ハッシュタグ2, ...
            ---
            本文（Markdown形式）

        Args:
            response_text: Claude API のレスポンステキスト。

        Returns:
            パース結果の辞書。

        Raises:
            ValueError: 期待するフォーマットで出力されていない場合。
        """
        title = ""
        hashtags: list[str] = []
        body = ""

        lines = response_text.strip().split("\n")

        # セパレータ（---）の位置を探す
        separator_idx = -1
        for i, line in enumerate(lines):
            if line.strip() == "---":
                separator_idx = i
                break

        if separator_idx == -1:
            # セパレータがない場合: ヘッダー行を先頭から探して残りを本文とする
            logger.warning(
                "セパレータ '---' が見つかりません。フォールバックパースを実行します。"
            )
            body_start = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("TITLE:"):
                    title = stripped[len("TITLE:"):].strip()
                    body_start = i + 1
                elif stripped.startswith("HASHTAGS:"):
                    hashtags = self._parse_hashtags(
                        stripped[len("HASHTAGS:"):].strip()
                    )
                    body_start = i + 1
                else:
                    # ヘッダーでない行に到達したら本文開始
                    break
            body = "\n".join(lines[body_start:]).strip()
        else:
            # セパレータがある場合: ヘッダー部とボディ部を分離
            header_lines = lines[:separator_idx]
            body = "\n".join(lines[separator_idx + 1 :]).strip()

            for line in header_lines:
                stripped = line.strip()
                if stripped.startswith("TITLE:"):
                    title = stripped[len("TITLE:"):].strip()
                elif stripped.startswith("HASHTAGS:"):
                    hashtags = self._parse_hashtags(
                        stripped[len("HASHTAGS:"):].strip()
                    )

        if not title:
            # タイトルが見つからない場合、本文の最初の見出しを使う
            heading_match = re.search(r"^#+\s+(.+)$", body, re.MULTILINE)
            if heading_match:
                title = heading_match.group(1).strip()
                logger.warning(
                    "TITLE 行が見つかりません。見出しから抽出: %s", title
                )
            else:
                title = "無題"
                logger.warning("タイトルを特定できませんでした。'無題' を使用します。")

        word_count = len(body)

        return {
            "title": title,
            "body": body,
            "hashtags": hashtags,
            "word_count": word_count,
        }

    @staticmethod
    def _parse_hashtags(hashtags_str: str) -> list[str]:
        """ハッシュタグ文字列をリストに変換する。

        ``ハッシュタグ1, ハッシュタグ2`` や ``#タグ1, #タグ2`` 等の形式に対応。
        角括弧 ``[...]`` で囲まれている場合も処理する。

        Args:
            hashtags_str: ハッシュタグの文字列。

        Returns:
            ハッシュタグのリスト（# プレフィックスなし）。
        """
        # 角括弧を除去
        cleaned = hashtags_str.strip("[]")

        # カンマまたは半角スペースで分割
        tags = re.split(r"[,、]\s*", cleaned)

        result: list[str] = []
        for tag in tags:
            tag = tag.strip().strip("#").strip()
            if tag:
                result.append(tag)
        return result

    # ------------------------------------------------------------------
    # API 呼び出し（プロンプトキャッシング付き）
    # ------------------------------------------------------------------

    def _call_api(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        """Claude API を呼び出す（プロンプトキャッシング活用）。

        システムプロンプトに ``cache_control`` を設定し、
        同一内容のシステムプロンプトを再利用した際のコスト削減を図る。
        レート制限エラー時にはエクスポネンシャルバックオフでリトライする。

        Args:
            system_prompt: システムプロンプト文字列。
            user_prompt: ユーザープロンプト文字列。
            max_tokens: 最大トークン数。

        Returns:
            Claude API のレスポンステキスト。

        Raises:
            anthropic.APIError: リトライ超過後も API 呼び出しに失敗した場合。
        """
        last_error: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=[
                        {
                            "type": "text",
                            "text": system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=[
                        {"role": "user", "content": user_prompt},
                    ],
                )
                return response.content[0].text

            except anthropic.RateLimitError as e:
                last_error = e
                wait_time = _RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "レート制限に達しました。%d秒後にリトライします "
                    "(attempt %d/%d)",
                    wait_time,
                    attempt + 1,
                    _MAX_RETRIES,
                )
                time.sleep(wait_time)

            except anthropic.APIStatusError as e:
                last_error = e
                # 5xx 系のサーバーエラーはリトライ対象
                if e.status_code >= 500:
                    wait_time = _RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        "サーバーエラー (HTTP %d)。%d秒後にリトライします "
                        "(attempt %d/%d)",
                        e.status_code,
                        wait_time,
                        attempt + 1,
                        _MAX_RETRIES,
                    )
                    time.sleep(wait_time)
                else:
                    # 4xx 系のクライアントエラーはリトライしない
                    logger.error("API クライアントエラー (HTTP %d): %s", e.status_code, e)
                    raise

            except anthropic.APIError as e:
                last_error = e
                logger.error("予期しない API エラー: %s", e)
                raise

        # リトライ超過
        logger.error("%d回のリトライ後も API 呼び出しに失敗しました。", _MAX_RETRIES)
        raise last_error  # type: ignore[misc]

    # ------------------------------------------------------------------
    # JSON 抽出ヘルパー
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_json_array(text: str) -> list[dict]:
        """テキストから JSON 配列を抽出してパースする。

        コードブロック (````json ... `````) で囲まれている場合にも対応する。

        Args:
            text: Claude API のレスポンステキスト。

        Returns:
            パースされた辞書のリスト。

        Raises:
            json.JSONDecodeError: JSON のパースに失敗した場合。
        """
        cleaned = text.strip()

        # ```json ... ``` ブロックの除去
        if cleaned.startswith("```"):
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[: cleaned.rfind("```")]
        cleaned = cleaned.strip()

        # JSON 配列の開始位置を探す
        bracket_start = cleaned.find("[")
        if bracket_start > 0:
            cleaned = cleaned[bracket_start:]

        # 末尾のゴミを除去（] の後ろ）
        bracket_end = cleaned.rfind("]")
        if bracket_end >= 0:
            cleaned = cleaned[: bracket_end + 1]

        return json.loads(cleaned)
