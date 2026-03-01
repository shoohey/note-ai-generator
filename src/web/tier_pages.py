"""
プラン比較ページ・管理画面・記事共有ページ
"""

from __future__ import annotations

import json
import secrets

import streamlit as st

from src.auth.auth_manager import AuthManager
from src.auth.tier_gate import TierGate


# ---------------------------------------------------------------------------
# ティア比較データ
# ---------------------------------------------------------------------------

TIER_FEATURES = [
    {"label": "記事生成", "free": "合計3本", "front": "月20本", "middle": "月100本", "venture": "無制限"},
    {"label": "バッチサイズ", "free": "1本ずつ", "front": "最大5本", "middle": "最大50本", "venture": "最大50本"},
    {"label": "目標文字数", "free": "〜2,000字", "front": "〜3,000字", "middle": "〜5,000字", "venture": "〜5,000字"},
    {"label": "カスタムスタイル", "free": "不可", "front": "1つ", "middle": "無制限", "venture": "無制限"},
    {"label": "URL取込", "free": "不可", "front": "不可", "middle": "可", "venture": "可"},
    {"label": "メルマガCTA", "free": "不可", "front": "可", "middle": "可", "venture": "可"},
    {"label": "A→Bリライト学習", "free": "不可", "front": "可", "middle": "可", "venture": "可"},
    {"label": "優先サポート", "free": "不可", "front": "不可", "middle": "不可", "venture": "可"},
]


# ---------------------------------------------------------------------------
# プラン比較
# ---------------------------------------------------------------------------

def page_plans():
    st.markdown('<div class="page-header">プラン比較</div>', unsafe_allow_html=True)

    user = st.session_state.get("user")
    current_tier = user["tier"] if user else "free"

    tiers = [
        {"name": "free", "display": "Free", "price": "¥0", "desc": "まずはお試し", "color": "#8b95a0"},
        {"name": "front", "display": "Front", "price": "¥2,980/月", "desc": "個人クリエイター向け", "color": "#149274"},
        {"name": "middle", "display": "Middle", "price": "¥9,800/月", "desc": "本格的な運用に", "color": "#4c7cf3"},
        {"name": "venture", "display": "Venture", "price": "¥49,800/月", "desc": "ビジネス利用に", "color": "#e89d3c"},
    ]

    cols = st.columns(4)
    for i, t in enumerate(tiers):
        with cols[i]:
            is_current = t["name"] == current_tier
            border = f"3px solid {t['color']}" if is_current else "1px solid #e6eaed"
            badge = (
                f'<div style="background: {t["color"]}; color: #fff !important; '
                f'font-size: 0.7rem; padding: 2px 8px; border-radius: 4px; '
                f'display: inline-block; margin-bottom: 0.5rem;">現在のプラン</div>'
                if is_current
                else ""
            )
            st.markdown(f"""
            <div style="border: {border}; border-radius: 12px;
                        padding: 1.5rem 1rem; text-align: center; min-height: 200px;">
                {badge}
                <div style="font-size: 1.1rem; font-weight: 700; color: {t['color']};">
                    {t['display']}
                </div>
                <div style="font-size: 1.5rem; font-weight: 700; margin: 0.5rem 0;">
                    {t['price']}
                </div>
                <div style="font-size: 0.8rem; color: #8b95a0;">{t['desc']}</div>
            </div>
            """, unsafe_allow_html=True)

            if not is_current and t["name"] != "free":
                if st.button(
                    "お問い合わせ",
                    key=f"upgrade_{t['name']}",
                    use_container_width=True,
                ):
                    st.session_state.page = "contact"
                    st.rerun()

    st.markdown("---")
    st.markdown('<div class="section-title">機能比較</div>', unsafe_allow_html=True)

    header = "| 機能 | Free | Front | Middle | Venture |"
    separator = "|---|---|---|---|---|"
    rows = [
        f"| {f['label']} | {f['free']} | {f['front']} | {f['middle']} | {f['venture']} |"
        for f in TIER_FEATURES
    ]
    st.markdown("\n".join([header, separator] + rows))

    st.markdown("---")
    st.markdown('<div class="section-title">お問い合わせ</div>', unsafe_allow_html=True)
    st.markdown(
        "プランのアップグレードやご質問は、以下からお問い合わせください。\n\n"
        "- **LINE**: [友達追加はこちら](#)\n"
        "- **メール**: support@example.com"
    )


# ---------------------------------------------------------------------------
# お問い合わせ
# ---------------------------------------------------------------------------

def page_contact():
    st.markdown('<div class="page-header">お問い合わせ</div>', unsafe_allow_html=True)
    st.markdown("""
    プランのアップグレードや機能のご質問は、以下からお気軽にどうぞ。

    ### LINE
    以下のリンクから友達追加してメッセージをお送りください。

    ### メール
    support@example.com までお送りください。

    ---

    *担当者が確認次第、ご連絡いたします。*
    """)


# ---------------------------------------------------------------------------
# 記事共有（読み取り専用）
# ---------------------------------------------------------------------------

def render_shared_articles(db, token: str):
    """共有トークンによる記事一覧の読み取り専用表示"""
    row = db.fetch_one(
        "SELECT st.user_id, u.display_name "
        "FROM share_tokens st JOIN users u ON st.user_id = u.id "
        "WHERE st.token = ?",
        (token,),
    )
    if not row:
        st.error("無効な共有リンクです")
        return

    user_id = row["user_id"]
    author_name = row["display_name"]

    st.markdown(f"""
    <div style="text-align: center; margin: 2rem 0 1rem;">
        <span style="background-color: #149274; color: #fff !important; font-weight: 700;
                     font-size: 1rem; padding: 4px 12px; border-radius: 6px;">note</span>
        <span style="font-size: 1.1rem; font-weight: 700; margin-left: 8px;">
            {author_name} の記事一覧
        </span>
    </div>
    """, unsafe_allow_html=True)

    articles = db.fetch_all(
        "SELECT id, title, content, word_count, status, created_at "
        "FROM generated_articles WHERE user_id = ? "
        "ORDER BY created_at DESC",
        (user_id,),
    )

    if not articles:
        st.info("まだ記事がありません。")
        return

    st.markdown(f"**{len(articles)}件**の記事")

    for a in articles:
        status_jp = {
            "draft": "下書き", "reviewed": "確認済", "published": "公開済"
        }.get(a["status"], a["status"])
        with st.expander(
            f"{a['title']}  ({a['word_count']:,}文字 / {status_jp} / {a['created_at']})"
        ):
            st.markdown(a["content"])


def generate_share_token(db, user_id: int) -> str:
    """共有トークンを生成して返す。既存があればそれを返す。"""
    existing = db.fetch_one(
        "SELECT token FROM share_tokens WHERE user_id = ?", (user_id,)
    )
    if existing:
        return existing["token"]

    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO share_tokens (user_id, token) VALUES (?, ?)",
        (user_id, token),
    )
    return token


# ---------------------------------------------------------------------------
# 管理画面
# ---------------------------------------------------------------------------

def page_admin(db):
    st.markdown('<div class="page-header">管理画面</div>', unsafe_allow_html=True)

    user = st.session_state.get("user")
    if not user or not user.get("is_admin"):
        st.error("管理者権限がありません")
        return

    tab_users, tab_stats, tab_tiers, tab_add = st.tabs([
        "ユーザー管理", "利用統計", "ティア設定", "ユーザー追加"
    ])

    with tab_users:
        _admin_users(db)
    with tab_stats:
        _admin_stats(db)
    with tab_tiers:
        _admin_tiers(db)
    with tab_add:
        _admin_add_user(db)


def _admin_users(db):
    users = db.fetch_all("SELECT * FROM users ORDER BY created_at DESC")
    st.markdown(f"**{len(users)}人**のユーザー")

    for u in users:
        tier_icon = {"free": "", "front": "", "middle": "", "venture": ""}.get(
            u["tier"], ""
        )
        active_mark = "" if u["is_active"] else " (無効)"
        admin_mark = " [管理者]" if u["is_admin"] else ""

        with st.expander(
            f"{u['display_name']} ({u['email']}) - {u['tier']}{admin_mark}{active_mark}"
        ):
            c1, c2 = st.columns(2)
            with c1:
                new_tier = st.selectbox(
                    "ティア",
                    ["free", "front", "middle", "venture"],
                    index=["free", "front", "middle", "venture"].index(u["tier"]),
                    key=f"at_{u['id']}",
                )
            with c2:
                new_active = st.checkbox(
                    "有効", value=bool(u["is_active"]), key=f"aa_{u['id']}"
                )

            gate = TierGate(db, u)
            usage = gate.get_usage()
            total = gate.get_total_usage()
            st.markdown(
                f"今月: **{usage['article_count']}本** / "
                f"累計: **{total}本** / 登録日: {u['created_at']}"
            )

            if st.button("更新", key=f"au_{u['id']}", type="primary"):
                auth = AuthManager(db)
                auth.update_user(
                    u["id"], tier=new_tier, is_active=1 if new_active else 0
                )
                current = st.session_state.get("user")
                if current and current["id"] == u["id"]:
                    st.session_state["user"] = dict(
                        db.fetch_one("SELECT * FROM users WHERE id = ?", (u["id"],))
                    )
                st.success("更新しました")
                st.rerun()


def _admin_stats(db):
    total_users = db.fetch_one("SELECT COUNT(*) as cnt FROM users")["cnt"]
    total_articles = db.fetch_one("SELECT COUNT(*) as cnt FROM generated_articles")["cnt"]
    total_chars = db.fetch_one(
        "SELECT COALESCE(SUM(word_count), 0) as t FROM generated_articles"
    )["t"]

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("総ユーザー数", total_users)
    with c2:
        st.metric("総記事数", total_articles)
    with c3:
        st.metric("総文字数", f"{total_chars:,}")

    st.markdown("### ティア分布")
    tier_dist = db.fetch_all(
        "SELECT tier, COUNT(*) as cnt FROM users GROUP BY tier ORDER BY cnt DESC"
    )
    for td in tier_dist:
        st.markdown(f"- **{td['tier']}**: {td['cnt']}人")

    st.markdown("### 直近の利用")
    recent = db.fetch_all(
        "SELECT u.display_name, u.email, ul.action, ul.created_at "
        "FROM usage_log ul JOIN users u ON ul.user_id = u.id "
        "ORDER BY ul.created_at DESC LIMIT 20"
    )
    if recent:
        for r in recent:
            st.markdown(f"- {r['created_at']} | {r['display_name']} | {r['action']}")
    else:
        st.info("利用ログはまだありません")


def _admin_tiers(db):
    configs = db.fetch_all("SELECT * FROM tier_config ORDER BY price ASC")

    for cfg in configs:
        with st.expander(
            f"{cfg['display_name']} ({cfg['tier_name']}) - ¥{cfg['price']:,}/月"
        ):
            c1, c2 = st.columns(2)
            with c1:
                new_price = st.number_input(
                    "月額価格", value=cfg["price"], key=f"tp_{cfg['id']}"
                )
                new_monthly = st.number_input(
                    "月間上限 (0=無制限)", value=cfg["monthly_limit"], key=f"tm_{cfg['id']}"
                )
                new_total = st.number_input(
                    "累計上限 (0=なし)", value=cfg["total_limit"], key=f"tt_{cfg['id']}"
                )
            with c2:
                new_batch = st.number_input(
                    "最大バッチ", value=cfg["max_batch_size"], key=f"tb_{cfg['id']}"
                )
                new_chars = st.number_input(
                    "最大文字数", value=cfg["max_target_chars"], key=f"tc_{cfg['id']}"
                )
                new_style = st.number_input(
                    "スタイル上限 (-1=無制限)",
                    value=cfg["custom_style_limit"],
                    key=f"ts_{cfg['id']}",
                )

            new_url = st.checkbox(
                "URL取込", value=bool(cfg["url_ingestion"]), key=f"tu_{cfg['id']}"
            )
            new_support = st.checkbox(
                "優先サポート", value=bool(cfg["priority_support"]), key=f"tps_{cfg['id']}"
            )

            if st.button("保存", key=f"tsave_{cfg['id']}", type="primary"):
                db.execute(
                    "UPDATE tier_config SET price=?, monthly_limit=?, total_limit=?, "
                    "max_batch_size=?, max_target_chars=?, custom_style_limit=?, "
                    "url_ingestion=?, priority_support=? WHERE id=?",
                    (
                        new_price, new_monthly, new_total, new_batch,
                        new_chars, new_style, 1 if new_url else 0,
                        1 if new_support else 0, cfg["id"],
                    ),
                )
                st.success("保存しました")
                st.rerun()


def _admin_add_user(db):
    st.markdown("有料プラン受講生を手動で登録できます。")

    with st.form("add_user_form"):
        email = st.text_input("メールアドレス")
        display_name = st.text_input("表示名")
        password = st.text_input("初期パスワード", type="password")
        tier = st.selectbox("ティア", ["free", "front", "middle", "venture"])
        submitted = st.form_submit_button("追加", type="primary")

    if submitted:
        if not email or not password:
            st.error("メールアドレスとパスワードを入力してください")
            return
        auth = AuthManager(db)
        user, error = auth.register(email, password, display_name)
        if error:
            st.error(error)
        else:
            auth.update_user(user["id"], tier=tier)
            st.success(f"ユーザー「{display_name or email}」を{tier}プランで追加しました")
            st.rerun()
