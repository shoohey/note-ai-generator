-- note自動投稿ツール データベーススキーマ
-- SQLite用。WALモードと外部キー制約を前提とする。

-- ソース資料テーブル: PDF・URL等の取り込み済み素材を管理
CREATE TABLE IF NOT EXISTS sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    type        TEXT    NOT NULL,       -- 'pdf', 'url', 'text' など
    title       TEXT    NOT NULL,       -- ソースのタイトル
    content     TEXT    NOT NULL,       -- 抽出済みテキスト本文
    url         TEXT,                   -- 元URL（該当する場合）
    metadata    TEXT    DEFAULT '{}',   -- JSON形式の追加情報
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- スタイルプロファイルテーブル: 文体・トーンの分析結果を保存
CREATE TABLE IF NOT EXISTS style_profiles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,           -- プロファイル名
    profile         TEXT    NOT NULL DEFAULT '{}',  -- JSON: 文体分析結果
    source_articles TEXT    NOT NULL DEFAULT '[]',  -- JSON: 分析元記事のID一覧
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 生成記事テーブル: AIが生成した記事を管理
CREATE TABLE IF NOT EXISTS generated_articles (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT    NOT NULL,              -- 記事タイトル
    content          TEXT    NOT NULL,              -- 記事本文
    topic            TEXT    NOT NULL,              -- 記事のトピック・テーマ
    source_ids       TEXT    NOT NULL DEFAULT '[]', -- JSON: 参照したソースIDの配列
    style_profile_id INTEGER,                       -- 使用したスタイルプロファイル
    word_count       INTEGER NOT NULL DEFAULT 0,    -- 文字数
    status           TEXT    NOT NULL DEFAULT 'draft', -- 'draft', 'reviewed', 'published'
    metadata         TEXT    DEFAULT '{}',          -- JSON形式の追加情報
    created_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),

    FOREIGN KEY (style_profile_id) REFERENCES style_profiles(id)
        ON DELETE SET NULL
);

-- スクレイプキャッシュテーブル: URLスクレイピング結果のキャッシュ
CREATE TABLE IF NOT EXISTS scrape_cache (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT    NOT NULL UNIQUE,  -- キャッシュ対象URL（一意制約）
    content     TEXT    NOT NULL,         -- 取得したHTMLまたはテキスト
    status_code INTEGER NOT NULL,         -- HTTPステータスコード
    fetched_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- バッチジョブテーブル: 一括処理ジョブの進捗管理
CREATE TABLE IF NOT EXISTS batch_jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,              -- ジョブ名
    status          TEXT    NOT NULL DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
    total_count     INTEGER NOT NULL DEFAULT 0,    -- 処理対象の総数
    completed_count INTEGER NOT NULL DEFAULT 0,    -- 完了済み件数
    config          TEXT    DEFAULT '{}',          -- JSON: ジョブ設定
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- インデックス: よく使うクエリの高速化
CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(type);
CREATE INDEX IF NOT EXISTS idx_generated_articles_status ON generated_articles(status);
CREATE INDEX IF NOT EXISTS idx_generated_articles_style_profile ON generated_articles(style_profile_id);
CREATE INDEX IF NOT EXISTS idx_scrape_cache_url ON scrape_cache(url);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_status ON batch_jobs(status);
