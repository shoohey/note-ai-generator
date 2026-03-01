"""
認証ページ（ログイン・新規登録・アカウント設定）
"""

from __future__ import annotations

import streamlit as st

from src.auth.auth_manager import AuthManager


def render_auth_page(db):
    """認証ページ（ログイン/新規登録）を表示"""

    st.markdown("""
    <div style="max-width: 420px; margin: 0 auto; padding-top: 3rem;">
        <div style="text-align: center; margin-bottom: 2rem;">
            <span style="background-color: #149274; color: #fff !important; font-weight: 700;
                         font-size: 1.2rem; padding: 6px 16px; border-radius: 6px;">note</span>
            <span style="font-size: 1.3rem; font-weight: 700; margin-left: 8px;">記事ジェネレーター</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["ログイン", "新規登録"])
    auth = AuthManager(db)

    with tab_login:
        _render_login(auth)

    with tab_register:
        _render_register(auth)


def _render_login(auth: AuthManager):
    with st.form("login_form"):
        email = st.text_input("メールアドレス", placeholder="example@email.com")
        password = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button(
            "ログイン", type="primary", use_container_width=True
        )

    if submitted:
        if not email or not password:
            st.error("メールアドレスとパスワードを入力してください")
            return
        user, error = auth.login(email, password)
        if error:
            st.error(error)
        else:
            st.session_state["user"] = dict(user)
            st.rerun()


def _render_register(auth: AuthManager):
    st.markdown("""
    <div style="background: linear-gradient(135deg, #e8f5e9, #e3f2fd);
                border: 1px solid #149274; border-radius: 10px;
                padding: 1rem 1.2rem; margin-bottom: 1rem; text-align: center;">
        <div style="font-size: 0.95rem; font-weight: 600; color: #149274;">
            無料で3記事まで生成できます
        </div>
        <div style="font-size: 0.8rem; color: #666; margin-top: 0.3rem;">
            AIがあなたのスタイルで記事を自動生成。まずはお試しください。
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("register_form"):
        email = st.text_input(
            "メールアドレス", placeholder="example@email.com", key="reg_email"
        )
        display_name = st.text_input(
            "表示名", placeholder="山田太郎", key="reg_name"
        )
        password = st.text_input("パスワード", type="password", key="reg_pass")
        password_confirm = st.text_input(
            "パスワード（確認）", type="password", key="reg_pass2"
        )
        submitted = st.form_submit_button(
            "無料で始める", type="primary", use_container_width=True
        )

    if submitted:
        if not email or not password:
            st.error("メールアドレスとパスワードを入力してください")
            return
        if len(password) < 6:
            st.error("パスワードは6文字以上にしてください")
            return
        if password != password_confirm:
            st.error("パスワードが一致しません")
            return
        user, error = auth.register(email, password, display_name)
        if error:
            st.error(error)
        else:
            st.session_state["user"] = dict(user)
            st.success("アカウントを作成しました！")
            st.rerun()


def render_account_page(db):
    """アカウント設定ページ"""
    st.markdown('<div class="page-header">アカウント設定</div>', unsafe_allow_html=True)

    user = st.session_state.get("user")
    if not user:
        return

    auth = AuthManager(db)

    st.markdown('<div class="section-title">プロフィール</div>', unsafe_allow_html=True)

    with st.form("account_form"):
        display_name = st.text_input("表示名", value=user.get("display_name", ""))
        st.text_input("メールアドレス", value=user.get("email", ""), disabled=True)
        st.text_input(
            "プラン",
            value=user.get("tier", "free").title(),
            disabled=True,
        )
        submitted = st.form_submit_button("保存", type="primary")

    if submitted:
        auth.update_user(user["id"], display_name=display_name)
        st.session_state["user"]["display_name"] = display_name
        st.success("保存しました")

    st.markdown("---")
    st.markdown('<div class="section-title">メルマガ / LINE CTA 設定</div>', unsafe_allow_html=True)
    st.markdown(
        "記事末尾に自動挿入されるCTAテキストを設定できます。"
        "（Frontプラン以上で利用可能）"
    )

    with st.form("cta_form"):
        cta_text = st.text_area(
            "CTA テキスト（Markdown可）",
            value=user.get("newsletter_cta_text", ""),
            height=120,
            placeholder=(
                "例:\n"
                "---\n"
                "📩 メルマガ登録はこちら → [登録リンク]\n"
                "📱 LINE友達追加 → [LINEリンク]"
            ),
        )
        line_url = st.text_input(
            "LINE URL",
            value=user.get("line_url", ""),
            placeholder="https://line.me/R/ti/p/...",
        )
        submitted_cta = st.form_submit_button("CTA設定を保存", type="primary")

    if submitted_cta:
        auth.update_user(
            user["id"], newsletter_cta_text=cta_text, line_url=line_url
        )
        st.session_state["user"]["newsletter_cta_text"] = cta_text
        st.session_state["user"]["line_url"] = line_url
        st.success("CTA設定を保存しました")

    st.markdown("---")
    if st.button("ログアウト"):
        for key in ["user", "db", "settings"]:
            st.session_state.pop(key, None)
        st.rerun()
