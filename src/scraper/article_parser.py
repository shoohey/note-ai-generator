"""
記事パーサー

note.com API v2 レスポンスおよび HTML ページから
NoteArticle オブジェクトを生成するモジュール。
"""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup
from rich.console import Console

from .models import ArticleMetrics, NoteArticle

console = Console()


class ArticleParser:
    """note.com 記事の解析を行うパーサークラス。

    API v2 の JSON レスポンスと HTML ページの両方に対応する。
    すべてのメソッドは staticmethod として提供する。
    """

    # ------------------------------------------------------------------
    # API レスポンス → NoteArticle
    # ------------------------------------------------------------------

    @staticmethod
    def parse_api_response(data: dict[str, Any]) -> NoteArticle:
        """API v2 レスポンスの辞書から NoteArticle を生成する。

        Args:
            data: API レスポンスの記事データ辞書。
                  ``/api/v2/notes/{key}`` の ``data`` フィールドに相当。

        Returns:
            解析済み NoteArticle インスタンス。
        """
        # ハッシュタグ抽出
        hashtags: list[str] = []
        hashtag_list = data.get("hashtag_notes") or data.get("hashtags") or []
        for tag_entry in hashtag_list:
            if isinstance(tag_entry, dict):
                tag_name = tag_entry.get("hashtag", {}).get("name", "")
                if tag_name:
                    hashtags.append(tag_name)
            elif isinstance(tag_entry, str):
                hashtags.append(tag_entry)

        # メトリクス
        metrics = ArticleMetrics(
            like_count=int(data.get("like_count", 0) or 0),
            comment_count=int(data.get("comment_count", 0) or 0),
        )

        # ユーザー情報
        user = data.get("user") or {}
        author = user.get("nickname") or user.get("urlname") or "unknown"

        # URL の組み立て
        urlname = user.get("urlname", "")
        note_key = data.get("key") or data.get("id", "")
        url = data.get("note_url") or f"https://note.com/{urlname}/n/{note_key}"

        # 本文（body が含まれない一覧 API もあるため空文字許容）
        body = data.get("body") or ""

        # 公開日時
        published_at = (
            data.get("publish_at")
            or data.get("created_at")
            or data.get("published_at")
            or ""
        )

        return NoteArticle(
            id=str(data.get("id", note_key)),
            title=data.get("name", ""),
            body=body,
            author=author,
            url=url,
            published_at=published_at,
            metrics=metrics,
            hashtags=hashtags,
            note_type=data.get("type", "TextNote"),
        )

    # ------------------------------------------------------------------
    # HTML → NoteArticle
    # ------------------------------------------------------------------

    @staticmethod
    def parse_html(html: str, url: str) -> NoteArticle | None:
        """HTML ページから NoteArticle を解析する（フォールバック用）。

        JSON-LD (``<script type="application/ld+json">``) を優先的に利用し、
        取得できない場合は HTML 構造から情報を抽出する。

        Args:
            html: 記事ページの HTML 文字列。
            url: 記事ページの URL。

        Returns:
            解析成功時は NoteArticle、失敗時は None。
        """
        if not html:
            return None

        soup = BeautifulSoup(html, "lxml")

        # --- 1) JSON-LD から抽出を試みる ---
        article = ArticleParser._parse_json_ld(soup, url)
        if article is not None:
            console.log("[green]JSON-LD からの解析に成功[/green]")
            return article

        # --- 2) HTML 構造からフォールバック抽出 ---
        console.log("[yellow]JSON-LD が見つからず、HTML 構造から解析[/yellow]")
        return ArticleParser._parse_html_structure(soup, url)

    @staticmethod
    def _parse_json_ld(
        soup: BeautifulSoup, url: str
    ) -> NoteArticle | None:
        """JSON-LD スクリプトタグから記事情報を抽出する。"""
        ld_scripts = soup.find_all("script", type="application/ld+json")

        for script in ld_scripts:
            try:
                ld_data = json.loads(script.string or "")
            except (json.JSONDecodeError, TypeError):
                continue

            # @type が Article / BlogPosting / NewsArticle の場合
            ld_type = ld_data.get("@type", "")
            if ld_type not in ("Article", "BlogPosting", "NewsArticle"):
                continue

            # 本文の取得
            body = ArticleParser._extract_body_from_soup(soup)

            # 著者
            author_data = ld_data.get("author", {})
            if isinstance(author_data, dict):
                author = author_data.get("name", "unknown")
            elif isinstance(author_data, list) and author_data:
                author = author_data[0].get("name", "unknown")
            else:
                author = str(author_data) if author_data else "unknown"

            return NoteArticle(
                id=ArticleParser._extract_note_id(url),
                title=ld_data.get("headline", ""),
                body=body,
                author=author,
                url=url,
                published_at=ld_data.get("datePublished", ""),
                metrics=ArticleMetrics(),  # HTML からメトリクスを取得するのは困難
                hashtags=ArticleParser._extract_hashtags_from_soup(soup),
                note_type="TextNote",
            )

        return None

    @staticmethod
    def _parse_html_structure(
        soup: BeautifulSoup, url: str
    ) -> NoteArticle | None:
        """HTML の DOM 構造から記事情報を抽出する。"""
        # タイトル
        title_elem = (
            soup.select_one("h1.o-noteContentHeader__title")
            or soup.select_one('h1[class*="title"]')
            or soup.find("h1")
        )
        title = title_elem.get_text(strip=True) if title_elem else ""

        if not title:
            # タイトルすら取れなければ解析失敗とみなす
            console.log("[red]HTML からタイトルを抽出できません[/red]")
            return None

        # 本文
        body = ArticleParser._extract_body_from_soup(soup)

        # 著者
        author_elem = (
            soup.select_one('a[class*="author"]')
            or soup.select_one('span[class*="creator"]')
            or soup.select_one('meta[name="author"]')
        )
        if author_elem:
            author = (
                author_elem.get("content")  # type: ignore[arg-type]
                or author_elem.get_text(strip=True)
            )
        else:
            author = "unknown"

        # 公開日時
        time_elem = soup.find("time")
        published_at = ""
        if time_elem:
            published_at = time_elem.get("datetime", "") or time_elem.get_text(strip=True)  # type: ignore[assignment]

        return NoteArticle(
            id=ArticleParser._extract_note_id(url),
            title=title,
            body=body,
            author=str(author),
            url=url,
            published_at=str(published_at),
            metrics=ArticleMetrics(),
            hashtags=ArticleParser._extract_hashtags_from_soup(soup),
            note_type="TextNote",
        )

    # ------------------------------------------------------------------
    # 記事構造分析
    # ------------------------------------------------------------------

    @staticmethod
    def extract_structure(article: NoteArticle) -> dict[str, Any]:
        """記事の構造を分析して辞書で返す。

        Args:
            article: 分析対象の NoteArticle。

        Returns:
            以下のキーを含む辞書:
                - heading_count: 見出し (h1-h6) の数
                - paragraph_count: 段落 (<p>) の数
                - has_list: リスト要素を含むか
                - has_quote: 引用要素を含むか
                - has_image: 画像を含むか
                - opening_style: 冒頭スタイルの分類
                - closing_style: 締めスタイルの分類
                - avg_paragraph_length: 平均段落文字数
        """
        soup = BeautifulSoup(article.body, "html.parser")

        # 見出し
        headings = soup.find_all(re.compile(r"^h[1-6]$"))
        heading_count = len(headings)

        # 段落
        paragraphs = soup.find_all("p")
        paragraph_texts = [
            p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)
        ]
        paragraph_count = len(paragraph_texts)

        # 平均段落文字数
        avg_paragraph_length = 0.0
        if paragraph_texts:
            avg_paragraph_length = sum(len(t) for t in paragraph_texts) / len(
                paragraph_texts
            )

        # リスト・引用・画像
        has_list = bool(soup.find(["ul", "ol"]))
        has_quote = bool(soup.find("blockquote"))
        has_image = bool(soup.find("img"))

        # 冒頭・締めスタイル
        plain = article.plain_text
        lines = [line.strip() for line in plain.split("\n") if line.strip()]

        opening_style = ArticleParser._classify_opening(lines)
        closing_style = ArticleParser._classify_closing(lines)

        return {
            "heading_count": heading_count,
            "paragraph_count": paragraph_count,
            "has_list": has_list,
            "has_quote": has_quote,
            "has_image": has_image,
            "opening_style": opening_style,
            "closing_style": closing_style,
            "avg_paragraph_length": round(avg_paragraph_length, 1),
        }

    # ------------------------------------------------------------------
    # ヘルパーメソッド（内部用）
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_body_from_soup(soup: BeautifulSoup) -> str:
        """BeautifulSoup オブジェクトから本文 HTML を抽出する。"""
        body_selectors = [
            "div.note-common-styles__textnote-body",
            "div.p-article__body",
            'div[class*="note-body"]',
            "article",
        ]
        for selector in body_selectors:
            elem = soup.select_one(selector)
            if elem:
                return str(elem)
        return ""

    @staticmethod
    def _extract_hashtags_from_soup(soup: BeautifulSoup) -> list[str]:
        """HTML から ハッシュタグを抽出する。"""
        hashtags: list[str] = []

        # note.com のハッシュタグリンクを探索
        tag_links = soup.select('a[href*="/hashtag/"]')
        for link in tag_links:
            tag_text = link.get_text(strip=True).lstrip("#")
            if tag_text:
                hashtags.append(tag_text)

        return hashtags

    @staticmethod
    def _extract_note_id(url: str) -> str:
        """URL から note ID を抽出する。"""
        # https://note.com/{user}/n/{key} → key を返す
        match = re.search(r"/n/([a-zA-Z0-9]+)", url)
        if match:
            return match.group(1)

        # フォールバック: URL 末尾のパス要素
        parts = url.rstrip("/").split("/")
        return parts[-1] if parts else "unknown"

    @staticmethod
    def _classify_opening(lines: list[str]) -> str:
        """冒頭数行からスタイルを分類する。"""
        if not lines:
            return "不明"

        opening = lines[0]

        # 問いかけパターン
        if re.search(r"[？\?]$", opening) or re.search(
            r"(ですか|ませんか|でしょうか|だろうか)", opening
        ):
            return "問いかけ"

        # 名言引用パターン（カギ括弧で始まる）
        if re.match(r'^[「『""\'"]', opening):
            return "名言引用"

        # 体験談パターン
        if re.match(r"^(私は|僕は|わたしは|ぼくは|自分は)", opening):
            return "体験談"

        # 挨拶パターン
        if re.match(r"^(こんにちは|はじめまして|どうも|お久しぶり)", opening):
            return "挨拶"

        # 宣言パターン
        if re.search(r"(します|しました|です。|ます。)$", opening):
            return "宣言"

        # 数字・データ開始
        if re.match(r"^[0-9０-９]", opening):
            return "データ提示"

        return "その他"

    @staticmethod
    def _classify_closing(lines: list[str]) -> str:
        """末尾数行からスタイルを分類する。"""
        if not lines:
            return "不明"

        closing = lines[-1]

        # 行動喚起
        if re.search(
            r"(してみてください|しましょう|始めてみ|やってみ|挑戦して)", closing
        ):
            return "行動喚起"

        # まとめ
        if re.search(r"(まとめ|以上|おわりに|最後に)", closing):
            return "まとめ"

        # 問いかけ
        if re.search(r"[？\?]$", closing) or re.search(
            r"(ですか|ませんか|でしょうか)", closing
        ):
            return "問いかけ"

        # 感謝
        if re.search(r"(ありがとう|感謝|読んでいただ)", closing):
            return "感謝"

        # 宣伝・告知
        if re.search(r"(フォロー|スキ|いいね|シェア|コメント)", closing):
            return "宣伝"

        # 余韻
        if re.search(r"[。…]+$", closing) and len(closing) < 30:
            return "余韻"

        return "その他"
