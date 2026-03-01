"""
データベースマイグレーション管理

スキーマバージョンを管理し、段階的にDBを更新する。
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)


def get_schema_version(conn: sqlite3.Connection) -> int:
    try:
        cursor = conn.execute("PRAGMA user_version")
        return cursor.fetchone()[0]
    except Exception:
        return 0


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(f"PRAGMA user_version = {version}")


def migrate(conn: sqlite3.Connection) -> None:
    version = get_schema_version(conn)

    if version < 2:
        _migrate_to_v2(conn)
        set_schema_version(conn, 2)
        conn.commit()
        logger.info("マイグレーション完了: v%d → v2", version)


def _migrate_to_v2(conn: sqlite3.Connection) -> None:
    """v1 → v2: ユーザー・ティア・利用量管理テーブルを追加"""

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            email           TEXT    NOT NULL UNIQUE,
            password_hash   TEXT    NOT NULL,
            display_name    TEXT    NOT NULL DEFAULT '',
            tier            TEXT    NOT NULL DEFAULT 'free',
            is_admin        INTEGER NOT NULL DEFAULT 0,
            is_active       INTEGER NOT NULL DEFAULT 1,
            newsletter_cta_text TEXT DEFAULT '',
            line_url        TEXT    DEFAULT '',
            created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tier_config (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            tier_name           TEXT    NOT NULL UNIQUE,
            display_name        TEXT    NOT NULL,
            price               INTEGER NOT NULL DEFAULT 0,
            monthly_limit       INTEGER NOT NULL DEFAULT 0,
            total_limit         INTEGER NOT NULL DEFAULT 0,
            max_batch_size      INTEGER NOT NULL DEFAULT 1,
            max_target_chars    INTEGER NOT NULL DEFAULT 2000,
            custom_style_limit  INTEGER NOT NULL DEFAULT 0,
            url_ingestion       INTEGER NOT NULL DEFAULT 0,
            priority_support    INTEGER NOT NULL DEFAULT 0,
            created_at          TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_tracking (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            year_month      TEXT    NOT NULL,
            article_count   INTEGER NOT NULL DEFAULT 0,
            total_chars     INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, year_month)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            action      TEXT    NOT NULL,
            details     TEXT    DEFAULT '{}',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS share_tokens (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            token       TEXT    NOT NULL UNIQUE,
            expires_at  TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # 既存テーブルに user_id カラムを追加
    for table in ["generated_articles", "style_profiles", "sources", "batch_jobs"]:
        try:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id)"
            )
        except sqlite3.OperationalError:
            pass  # カラム既存

    # インデックス
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
        "CREATE INDEX IF NOT EXISTS idx_usage_tracking_user_month ON usage_tracking(user_id, year_month)",
        "CREATE INDEX IF NOT EXISTS idx_usage_log_user ON usage_log(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_generated_articles_user ON generated_articles(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_style_profiles_user ON style_profiles(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_sources_user ON sources(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_share_tokens_token ON share_tokens(token)",
    ]:
        conn.execute(idx_sql)

    # デフォルトティア設定
    tier_defaults = [
        ("free", "Free", 0, 0, 3, 1, 2000, 0, 0, 0),
        ("front", "Front", 2980, 20, 0, 5, 3000, 1, 0, 0),
        ("middle", "Middle", 9800, 100, 0, 50, 5000, -1, 1, 0),
        ("venture", "Venture", 49800, 0, 0, 50, 5000, -1, 1, 1),
    ]
    for td in tier_defaults:
        conn.execute(
            "INSERT OR IGNORE INTO tier_config "
            "(tier_name, display_name, price, monthly_limit, total_limit, "
            "max_batch_size, max_target_chars, custom_style_limit, "
            "url_ingestion, priority_support) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            td,
        )
