"""
認証・セッション管理モジュール

メール+パスワード認証、ユーザー管理、初期管理者作成を担当する。
"""

from __future__ import annotations

import os

import bcrypt as _bcrypt


def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


class AuthManager:
    """ユーザー認証・管理クラス"""

    def __init__(self, db) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # 登録・ログイン
    # ------------------------------------------------------------------

    def register(self, email: str, password: str, display_name: str = ""):
        """新規ユーザー登録。成功時は (user_row, None)、失敗時は (None, error_msg)。"""
        existing = self.db.fetch_one(
            "SELECT id FROM users WHERE email = ?", (email,)
        )
        if existing:
            return None, "このメールアドレスは既に登録されています"

        password_hash = _hash_password(password)
        admin_email = os.getenv("ADMIN_EMAIL", "")
        is_admin = 1 if email == admin_email else 0

        self.db.execute(
            "INSERT INTO users (email, password_hash, display_name, tier, is_admin) "
            "VALUES (?, ?, ?, ?, ?)",
            (email, password_hash, display_name or email.split("@")[0], "free", is_admin),
        )
        user = self.db.fetch_one("SELECT * FROM users WHERE email = ?", (email,))
        return user, None

    def login(self, email: str, password: str):
        """ログイン。成功時は (user_row, None)、失敗時は (None, error_msg)。"""
        user = self.db.fetch_one(
            "SELECT * FROM users WHERE email = ?", (email,)
        )
        if not user:
            return None, "メールアドレスまたはパスワードが正しくありません"

        if not user["is_active"]:
            return None, "このアカウントは無効になっています"

        if not _verify_password(password, user["password_hash"]):
            return None, "メールアドレスまたはパスワードが正しくありません"

        return user, None

    # ------------------------------------------------------------------
    # ユーザー取得・更新
    # ------------------------------------------------------------------

    def get_user(self, user_id: int):
        return self.db.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))

    def update_user(self, user_id: int, **kwargs) -> None:
        allowed = {
            "display_name", "tier", "is_active", "is_admin",
            "newsletter_cta_text", "line_url",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [user_id]
        self.db.execute(
            f"UPDATE users SET {set_clause}, "
            f"updated_at = datetime('now', 'localtime') WHERE id = ?",
            tuple(values),
        )

    # ------------------------------------------------------------------
    # 初期管理者
    # ------------------------------------------------------------------

    def ensure_admin(self) -> None:
        """環境変数の ADMIN_EMAIL / ADMIN_PASSWORD から管理者アカウントを作成・更新する。"""
        admin_email = os.getenv("ADMIN_EMAIL", "")
        admin_password = os.getenv("ADMIN_PASSWORD", "")
        if not admin_email or not admin_password:
            return

        existing = self.db.fetch_one(
            "SELECT id FROM users WHERE email = ?", (admin_email,)
        )
        if existing:
            self.db.execute(
                "UPDATE users SET is_admin = 1 WHERE email = ?", (admin_email,)
            )
            return

        password_hash = _hash_password(admin_password)
        self.db.execute(
            "INSERT INTO users (email, password_hash, display_name, tier, is_admin) "
            "VALUES (?, ?, ?, ?, ?)",
            (admin_email, password_hash, "管理者", "venture", 1),
        )

        # 既存データを管理者に紐づけ
        admin = self.db.fetch_one(
            "SELECT id FROM users WHERE email = ?", (admin_email,)
        )
        if admin:
            admin_id = admin["id"]
            for table in ["generated_articles", "style_profiles", "sources", "batch_jobs"]:
                self.db.execute(
                    f"UPDATE {table} SET user_id = ? WHERE user_id IS NULL",
                    (admin_id,),
                )
