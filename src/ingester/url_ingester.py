"""
ブログURL取り込みモジュール

Web上のブログ記事URLからコンテンツを取得し、
SourceContent オブジェクトに変換する。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

from src.ingester.base import ContentIngester
from src.scraper.models import SourceContent

logger = logging.getLogger(__name__)

# コンテンツ抽出時に除去するタグ
_REMOVE_TAGS: set[str] = {
    "script",
    "style",
    "nav",
    "footer",
    "header",
    "aside",
    "iframe",
    "noscript",
}


class URLIngester(ContentIngester):
    """ブログURLからコンテンツを取り込む。

    単一のURLまたはURL一覧ファイル（1行1URL）を受け付け、
    各URLのメインコンテンツを抽出する。
    """

    def __init__(self, request_delay: float = 1.0, timeout: int = 30) -> None:
        """URLIngester を初期化する。

        Args:
            request_delay: リクエスト間の待機秒数。
            timeout: HTTP リクエストのタイムアウト秒数。
        """
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ja,en;q=0.9",
            }
        )
        self.request_delay = request_delay
        self.timeout = timeout
        self.last_request_time: float = 0.0

    def ingest(self, source: str) -> list[SourceContent]:
        """URLからコンテンツを取り込む。

        Args:
            source: 単一のURL、またはURL一覧ファイルパス（.txt、1行1URL）。

        Returns:
            取り込まれた SourceContent のリスト。
        """
        urls = self._resolve_source(source)
        results: list[SourceContent] = []

        for url in urls:
            content = self._fetch_url(url)
            if content is not None:
                results.append(content)

        logger.info(
            "%d / %d 件のURLからコンテンツを取り込みました",
            len(results),
            len(urls),
        )
        return results

    def _resolve_source(self, source: str) -> list[str]:
        """ソース文字列をURLリストに変換する。

        Args:
            source: URLまたはURL一覧ファイルパス。

        Returns:
            URLのリスト。
        """
        # URLの場合はそのまま返す
        if source.startswith(("http://", "https://")):
            return [source]

        # ファイルパスの場合はURL一覧として読み込む
        path = Path(source)
        if path.is_file() and path.suffix.lower() == ".txt":
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
                urls = [
                    line.strip()
                    for line in lines
                    if line.strip() and line.strip().startswith(("http://", "https://"))
                ]
                if not urls:
                    logger.warning("URL一覧ファイルに有効なURLが含まれていません: %s", source)
                return urls
            except OSError as e:
                logger.error("URL一覧ファイルの読み込みに失敗しました: %s - %s", source, e)
                return []

        logger.warning(
            "URLでもURL一覧ファイルでもありません: %s", source
        )
        return []

    def _fetch_url(self, url: str) -> SourceContent | None:
        """1つのURLからコンテンツを取得する。

        Args:
            url: 取得対象のURL。

        Returns:
            SourceContent オブジェクト。取得失敗時は None。
        """
        self._rate_limit()

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            # エンコーディング推定の改善
            if response.encoding and response.encoding.lower() == "iso-8859-1":
                response.encoding = response.apparent_encoding

            soup = BeautifulSoup(response.text, "html.parser")

            # 不要な要素を除去
            self._clean_soup(soup)

            # タイトルの抽出
            title = self._extract_title(soup)

            # メインコンテンツの抽出
            main_content = self._extract_main_content(soup)

            if not main_content.strip():
                logger.warning("コンテンツが空です: %s", url)
                return None

            return SourceContent(
                id=self._generate_id(),
                content_type="blog",
                title=title,
                content=main_content,
                url=url,
                metadata={
                    "status_code": response.status_code,
                    "content_length": len(main_content),
                    "encoding": response.encoding or "unknown",
                },
            )

        except requests.exceptions.Timeout:
            logger.error("リクエストタイムアウト: %s", url)
            return None
        except requests.exceptions.HTTPError as e:
            logger.error("HTTPエラー: %s - %s", url, e)
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error("接続エラー: %s - %s", url, e)
            return None
        except requests.exceptions.RequestException as e:
            logger.error("リクエストエラー: %s - %s", url, e)
            return None
        except Exception as e:
            logger.error("予期しないエラー: %s - %s", url, e)
            return None

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """ページタイトルを抽出する。

        <h1> タグを優先し、なければ <title> タグから取得する。

        Args:
            soup: パース済みの BeautifulSoup オブジェクト。

        Returns:
            タイトル文字列。取得できない場合は "無題"。
        """
        # h1 タグを優先
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)

        # title タグにフォールバック
        title_tag = soup.find("title")
        if title_tag and title_tag.get_text(strip=True):
            return title_tag.get_text(strip=True)

        return "無題"

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """メインコンテンツを抽出する。

        article > main > body の優先順位で探索し、
        最初に見つかった要素のテキストを返す。

        Args:
            soup: パース済みの BeautifulSoup オブジェクト。

        Returns:
            抽出されたテキストコンテンツ。
        """
        # 優先順位: article > main > body
        for tag_name in ("article", "main", "body"):
            element = soup.find(tag_name)
            if element and isinstance(element, Tag):
                text = element.get_text(separator="\n", strip=True)
                if text:
                    return text

        # どれも見つからない場合はページ全体のテキスト
        return soup.get_text(separator="\n", strip=True)

    def _clean_soup(self, soup: BeautifulSoup) -> None:
        """不要な要素を BeautifulSoup オブジェクトから除去する。

        script, style, nav, footer などのタグを削除して
        メインコンテンツの抽出精度を向上させる。

        Args:
            soup: クリーンアップ対象の BeautifulSoup オブジェクト。
        """
        for tag_name in _REMOVE_TAGS:
            for element in soup.find_all(tag_name):
                element.decompose()

    def _rate_limit(self) -> None:
        """リクエスト間隔を制御する。

        前回のリクエストから request_delay 秒が経過していない場合、
        残りの時間だけスリープする。
        """
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.request_delay:
            wait_time = self.request_delay - elapsed
            logger.debug("レート制限: %.2f 秒待機", wait_time)
            time.sleep(wait_time)
        self.last_request_time = time.time()
