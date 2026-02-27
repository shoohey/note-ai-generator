"""
データベース管理モジュール

SQLiteデータベースの初期化・接続・クエリ実行を担当する。
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator


# スキーマファイルのパス（このファイルと同じディレクトリにある schema.sql）
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Database:
    """SQLiteデータベースの管理クラス。

    WALモードと外部キー制約を有効にした接続を提供する。

    使い方:
        db = Database("data/note_generator.db")
        db.initialize()

        rows = db.fetch_all("SELECT * FROM sources WHERE type = ?", ("pdf",))
    """

    def __init__(self, db_path: str | Path) -> None:
        """データベースを初期化する。

        Args:
            db_path: SQLiteデータベースファイルのパス。
        """
        self.db_path = Path(db_path)

    # ------------------------------------------------------------------
    # 初期化
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """データベースを初期化する。

        - 親ディレクトリが存在しなければ作成する
        - WALモードを有効化する
        - 外部キー制約を有効化する
        - schema.sql を実行してテーブルを作成する
        """
        # 親ディレクトリの作成
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # スキーマの読み込み
        schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")

        with self.get_connection() as conn:
            # WALモードと外部キー制約の有効化
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")

            # テーブル作成
            conn.executescript(schema_sql)
            conn.commit()

    # ------------------------------------------------------------------
    # 接続管理
    # ------------------------------------------------------------------

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """データベース接続のコンテキストマネージャ。

        接続時にWALモードと外部キー制約を有効化する。
        行は辞書風にアクセスできる sqlite3.Row を返す。

        Yields:
            sqlite3.Connection: データベース接続。

        使い方:
            with db.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM sources")
                rows = cursor.fetchall()
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # クエリヘルパー
    # ------------------------------------------------------------------

    def execute(
        self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()
    ) -> sqlite3.Cursor:
        """SQLを実行してカーソルを返す。

        INSERT / UPDATE / DELETE などの書き込み操作向け。
        自動的にコミットする。

        Args:
            sql: 実行するSQL文。
            params: バインドパラメータ（タプルまたは辞書）。

        Returns:
            sqlite3.Cursor: 実行結果のカーソル。
        """
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor

    def fetch_one(
        self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()
    ) -> sqlite3.Row | None:
        """SQLを実行して1行だけ取得する。

        結果がない場合は None を返す。

        Args:
            sql: 実行するSQL文。
            params: バインドパラメータ。

        Returns:
            sqlite3.Row | None: 結果行、または None。
        """
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            return cursor.fetchone()

    def fetch_all(
        self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()
    ) -> list[sqlite3.Row]:
        """SQLを実行して全行を取得する。

        Args:
            sql: 実行するSQL文。
            params: バインドパラメータ。

        Returns:
            list[sqlite3.Row]: 結果行のリスト。
        """
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            return cursor.fetchall()
