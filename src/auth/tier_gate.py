"""
ティアゲーティングモジュール

ユーザーのプランに応じて機能制限・クォータを制御する。
"""

from __future__ import annotations

import json
from datetime import datetime


class TierGate:
    """ユーザーのティアに基づく機能ゲートクラス"""

    def __init__(self, db, user) -> None:
        self.db = db
        self.user = user
        self.tier = user["tier"] if user else "free"
        self._config = None

    # ------------------------------------------------------------------
    # ティア設定
    # ------------------------------------------------------------------

    @property
    def config(self):
        if self._config is None:
            self._config = self.db.fetch_one(
                "SELECT * FROM tier_config WHERE tier_name = ?", (self.tier,)
            )
            if self._config is None:
                self._config = self.db.fetch_one(
                    "SELECT * FROM tier_config WHERE tier_name = 'free'"
                )
        return self._config

    # ------------------------------------------------------------------
    # 利用量
    # ------------------------------------------------------------------

    def get_usage(self) -> dict:
        """現在月の使用量を取得"""
        year_month = datetime.now().strftime("%Y-%m")
        row = self.db.fetch_one(
            "SELECT article_count, total_chars FROM usage_tracking "
            "WHERE user_id = ? AND year_month = ?",
            (self.user["id"], year_month),
        )
        if row:
            return {"article_count": row["article_count"], "total_chars": row["total_chars"]}
        return {"article_count": 0, "total_chars": 0}

    def get_total_usage(self) -> int:
        """累計生成数を取得（Freeティア用）"""
        row = self.db.fetch_one(
            "SELECT COUNT(*) as cnt FROM generated_articles WHERE user_id = ?",
            (self.user["id"],),
        )
        return row["cnt"] if row else 0

    # ------------------------------------------------------------------
    # クォータチェック
    # ------------------------------------------------------------------

    def remaining_quota(self) -> int:
        """残りクォータを返す。-1 は無制限。"""
        cfg = self.config
        if not cfg:
            return 0

        if self.tier == "free":
            total_limit = cfg["total_limit"]
            if total_limit <= 0:
                return 0
            return max(total_limit - self.get_total_usage(), 0)

        monthly_limit = cfg["monthly_limit"]
        if monthly_limit <= 0:
            return -1  # 無制限

        usage = self.get_usage()
        return max(monthly_limit - usage["article_count"], 0)

    def can_generate(self, count: int = 1) -> bool:
        """指定本数を生成可能か"""
        remaining = self.remaining_quota()
        if remaining == -1:
            return True
        return remaining >= count

    # ------------------------------------------------------------------
    # 機能制限
    # ------------------------------------------------------------------

    def max_batch_size(self) -> int:
        cfg = self.config
        return cfg["max_batch_size"] if cfg else 1

    def max_target_chars(self) -> int:
        cfg = self.config
        return cfg["max_target_chars"] if cfg else 2000

    def can_use_custom_style(self) -> bool:
        cfg = self.config
        if not cfg:
            return False
        limit = cfg["custom_style_limit"]
        if limit == -1:
            return True
        if limit == 0:
            return False
        return self.custom_style_count() < limit

    def custom_style_count(self) -> int:
        row = self.db.fetch_one(
            "SELECT COUNT(*) as cnt FROM style_profiles WHERE user_id = ?",
            (self.user["id"],),
        )
        return row["cnt"] if row else 0

    def custom_style_limit(self) -> int:
        """-1=無制限, 0=不可"""
        cfg = self.config
        return cfg["custom_style_limit"] if cfg else 0

    def can_use_url_ingestion(self) -> bool:
        cfg = self.config
        return bool(cfg["url_ingestion"]) if cfg else False

    def has_priority_support(self) -> bool:
        cfg = self.config
        return bool(cfg["priority_support"]) if cfg else False

    # ------------------------------------------------------------------
    # 利用量記録
    # ------------------------------------------------------------------

    def record_generation(self, count: int = 1, chars: int = 0) -> None:
        user_id = self.user["id"]
        year_month = datetime.now().strftime("%Y-%m")

        existing = self.db.fetch_one(
            "SELECT id FROM usage_tracking WHERE user_id = ? AND year_month = ?",
            (user_id, year_month),
        )
        if existing:
            self.db.execute(
                "UPDATE usage_tracking SET article_count = article_count + ?, "
                "total_chars = total_chars + ? "
                "WHERE user_id = ? AND year_month = ?",
                (count, chars, user_id, year_month),
            )
        else:
            self.db.execute(
                "INSERT INTO usage_tracking (user_id, year_month, article_count, total_chars) "
                "VALUES (?, ?, ?, ?)",
                (user_id, year_month, count, chars),
            )

        self.db.execute(
            "INSERT INTO usage_log (user_id, action, details) VALUES (?, ?, ?)",
            (user_id, "generate", json.dumps({"count": count, "chars": chars})),
        )

    # ------------------------------------------------------------------
    # 表示用
    # ------------------------------------------------------------------

    def tier_display_name(self) -> str:
        cfg = self.config
        return cfg["display_name"] if cfg else "Free"

    def tier_badge_color(self) -> str:
        colors = {
            "free": "#8b95a0",
            "front": "#149274",
            "middle": "#4c7cf3",
            "venture": "#e89d3c",
        }
        return colors.get(self.tier, "#8b95a0")
