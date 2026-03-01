"""
アップグレードCTAコンポーネント

制限到達時のモーダル、機能ロック表示、アップグレードバナーを提供する。
"""

from __future__ import annotations

import streamlit as st


def render_quota_exhausted(tier_gate):
    """クォータ到達時の案内表示"""
    tier_name = tier_gate.tier_display_name()

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #fff5f5, #fff);
                border: 2px solid #e74c3c; border-radius: 12px;
                padding: 2rem; text-align: center; margin: 1rem 0;">
        <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">&#9888;&#65039;</div>
        <div style="font-size: 1.2rem; font-weight: 700; color: #e74c3c; margin-bottom: 0.5rem;">
            記事生成の上限に達しました
        </div>
        <div style="font-size: 0.9rem; color: #666; margin-bottom: 1.5rem;">
            現在のプラン（{tier_name}）では、これ以上記事を生成できません。<br>
            プランをアップグレードして、さらに多くの記事を生成しましょう。
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("プランを比較する", type="primary", use_container_width=True):
            st.session_state.page = "plans"
            st.rerun()
    with c2:
        if st.button("お問い合わせ", use_container_width=True, key="quota_contact"):
            st.session_state.page = "contact"
            st.rerun()


def render_feature_locked(feature_name: str, required_tier: str = "Front"):
    """機能ロック表示"""
    st.markdown(f"""
    <div style="background: #f7f9fa; border: 1px solid #e6eaed;
                border-radius: 10px; padding: 1.2rem; text-align: center;
                margin: 0.5rem 0;">
        <div style="font-size: 1.5rem; margin-bottom: 0.3rem;">&#128274;</div>
        <div style="font-size: 0.9rem; font-weight: 600; color: #08131a;">
            {feature_name}
        </div>
        <div style="font-size: 0.8rem; color: #8b95a0; margin-top: 0.3rem;">
            {required_tier}プラン以上で利用可能
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_upgrade_banner():
    """Freeユーザー向けアップグレードバナー"""
    st.markdown("""
    <div style="background: linear-gradient(135deg, #e8f5e9, #e3f2fd);
                border: 1px solid #149274; border-radius: 12px;
                padding: 1.2rem 1.5rem; margin-bottom: 1rem;">
        <div style="font-size: 1rem; font-weight: 700; color: #149274; margin-bottom: 0.3rem;">
            もっと記事を生成しませんか？
        </div>
        <div style="font-size: 0.85rem; color: #08131a;">
            Frontプラン（月額¥2,980）で月20本まで生成可能。カスタムスタイルも使えます。
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_quota_sidebar(tier_gate):
    """サイドバー用クォータ表示"""
    tier_name = tier_gate.tier_display_name()
    badge_color = tier_gate.tier_badge_color()
    user = tier_gate.user
    remaining = tier_gate.remaining_quota()

    st.markdown(f"""
    <div style="margin-bottom: 0.5rem;">
        <span style="font-weight: 600; font-size: 0.9rem;">
            {user['display_name']}
        </span>
        <span style="background: {badge_color}; color: #fff !important;
                     font-size: 0.7rem; font-weight: 600; padding: 2px 8px;
                     border-radius: 4px; margin-left: 6px;">
            {tier_name}
        </span>
    </div>
    """, unsafe_allow_html=True)

    if remaining == -1:
        quota_text = "無制限"
    elif tier_gate.tier == "free":
        total = tier_gate.config["total_limit"]
        quota_text = f"残り {remaining} / {total} 本"
    else:
        total = tier_gate.config["monthly_limit"]
        usage = tier_gate.get_usage()
        quota_text = f"今月 {usage['article_count']} / {total} 本"

    st.markdown(f"""
    <div style="font-size: 0.78rem; color: rgba(8,19,26,0.5); line-height: 1.6;">
        記事: {quota_text}
    </div>
    """, unsafe_allow_html=True)
