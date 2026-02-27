"""
Markdown出力モジュール

生成した記事をYAMLフロントマター付きのMarkdownファイルとして出力し、
出力ディレクトリの管理を行う。
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


class MarkdownWriter:
    """生成記事をMarkdownファイルとして出力する。

    YAMLフロントマター付きのMarkdownファイルを生成し、
    タイムスタンプ付きのファイル名で保存する。
    """

    def __init__(self, output_dir: str = "data/output") -> None:
        """MarkdownWriter を初期化する。

        Args:
            output_dir: 出力先ディレクトリのパス。
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_article(
        self,
        title: str,
        body: str,
        hashtags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> Path:
        """記事をMarkdownファイルとして書き出す。

        YAML フロントマターにタイトル、ハッシュタグ、生成日時、
        文字数、ステータスを含め、本文を続けて出力する。

        Args:
            title: 記事タイトル。
            body: 記事本文（Markdown形式）。
            hashtags: ハッシュタグのリスト。
            metadata: 追加メタデータの辞書。

        Returns:
            出力されたファイルのパス。
        """
        now = datetime.now()
        hashtags = hashtags or []
        metadata = metadata or {}

        # フロントマターの構築
        frontmatter = {
            "title": title,
            "hashtags": hashtags,
            "generated_at": now.isoformat(timespec="seconds"),
            "word_count": len(body),
            "status": "draft",
        }
        # 追加メタデータをマージ
        frontmatter.update(metadata)

        # YAML フロントマター + 本文
        yaml_str = yaml.dump(
            frontmatter,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
        content = f"---\n{yaml_str}---\n\n{body}\n"

        # ファイル名の生成: YYYYMMDD_HHMMSS_{sanitized_title}.md
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        safe_title = self._sanitize_filename(title)
        filename = f"{timestamp}_{safe_title}.md"

        output_path = self.output_dir / filename

        try:
            output_path.write_text(content, encoding="utf-8")
            logger.info("記事を出力しました: %s", output_path)
            return output_path
        except OSError as e:
            logger.error("ファイル書き込みエラー: %s - %s", output_path, e)
            # ファイル名を簡略化してリトライ
            fallback_filename = f"{timestamp}_article.md"
            fallback_path = self.output_dir / fallback_filename
            fallback_path.write_text(content, encoding="utf-8")
            logger.info("フォールバックファイル名で出力しました: %s", fallback_path)
            return fallback_path

    def _sanitize_filename(self, title: str) -> str:
        """タイトルをファイル名として安全な文字列に変換する。

        - ファイル名に使用できない文字を除去
        - Unicode正規化（NFC）
        - 最大50文字に制限
        - 空になった場合は "untitled" を返す

        Args:
            title: 元のタイトル文字列。

        Returns:
            サニタイズされたファイル名文字列。
        """
        # Unicode正規化
        sanitized = unicodedata.normalize("NFC", title)

        # ファイル名に使えない文字を除去/置換
        sanitized = re.sub(r'[\\/:*?"<>|\s]+', "_", sanitized)

        # 先頭・末尾のアンダースコアとドットを除去
        sanitized = sanitized.strip("_.")

        # 長さ制限
        if len(sanitized) > 50:
            sanitized = sanitized[:50].rstrip("_.")

        # 空文字チェック
        if not sanitized:
            sanitized = "untitled"

        return sanitized

    def write_batch(self, articles: list[dict]) -> list[Path]:
        """複数記事を一括出力する。

        Args:
            articles: 記事辞書のリスト。各辞書は以下のキーを含む:
                - title (str): 記事タイトル（必須）
                - body (str): 記事本文（必須）
                - hashtags (list[str], optional): ハッシュタグ
                - metadata (dict, optional): 追加メタデータ

        Returns:
            出力されたファイルパスのリスト。
        """
        paths: list[Path] = []

        for i, article in enumerate(articles):
            try:
                title = article.get("title", f"無題_{i + 1}")
                body = article.get("body", "")
                hashtags = article.get("hashtags")
                metadata = article.get("metadata")

                path = self.write_article(
                    title=title,
                    body=body,
                    hashtags=hashtags,
                    metadata=metadata,
                )
                paths.append(path)

            except Exception as e:
                logger.error(
                    "記事の出力に失敗しました (index=%d, title=%s): %s",
                    i,
                    article.get("title", "unknown"),
                    e,
                )

        logger.info("%d / %d 件の記事を出力しました", len(paths), len(articles))
        return paths


class ExportManager:
    """出力ディレクトリの管理。

    バッチ出力用ディレクトリの作成、出力ファイル一覧の取得、
    出力サマリーの集計を行う。
    """

    def __init__(self, base_dir: str = "data/output") -> None:
        """ExportManager を初期化する。

        Args:
            base_dir: 出力のベースディレクトリパス。
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_batch_dir(self, batch_name: str | None = None) -> Path:
        """バッチ出力用ディレクトリを作成する。

        Args:
            batch_name: バッチ名。None の場合はタイムスタンプベースの名前を使用。
                Format: batch_YYYYMMDD_HHMMSS/

        Returns:
            作成されたディレクトリのパス。
        """
        if batch_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            batch_name = f"batch_{timestamp}"

        batch_dir = self.base_dir / batch_name
        batch_dir.mkdir(parents=True, exist_ok=True)
        logger.info("バッチディレクトリを作成しました: %s", batch_dir)
        return batch_dir

    def list_outputs(self) -> list[Path]:
        """出力済みMarkdownファイルの一覧を返す。

        ベースディレクトリ内を再帰的に探索し、
        更新日時の新しい順にソートして返す。

        Returns:
            Markdownファイルパスのリスト（更新日時の降順）。
        """
        if not self.base_dir.exists():
            return []

        files = list(self.base_dir.rglob("*.md"))
        # 更新日時の降順でソート
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files

    def get_summary(self) -> dict:
        """出力サマリーを返す。

        Returns:
            以下のキーを含む辞書:
            - total_files (int): 総ファイル数
            - total_chars (int): 総文字数（本文のみ）
            - oldest (str | None): 最も古いファイルのタイムスタンプ
            - newest (str | None): 最も新しいファイルのタイムスタンプ
            - files (list[dict]): 各ファイルの基本情報
        """
        files = self.list_outputs()

        if not files:
            return {
                "total_files": 0,
                "total_chars": 0,
                "oldest": None,
                "newest": None,
                "files": [],
            }

        total_chars = 0
        file_info_list: list[dict] = []

        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8")
                # フロントマターを除いた本文の文字数を取得
                body = self._extract_body(content)
                char_count = len(body)
                total_chars += char_count

                file_info_list.append(
                    {
                        "path": str(file_path),
                        "name": file_path.name,
                        "chars": char_count,
                        "modified": datetime.fromtimestamp(
                            file_path.stat().st_mtime
                        ).isoformat(timespec="seconds"),
                    }
                )
            except OSError as e:
                logger.warning("ファイル読み込みエラー: %s - %s", file_path, e)

        return {
            "total_files": len(files),
            "total_chars": total_chars,
            "oldest": file_info_list[-1]["modified"] if file_info_list else None,
            "newest": file_info_list[0]["modified"] if file_info_list else None,
            "files": file_info_list,
        }

    def _extract_body(self, content: str) -> str:
        """Markdownコンテンツからフロントマターを除いた本文を抽出する。

        Args:
            content: YAMLフロントマター付きMarkdownコンテンツ。

        Returns:
            フロントマターを除いた本文。
        """
        if content.startswith("---"):
            # 2つ目の --- を探す
            end_idx = content.find("---", 3)
            if end_idx != -1:
                return content[end_idx + 3 :].strip()
        return content.strip()
