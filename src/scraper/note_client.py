"""
note.com API クライアント

note.com API v2 を利用して記事情報を取得するHTTPクライアント。
API が利用できない場合は HTML フォールバックを行う。
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote, urljoin

import requests
from rich.console import Console

console = Console()


class NoteClient:
    """note.com API v2 クライアント（HTMLフォールバック付き）。

    特徴:
        - リクエスト間隔のレート制限
        - 403/429 エラー時の指数バックオフリトライ
        - レスポンスキャッシュ
        - API 失敗時の HTML フォールバック
        - Rich コンソールによるログ出力
    """

    # note.com API v2 ベース URL
    DEFAULT_API_BASE = "https://note.com/api/v2"

    def __init__(
        self,
        request_delay: float = 2.0,
        max_retries: int = 3,
        api_base: str | None = None,
    ) -> None:
        """クライアントを初期化する。

        Args:
            request_delay: リクエスト間の最小待機秒数。
            max_retries: リトライ最大回数。
            api_base: API ベース URL。None の場合はデフォルト値を使用。
        """
        self.api_base = (api_base or self.DEFAULT_API_BASE).rstrip("/")
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.last_request_time: float = 0.0

        # セッション設定
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            }
        )

        # レスポンスキャッシュ（URL → レスポンス辞書）
        self._cache: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # レート制限
    # ------------------------------------------------------------------

    def _rate_limit(self) -> None:
        """前回リクエストからの経過時間を確認し、必要に応じて待機する。"""
        elapsed = time.monotonic() - self.last_request_time
        if elapsed < self.request_delay:
            wait = self.request_delay - elapsed
            console.log(f"[dim]レート制限: {wait:.1f}秒待機中...[/dim]")
            time.sleep(wait)

    # ------------------------------------------------------------------
    # 内部リクエストヘルパー
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> requests.Response | None:
        """レート制限・リトライ付きの HTTP リクエストを送信する。

        Args:
            method: HTTP メソッド ("GET" など)。
            url: リクエスト先 URL。
            params: クエリパラメータ。
            use_cache: キャッシュを利用するかどうか。

        Returns:
            成功時は Response オブジェクト、全リトライ失敗時は None。
        """
        # キャッシュ確認
        cache_key = f"{method}:{url}:{params}"
        if use_cache and cache_key in self._cache:
            console.log(f"[green]キャッシュヒット:[/green] {url}")
            return self._cache[cache_key]

        last_exception: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            self._rate_limit()
            try:
                console.log(
                    f"[blue]リクエスト ({attempt}/{self.max_retries}):[/blue] "
                    f"{method} {url}"
                )
                self.last_request_time = time.monotonic()

                response = self.session.request(
                    method, url, params=params, timeout=30
                )

                # 成功
                if response.ok:
                    if use_cache:
                        self._cache[cache_key] = response
                    return response

                # リトライ対象のステータスコード
                if response.status_code in (403, 429, 500, 502, 503):
                    backoff = self.request_delay * (2 ** (attempt - 1))
                    console.log(
                        f"[yellow]HTTP {response.status_code}: "
                        f"{backoff:.1f}秒後にリトライします[/yellow]"
                    )
                    time.sleep(backoff)
                    continue

                # その他のエラー（リトライしない）
                console.log(
                    f"[red]HTTP {response.status_code}: {url}[/red]"
                )
                return None

            except requests.RequestException as exc:
                last_exception = exc
                backoff = self.request_delay * (2 ** (attempt - 1))
                console.log(
                    f"[red]リクエストエラー ({attempt}/{self.max_retries}): "
                    f"{exc}[/red]"
                )
                if attempt < self.max_retries:
                    time.sleep(backoff)

        console.log(
            f"[red]最大リトライ回数到達: {url} "
            f"(最終エラー: {last_exception})[/red]"
        )
        return None

    # ------------------------------------------------------------------
    # クリエイター記事一覧
    # ------------------------------------------------------------------

    def get_creator_articles(
        self,
        creator_name: str,
        page: int = 1,
        per_page: int = 10,
    ) -> list[dict]:
        """クリエイターの記事一覧を取得する。

        Args:
            creator_name: note.com のクリエイター名（URL スラッグ）。
            page: ページ番号 (1-indexed)。
            per_page: 1ページあたりの取得件数。

        Returns:
            記事情報の辞書リスト。取得失敗時は空リスト。
        """
        url = f"{self.api_base}/creators/{quote(creator_name, safe='')}/contents"
        params = {"kind": "note", "page": page, "per_page": per_page}

        response = self._request("GET", url, params=params)
        if response is None:
            return []

        try:
            data = response.json()
            contents = data.get("data", {}).get("contents", [])
            console.log(
                f"[green]{creator_name} の記事 {len(contents)} 件取得[/green]"
            )
            return contents
        except (ValueError, KeyError) as exc:
            console.log(f"[red]レスポンス解析エラー: {exc}[/red]")
            return []

    # ------------------------------------------------------------------
    # 記事詳細
    # ------------------------------------------------------------------

    def get_article_detail(self, note_key: str) -> dict | None:
        """記事の詳細情報を取得する。

        Args:
            note_key: 記事の一意キー（URL のスラッグまたは数値ID）。

        Returns:
            記事詳細の辞書。取得失敗時は None。
        """
        url = f"{self.api_base}/notes/{quote(str(note_key), safe='')}"

        response = self._request("GET", url)
        if response is None:
            return None

        try:
            data = response.json()
            note_data = data.get("data", {})
            console.log(
                f"[green]記事詳細取得: {note_data.get('name', note_key)}[/green]"
            )
            return note_data
        except (ValueError, KeyError) as exc:
            console.log(f"[red]レスポンス解析エラー: {exc}[/red]")
            return None

    # ------------------------------------------------------------------
    # 記事本文
    # ------------------------------------------------------------------

    def get_article_body(self, note_key: str) -> str | None:
        """記事本文の HTML を取得する。

        まず API から取得を試み、失敗した場合は HTML フォールバックを行う。

        Args:
            note_key: 記事の一意キー。

        Returns:
            本文 HTML 文字列。取得失敗時は None。
        """
        # 1) API から取得を試みる
        detail = self.get_article_detail(note_key)
        if detail is not None:
            body = detail.get("body")
            if body:
                return body

        # 2) HTML フォールバック
        console.log("[yellow]APIから本文を取得できず、HTMLフォールバックを試行[/yellow]")
        article_url = f"https://note.com/n/{note_key}"
        return self._fetch_html_fallback(article_url)

    # ------------------------------------------------------------------
    # ハッシュタグ検索
    # ------------------------------------------------------------------

    def search_by_hashtag(
        self,
        hashtag: str,
        page: int = 1,
    ) -> list[dict]:
        """ハッシュタグで記事を検索する。

        robots.txt でブロックされる可能性があるため、
        エラー時は空リストを返却する。

        Args:
            hashtag: 検索するハッシュタグ（#なし）。
            page: ページ番号。

        Returns:
            検索結果の記事辞書リスト。エラー時は空リスト。
        """
        url = f"{self.api_base}/searches"
        params = {
            "q": hashtag,
            "context": "note",
            "mode": "tag",
            "page": page,
        }

        response = self._request("GET", url, params=params)
        if response is None:
            console.log(
                f"[yellow]ハッシュタグ検索失敗 (#{hashtag}): "
                f"robots.txt による制限の可能性[/yellow]"
            )
            return []

        try:
            data = response.json()
            notes = data.get("data", {}).get("notes", {}).get("contents", [])
            console.log(
                f"[green]ハッシュタグ '#{hashtag}' で {len(notes)} 件取得[/green]"
            )
            return notes
        except (ValueError, KeyError) as exc:
            console.log(f"[red]検索結果の解析エラー: {exc}[/red]")
            return []

    # ------------------------------------------------------------------
    # HTML フォールバック
    # ------------------------------------------------------------------

    def _fetch_html_fallback(self, url: str) -> str | None:
        """API 失敗時に HTML ページから本文を取得するフォールバック。

        Args:
            url: 記事の URL。

        Returns:
            抽出した本文 HTML。取得・解析失敗時は None。
        """
        # Accept ヘッダーを HTML 用に一時変更
        original_accept = self.session.headers.get("Accept", "")
        self.session.headers["Accept"] = "text/html"

        try:
            response = self._request("GET", url, use_cache=False)
            if response is None:
                return None

            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "lxml")

            # note.com の記事本文は class="note-common-styles__textnote-body"
            # または class="p-article__body" に格納されている
            body_selectors = [
                "div.note-common-styles__textnote-body",
                "div.p-article__body",
                'div[class*="note-body"]',
                "article",
            ]

            for selector in body_selectors:
                body_elem = soup.select_one(selector)
                if body_elem:
                    console.log(
                        f"[green]HTMLフォールバック成功: "
                        f"セレクタ '{selector}'[/green]"
                    )
                    return str(body_elem)

            console.log("[red]HTMLフォールバック: 本文要素が見つかりません[/red]")
            return None

        finally:
            self.session.headers["Accept"] = original_accept

    # ------------------------------------------------------------------
    # キャッシュ管理
    # ------------------------------------------------------------------

    def clear_cache(self) -> None:
        """レスポンスキャッシュをクリアする。"""
        self._cache.clear()
        console.log("[dim]キャッシュをクリアしました[/dim]")
