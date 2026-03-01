-- note自動投稿ツール スキーマ v2
-- ユーザー・ティア・利用量管理テーブルを追加

-- ユーザーテーブル
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
);

-- ティア設定テーブル（管理画面から編集可能）
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
);

-- 利用量トラッキング（月次）
CREATE TABLE IF NOT EXISTS usage_tracking (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    year_month      TEXT    NOT NULL,
    article_count   INTEGER NOT NULL DEFAULT 0,
    total_chars     INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, year_month)
);

-- 利用ログ（個別イベント）
CREATE TABLE IF NOT EXISTS usage_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    action      TEXT    NOT NULL,
    details     TEXT    DEFAULT '{}',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 記事共有トークン
CREATE TABLE IF NOT EXISTS share_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    token       TEXT    NOT NULL UNIQUE,
    expires_at  TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_usage_tracking_user_month ON usage_tracking(user_id, year_month);
CREATE INDEX IF NOT EXISTS idx_usage_log_user ON usage_log(user_id);
CREATE INDEX IF NOT EXISTS idx_share_tokens_token ON share_tokens(token);

-- デフォルトティア設定
INSERT OR IGNORE INTO tier_config
    (tier_name, display_name, price, monthly_limit, total_limit, max_batch_size, max_target_chars, custom_style_limit, url_ingestion, priority_support)
VALUES
    ('free',    'Free',    0,     0,   3, 1,  2000, 0,  0, 0),
    ('front',   'Front',   2980,  20,  0, 5,  3000, 1,  0, 0),
    ('middle',  'Middle',  9800,  100, 0, 50, 5000, -1, 1, 0),
    ('venture', 'Venture', 49800, 0,   0, 50, 5000, -1, 1, 1);
