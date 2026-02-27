"""
設定管理モジュール

環境変数と .env ファイルからアプリケーション設定を読み込む。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """アプリケーション全体の設定を保持するデータクラス。

    frozen=True により、設定値の不変性を保証する。
    """

    # --- API設定 ---
    anthropic_api_key: str
    model_name: str
    review_model: str

    # --- ファイルパス ---
    db_path: str
    output_dir: str
    sources_dir: str

    # --- note.com API ---
    note_api_base: str

    # --- リクエスト制御 ---
    request_delay: float
    max_retries: int

    # --- 記事パラメータ ---
    article_min_length: int
    article_max_length: int

    @classmethod
    def from_env(cls, env_path: str | Path | None = None) -> Settings:
        """環境変数から設定を読み込んでインスタンスを生成する。

        Args:
            env_path: .env ファイルのパス。None の場合はカレントディレクトリの .env を探す。

        Returns:
            Settings インスタンス。

        Raises:
            ValueError: 必須の環境変数が未設定の場合。
        """
        # .env ファイルを読み込む（存在する場合）
        if env_path is not None:
            load_dotenv(env_path)
        else:
            load_dotenv()

        # 必須: Anthropic APIキー
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY が設定されていません。"
                ".env ファイルまたは環境変数で設定してください。"
            )

        return cls(
            # API設定
            anthropic_api_key=api_key,
            model_name=os.getenv(
                "NOTE_GENERATOR_MODEL", "claude-sonnet-4-5-20250514"
            ),
            review_model=os.getenv(
                "NOTE_GENERATOR_REVIEW_MODEL", "claude-haiku-4-5-20251001"
            ),
            # ファイルパス
            db_path=os.getenv(
                "NOTE_GENERATOR_DB_PATH", "data/note_generator.db"
            ),
            output_dir=os.getenv("NOTE_GENERATOR_OUTPUT_DIR", "data/output"),
            sources_dir=os.getenv(
                "NOTE_GENERATOR_SOURCES_DIR", "data/sources"
            ),
            # note.com API
            note_api_base=os.getenv(
                "NOTE_API_BASE", "https://note.com/api/v2"
            ),
            # リクエスト制御
            request_delay=float(
                os.getenv("NOTE_GENERATOR_REQUEST_DELAY", "2.0")
            ),
            max_retries=int(os.getenv("NOTE_GENERATOR_MAX_RETRIES", "3")),
            # 記事パラメータ
            article_min_length=int(
                os.getenv("NOTE_GENERATOR_ARTICLE_MIN_LENGTH", "1500")
            ),
            article_max_length=int(
                os.getenv("NOTE_GENERATOR_ARTICLE_MAX_LENGTH", "3000")
            ),
        )

    def ensure_directories(self) -> None:
        """必要なディレクトリを作成する。"""
        for dir_path in [self.output_dir, self.sources_dir]:
            Path(dir_path).mkdir(parents=True, exist_ok=True)

        # DBファイルの親ディレクトリも作成
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
