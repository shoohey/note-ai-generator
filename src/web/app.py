"""
note記事AI自動生成ツール - Web管理画面
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import Settings
from src.db.database import Database
from src.generator.article_generator import ArticleGenerator
from src.generator.style_profile import StyleAnalyzer, StyleProfile
from src.ingester.text_ingester import TextIngester
from src.ingester.url_ingester import URLIngester
from src.output.markdown_writer import MarkdownWriter

# ---------------------------------------------------------------------------
# ページ設定
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="note 記事ジェネレーター",
    page_icon="https://assets.st-note.com/production/uploads/images/favicon/note_favicon.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS - note.com ライクなデザイン
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;600;700&display=swap');

    /* ===== ベースリセット: 全要素をライトモードに強制 ===== */
    html, body, .stApp,
    .stApp *, .stApp *::before, .stApp *::after {
        color-scheme: light !important;
    }
    .stApp {
        background-color: #ffffff !important;
        color: #08131a !important;
        font-family: "Noto Sans JP", "Helvetica Neue", "Hiragino Sans", sans-serif;
    }
    .block-container {
        padding-top: 1.5rem;
        max-width: 1100px;
    }

    /* ===== テキスト色: 全要素 ===== */
    .stApp p, .stApp span, .stApp label, .stApp div, .stApp li, .stApp td, .stApp th,
    .stMarkdown, .stMarkdown p, .stMarkdown span, .stMarkdown li,
    .stMarkdown strong, .stMarkdown em, .stMarkdown a,
    [data-testid="stText"], [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] span,
    [data-testid="stMarkdownContainer"] li {
        color: #08131a !important;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #08131a !important;
    }
    h2 { font-size: 1.15rem; font-weight: 600; }
    hr { border-color: #e6eaed !important; }

    /* ===== サイドバー ===== */
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] > div {
        background-color: #f7f9fa !important;
        border-right: 1px solid #e6eaed;
    }
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] div {
        color: #08131a !important;
    }
    [data-testid="stSidebar"] hr { border-color: #e6eaed !important; }

    .sidebar-logo {
        font-size: 1.2rem; font-weight: 700; color: #08131a;
        padding: 0.3rem 0 0.6rem;
        display: flex; align-items: center; gap: 8px;
    }
    .sidebar-logo .note-mark {
        display: inline-block; background-color: #149274; color: #fff !important;
        font-weight: 700; font-size: 0.75rem; padding: 3px 8px;
        border-radius: 4px; letter-spacing: 0.03em;
    }
    [data-testid="stSidebar"] .stButton > button {
        background: transparent !important; color: rgba(8,19,26,0.66) !important;
        border: none !important; border-radius: 8px; text-align: left;
        padding: 0.55rem 0.9rem; font-size: 0.9rem; font-weight: 500;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: rgba(20,146,116,0.08) !important;
        color: #149274 !important;
    }
    .sidebar-info {
        font-size: 0.78rem; color: rgba(8,19,26,0.45) !important; line-height: 1.5;
    }

    /* ===== カスタムHTML部品 ===== */
    .page-header {
        font-size: 1.5rem; font-weight: 700; color: #08131a !important;
        margin-bottom: 1.5rem; padding-bottom: 0.8rem;
        border-bottom: 1px solid #e6eaed;
    }
    .stat-card {
        background: #f7f9fa !important; border: 1px solid #e6eaed;
        border-radius: 12px; padding: 1.2rem 1rem; text-align: center;
    }
    .stat-card .num {
        font-size: 2rem; font-weight: 700; color: #08131a !important;
        margin: 0; line-height: 1.2;
    }
    .stat-card .label {
        font-size: 0.8rem; color: rgba(8,19,26,0.5) !important;
        margin: 0.25rem 0 0; font-weight: 500;
    }
    .stat-card.green { border-left: 3px solid #149274; }
    .stat-card.blue  { border-left: 3px solid #4c7cf3; }
    .stat-card.amber { border-left: 3px solid #e89d3c; }
    .stat-card.gray  { border-left: 3px solid #8b95a0; }

    .article-card {
        background: #fff !important; border: 1px solid #e6eaed;
        border-radius: 10px; padding: 1rem 1.2rem; margin: 0.4rem 0;
    }
    .article-card:hover {
        border-color: #149274; box-shadow: 0 2px 8px rgba(20,146,116,0.08);
    }
    .article-card .card-title {
        font-weight: 600; color: #08131a !important; font-size: 0.95rem; margin-bottom: 0.3rem;
    }
    .article-card .card-meta {
        font-size: 0.8rem; color: rgba(8,19,26,0.45) !important;
    }
    .badge {
        display: inline-block; font-size: 0.72rem; font-weight: 600;
        padding: 2px 8px; border-radius: 4px; margin-left: 6px; vertical-align: middle;
    }
    .badge-draft    { background: #FFF3CD !important; color: #856404 !important; }
    .badge-reviewed { background: #D1ECF1 !important; color: #0C5460 !important; }
    .badge-published{ background: #D4EDDA !important; color: #155724 !important; }

    .section-title {
        font-size: 0.85rem; font-weight: 600; color: rgba(8,19,26,0.5) !important;
        text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.5rem;
    }
    .goal-text {
        font-size: 0.9rem; color: rgba(8,19,26,0.66) !important;
    }
    .goal-text strong { color: #149274 !important; }

    /* ===== ウィジェットラベル全般 ===== */
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] label,
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] span,
    .stTextInput label, .stTextArea label, .stSelectbox label,
    .stMultiselect label, .stSlider label, .stNumberInput label,
    .stRadio label, .stCheckbox label, .stFileUploader label {
        color: #08131a !important;
    }

    /* ===== 入力フィールド ===== */
    .stTextInput input, .stTextArea textarea, .stNumberInput input {
        color: #08131a !important;
        background-color: #ffffff !important;
        border-color: #e6eaed !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {
        border-color: #149274 !important;
    }
    .stTextArea textarea::placeholder, .stTextInput input::placeholder {
        color: rgba(8,19,26,0.35) !important;
    }
    /* disabled入力 */
    .stTextInput input:disabled, .stTextArea textarea:disabled {
        color: rgba(8,19,26,0.6) !important;
        background-color: #f7f9fa !important;
    }

    /* ===== セレクトボックス ===== */
    .stSelectbox [data-baseweb="select"],
    .stMultiselect [data-baseweb="select"] {
        background-color: #ffffff !important;
    }
    .stSelectbox [data-baseweb="select"] span,
    .stSelectbox [data-baseweb="select"] div,
    .stMultiselect [data-baseweb="select"] span {
        color: #08131a !important;
    }
    /* ドロップダウンメニュー */
    [data-baseweb="popover"], [data-baseweb="menu"],
    [data-baseweb="popover"] ul, [data-baseweb="menu"] ul {
        background-color: #ffffff !important;
    }
    [data-baseweb="menu"] li,
    [data-baseweb="menu"] li span,
    [data-baseweb="menu"] [role="option"],
    [data-baseweb="menu"] [role="option"] span {
        color: #08131a !important;
        background-color: #ffffff !important;
    }
    [data-baseweb="menu"] li:hover,
    [data-baseweb="menu"] [role="option"]:hover {
        background-color: #f7f9fa !important;
    }
    [data-baseweb="tag"] { background-color: #e6eaed !important; }
    [data-baseweb="tag"] span { color: #08131a !important; }

    /* ===== ラジオ・チェックボックス ===== */
    .stRadio div[role="radiogroup"] label,
    .stRadio div[role="radiogroup"] label p,
    .stRadio div[role="radiogroup"] label span,
    .stCheckbox label, .stCheckbox label span,
    .stCheckbox label p {
        color: #08131a !important;
    }

    /* ===== スライダー ===== */
    .stSlider [data-testid="stTickBarMin"],
    .stSlider [data-testid="stTickBarMax"],
    .stSlider div[data-baseweb="slider"] div,
    .stSlider [data-baseweb="thumb"] div {
        color: #08131a !important;
    }

    /* ===== ボタン ===== */
    .stButton > button {
        border-radius: 8px; font-weight: 600; font-size: 0.88rem;
    }
    /* プライマリ = noteグリーン */
    div[data-testid="stBaseButton-primary"] > button,
    .stButton > button[kind="primary"] {
        background-color: #149274 !important;
        border-color: #149274 !important;
        color: #fff !important;
    }
    div[data-testid="stBaseButton-primary"] > button:hover,
    .stButton > button[kind="primary"]:hover {
        background-color: #107c63 !important;
        border-color: #107c63 !important;
        color: #fff !important;
    }
    /* セカンダリ */
    div[data-testid="stBaseButton-secondary"] > button {
        background-color: #ffffff !important;
        color: #08131a !important;
        border: 1px solid #e6eaed !important;
    }
    div[data-testid="stBaseButton-secondary"] > button:hover {
        background-color: #f7f9fa !important;
        color: #149274 !important;
        border-color: #149274 !important;
    }

    /* ===== エクスパンダー ===== */
    [data-testid="stExpander"] {
        background-color: #ffffff !important;
        border-color: #e6eaed !important;
    }
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary span,
    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] summary svg {
        color: #08131a !important;
    }
    [data-testid="stExpander"] [data-testid="stExpanderDetails"],
    [data-testid="stExpander"] > div > div {
        background-color: #ffffff !important;
        color: #08131a !important;
    }

    /* ===== タブ ===== */
    .stTabs [data-baseweb="tab-list"] {
        background-color: transparent !important;
    }
    .stTabs [data-baseweb="tab-list"] button {
        color: rgba(8,19,26,0.6) !important;
    }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        color: #149274 !important;
    }
    .stTabs [data-baseweb="tab-panel"] {
        background-color: #ffffff !important;
        color: #08131a !important;
    }

    /* ===== JSON表示 ===== */
    [data-testid="stJson"],
    [data-testid="stJson"] > div,
    [data-testid="stJson"] * {
        background-color: #f7f9fa !important;
        color: #08131a !important;
    }
    /* react-json-view 対策 */
    .react-json-view {
        background-color: #f7f9fa !important;
        color: #08131a !important;
    }
    .react-json-view .string-value { color: #149274 !important; }
    .react-json-view .object-key { color: #4c7cf3 !important; }
    .react-json-view .int-value,
    .react-json-view .float-value { color: #e89d3c !important; }
    .react-json-view .boolean-value { color: #d35400 !important; }
    .react-json-view .null-value { color: #8b95a0 !important; }
    .react-json-view .icon-container,
    .react-json-view .copy-icon,
    .react-json-view .collapsed-icon,
    .react-json-view .expanded-icon {
        color: rgba(8,19,26,0.4) !important;
    }

    /* ===== コードブロック ===== */
    .stCodeBlock, code, pre,
    [data-testid="stCode"] {
        background-color: #f7f9fa !important;
        color: #08131a !important;
    }

    /* ===== アラート ===== */
    [data-testid="stAlert"] {
        background-color: #f7f9fa !important;
    }
    [data-testid="stAlert"] p,
    [data-testid="stAlert"] span {
        color: inherit !important;
    }

    /* ===== プログレスバー ===== */
    .stProgress > div > div > div > div { background-color: #149274 !important; }

    /* ===== ファイルアップローダー ===== */
    [data-testid="stFileUploader"],
    [data-testid="stFileUploader"] > div {
        background-color: #ffffff !important;
    }
    [data-testid="stFileUploader"] span,
    [data-testid="stFileUploader"] p,
    [data-testid="stFileUploader"] div,
    [data-testid="stFileUploader"] label {
        color: #08131a !important;
    }

    /* ===== スピナー ===== */
    [data-testid="stSpinner"] p,
    [data-testid="stSpinner"] span,
    .stSpinner > div { color: #08131a !important; }

    /* ===== ツールチップ・ポップオーバー ===== */
    [data-baseweb="tooltip"],
    [data-baseweb="tooltip"] div {
        background-color: #08131a !important;
        color: #ffffff !important;
    }

    /* ===== テーブル ===== */
    .stTable, .stDataFrame,
    .stTable th, .stTable td,
    .stDataFrame th, .stDataFrame td {
        background-color: #ffffff !important;
        color: #08131a !important;
        border-color: #e6eaed !important;
    }

    /* ===== カラムコンテナ ===== */
    [data-testid="stHorizontalBlock"],
    [data-testid="stVerticalBlock"],
    [data-testid="column"] {
        background-color: transparent !important;
    }

    /* ===== メインコンテナ背景 ===== */
    .main .block-container,
    .main [data-testid="stAppViewBlockContainer"] {
        background-color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# セッション
# ---------------------------------------------------------------------------

def init_session_state():
    defaults = {"settings": None, "db": None, "page": "dashboard", "proposed_topics": None}
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

def get_settings() -> Settings | None:
    if st.session_state.settings is None:
        try:
            s = Settings.from_env(env_path=PROJECT_ROOT / ".env")
            s.ensure_directories()
            st.session_state.settings = s
        except ValueError:
            return None
    return st.session_state.settings

def get_db() -> Database | None:
    s = get_settings()
    if s is None:
        return None
    if st.session_state.db is None:
        db = Database(s.db_path)
        db.initialize()
        st.session_state.db = db
    return st.session_state.db


# ---------------------------------------------------------------------------
# サイドバー
# ---------------------------------------------------------------------------

def render_sidebar():
    with st.sidebar:
        st.markdown(
            '<div class="sidebar-logo">'
            '<span class="note-mark">note</span> 記事ジェネレーター'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")

        nav = {
            "dashboard": "ダッシュボード",
            "generate":  "記事を生成",
            "articles":  "記事一覧",
            "style":     "スタイル設定",
            "sources":   "ソース管理",
            "settings_page": "設定",
        }
        for key, label in nav.items():
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state.page = key
                st.rerun()

        st.markdown("---")
        s = get_settings()
        if s:
            db = get_db()
            if db:
                cnt = db.fetch_one("SELECT COUNT(*) as cnt FROM generated_articles")["cnt"]
                st.markdown(
                    f'<div class="sidebar-info">'
                    f'モデル: {s.model_name}<br>'
                    f'生成済み: {cnt} 記事'
                    f'</div>',
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# 1,000記事プラン カテゴリ定義
# ---------------------------------------------------------------------------

ARTICLE_CATEGORIES = [
    {"name": "ホワイトエンジン・モチベーション", "target": 120, "keywords": ["ホワイトエンジン", "ブラックエンジン", "モチベーション", "動機", "エンジン"]},
    {"name": "前提・ビリーフの書き換え", "target": 120, "keywords": ["前提", "ビリーフ", "認知", "RAS", "書き換え"]},
    {"name": "コミュニケーション・人間関係", "target": 120, "keywords": ["コミュニケーション", "会話", "人間関係", "雑談", "傾聴"]},
    {"name": "夢実現・自己啓発", "target": 120, "keywords": ["夢", "目標", "実現", "成功", "挑戦"]},
    {"name": "リーダーシップ・チーム", "target": 100, "keywords": ["リーダー", "チーム", "組織", "上機嫌"]},
    {"name": "健康・腸内環境", "target": 100, "keywords": ["健康", "腸", "食事", "腸内", "菌"]},
    {"name": "意識レベル・スピリチュアル", "target": 80, "keywords": ["意識", "レベル", "ホーキンズ", "パワー"]},
    {"name": "セレブ論・豊かさマインド", "target": 80, "keywords": ["セレブ", "豊か", "運", "余白"]},
    {"name": "W1・W2・W3の世界観", "target": 80, "keywords": ["W1", "W2", "W3", "苫米地"]},
    {"name": "日常エッセイ・時事", "target": 80, "keywords": []},
]


def ensure_sources_loaded(db):
    """data/sources/ のファイルが未取り込みならDBに自動インポート"""
    if db is None:
        return
    cnt = db.fetch_one("SELECT COUNT(*) as cnt FROM sources")["cnt"]
    if cnt > 0:
        return
    _auto_crawl_sources(db)


def _auto_crawl_sources(db):
    """data/sources/ からソースを自動取り込み"""
    sources_dir = PROJECT_ROOT / "data" / "sources"
    if not sources_dir.exists():
        st.warning("data/sources/ ディレクトリが見つかりません。")
        return
    files = list(sources_dir.glob("*.txt"))
    if not files:
        st.warning("ソースファイルが見つかりません。")
        return
    title_map = {
        "ameblo_articles": "アメブロ記事集",
        "key_concepts": "キーコンセプト・思想まとめ",
        "profile_detail": "プロフィール詳細",
        "youtube_and_seminars": "YouTube・セミナー情報",
        "note_content": "note記事情報",
        "website_content": "公式サイト情報",
    }
    bar = st.progress(0)
    for i, f in enumerate(files):
        content = f.read_text(encoding="utf-8")
        title = title_map.get(f.stem, f.stem)
        db.execute(
            "INSERT INTO sources (type, title, content) VALUES (?, ?, ?)",
            ("file", title, content),
        )
        bar.progress((i + 1) / len(files))
    st.success(f"{len(files)}件のソースを自動取り込みしました")
    time.sleep(1)
    st.rerun()


def _categorize_article(title: str, topic: str) -> str:
    """記事をカテゴリに分類（キーワードマッチ）"""
    text = f"{title} {topic}"
    for cat in ARTICLE_CATEGORIES:
        if any(kw in text for kw in cat["keywords"]):
            return cat["name"]
    return "日常エッセイ・時事"


def _run_batch_generation(s, db, topics, sel_prof, prof_map, target, source_content):
    """バッチ記事生成の実行"""
    style_profile = None
    pid = prof_map[sel_prof]
    if pid is not None:
        row = db.fetch_one("SELECT name, profile FROM style_profiles WHERE id = ?", (pid,))
        if row:
            style_profile = StyleProfile.from_json(row["name"], row["profile"])

    gen = ArticleGenerator(api_key=s.anthropic_api_key, model=s.model_name)
    writer = MarkdownWriter(s.output_dir)

    bar = st.progress(0)
    stat = st.empty()
    out = st.container()
    generated = []

    for i, t in enumerate(topics):
        topic = t.get("suggested_title", t.get("topic", ""))
        stat.markdown(f"生成中 ({i+1}/{len(topics)}): **{topic}**")
        bar.progress(i / len(topics))
        try:
            result = gen.generate_article(
                topic=topic,
                source_content=source_content[:4000],
                style_profile=style_profile,
                target_length=target,
                min_length=max(target - 500, 1000),
                max_length=target + 1000,
            )
            generated.append(result)
            db.execute(
                "INSERT INTO generated_articles (title, content, topic, word_count, status) VALUES (?, ?, ?, ?, ?)",
                (result["title"], result["body"], topic, result["word_count"], "draft"),
            )
            writer.write_article(title=result["title"], body=result["body"], hashtags=result.get("hashtags"))
            with out:
                st.success(f"{result['title']}  ({result['word_count']:,}文字)")
        except Exception as e:
            with out:
                st.error(f"エラー: {e}")
        if i < len(topics) - 1:
            time.sleep(0.5)

    bar.progress(1.0)
    stat.markdown("**生成完了**")
    if generated:
        total = sum(a["word_count"] for a in generated)
        st.markdown(
            f"**生成結果:** {len(generated)}件 / 合計 {total:,}文字 / 平均 {total // len(generated):,}文字"
        )
    st.session_state["proposed_topics"] = None


def _render_article_plan(db, articles_count):
    """1,000記事プランの進捗表示"""
    st.markdown('<div class="section-title">1,000記事プラン</div>', unsafe_allow_html=True)

    progress = min(articles_count / 1000, 1.0)
    st.progress(progress)
    st.markdown(
        f'<div class="goal-text"><strong>{articles_count}</strong> / 1,000 記事 ({progress*100:.1f}%)</div>',
        unsafe_allow_html=True,
    )

    all_articles = db.fetch_all("SELECT title, topic FROM generated_articles")
    cat_counts = {}
    for a in all_articles:
        cat = _categorize_article(a["title"] or "", a["topic"] or "")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    st.markdown("")
    cols = st.columns(2)
    for i, cat in enumerate(ARTICLE_CATEGORIES):
        with cols[i % 2]:
            cnt = cat_counts.get(cat["name"], 0)
            cat_progress = min(cnt / cat["target"], 1.0) if cat["target"] > 0 else 0
            st.markdown(f"**{cat['name']}**  {cnt}/{cat['target']}")
            st.progress(cat_progress)


# ---------------------------------------------------------------------------
# ダッシュボード
# ---------------------------------------------------------------------------

def page_dashboard():
    st.markdown('<div class="page-header">ダッシュボード</div>', unsafe_allow_html=True)

    s = get_settings()
    if not s:
        st.error(".env にAPIキーが設定されていません。「設定」ページから設定してください。")
        return
    db = get_db()

    articles_count = db.fetch_one("SELECT COUNT(*) as cnt FROM generated_articles")["cnt"]
    sources_count = db.fetch_one("SELECT COUNT(*) as cnt FROM sources")["cnt"]
    profiles_count = db.fetch_one("SELECT COUNT(*) as cnt FROM style_profiles")["cnt"]
    total_chars = db.fetch_one("SELECT COALESCE(SUM(word_count),0) as t FROM generated_articles")["t"]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="stat-card green"><div class="num">{articles_count}</div><div class="label">生成記事数</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="stat-card blue"><div class="num">{total_chars:,}</div><div class="label">合計文字数</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="stat-card amber"><div class="num">{sources_count}</div><div class="label">ソース資料</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="stat-card gray"><div class="num">{profiles_count}</div><div class="label">スタイル</div></div>', unsafe_allow_html=True)

    st.markdown("")

    col_main, col_side = st.columns([5, 2])

    with col_main:
        st.markdown('<div class="section-title">最近の記事</div>', unsafe_allow_html=True)
        recent = db.fetch_all(
            "SELECT id, title, word_count, status, created_at "
            "FROM generated_articles ORDER BY created_at DESC LIMIT 8"
        )
        if recent:
            for row in recent:
                badge_cls = f"badge-{row['status']}"
                status_jp = {"draft": "下書き", "reviewed": "確認済", "published": "公開済"}.get(row["status"], row["status"])
                st.markdown(f"""
                <div class="article-card">
                    <div class="card-title">
                        {row['title']}
                        <span class="badge {badge_cls}">{status_jp}</span>
                    </div>
                    <div class="card-meta">{row['word_count']:,}文字 / {row['created_at']}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("まだ記事がありません。「記事を生成」から始めましょう。")

    with col_side:
        st.markdown('<div class="section-title">1,000記事 目標</div>', unsafe_allow_html=True)
        progress = min(articles_count / 1000, 1.0)
        st.progress(progress)
        st.markdown(
            f'<div class="goal-text"><strong>{articles_count}</strong> / 1,000 記事 ({progress*100:.1f}%)</div>',
            unsafe_allow_html=True,
        )

        st.markdown("")
        st.markdown('<div class="section-title">クイック操作</div>', unsafe_allow_html=True)
        if st.button("AIに記事を提案させる", use_container_width=True, type="primary"):
            st.session_state.page = "generate"
            st.rerun()
        if st.button("ソースを管理する", use_container_width=True):
            st.session_state.page = "sources"
            st.rerun()


# ---------------------------------------------------------------------------
# 記事生成
# ---------------------------------------------------------------------------

def page_generate():
    st.markdown('<div class="page-header">記事を生成</div>', unsafe_allow_html=True)

    s = get_settings()
    if not s:
        st.error("APIキーが設定されていません。「設定」ページから設定してください。")
        return
    db = get_db()
    ensure_sources_loaded(db)

    # --- ソース概要 ---
    sources = db.fetch_all("SELECT id, title, content FROM sources ORDER BY created_at DESC")
    total_chars = sum(len(r["content"]) for r in sources)
    articles_count = db.fetch_one("SELECT COUNT(*) as cnt FROM generated_articles")["cnt"]
    remaining = max(1000 - articles_count, 0)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div class="stat-card green"><div class="num">{len(sources)}</div>'
            f'<div class="label">収集ソース</div></div>', unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="stat-card blue"><div class="num">{total_chars:,}</div>'
            f'<div class="label">総文字数</div></div>', unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="stat-card amber"><div class="num">{articles_count}</div>'
            f'<div class="label">生成済み</div></div>', unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="stat-card gray"><div class="num">{remaining}</div>'
            f'<div class="label">目標まで</div></div>', unsafe_allow_html=True,
        )

    if not sources:
        st.warning("ソースが未登録です。自動収集を実行してコンテンツを取り込みます。")
        if st.button("SNSから自動収集する", type="primary"):
            _auto_crawl_sources(db)
        return

    st.markdown("---")

    # --- 生成設定（コンパクト） ---
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        profiles = db.fetch_all("SELECT id, name FROM style_profiles ORDER BY created_at DESC")
        prof_map = {"デフォルト": None}
        for p in profiles:
            prof_map[p["name"]] = p["id"]
        sel_prof = st.selectbox("スタイル", list(prof_map.keys()))
    with col_s2:
        batch_size = st.slider("生成数", 1, 50, 10)
    with col_s3:
        target = st.slider("目標文字数", 1000, 5000, 2000, step=500)
    with col_s4:
        model_short = s.model_name.replace("claude-", "").split("-2025")[0]
        st.markdown(
            f'<div style="padding-top:1.6rem;">'
            f'<div class="goal-text">モデル: <strong>{model_short}</strong></div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # --- ソースサマリー（AI用） ---
    source_summary = "\n\n---\n\n".join(
        f"【{r['title']}】\n{r['content'][:1500]}" for r in sources[:10]
    )

    # --- AI提案ボタン ---
    if st.button("AIにトピックを提案させる", type="primary", use_container_width=True):
        with st.spinner("収集済みソースを分析してトピックを提案中..."):
            gen = ArticleGenerator(api_key=s.anthropic_api_key, model=s.model_name)
            proposed = gen.extract_topics(source_summary, count=batch_size)
            st.session_state["proposed_topics"] = proposed

    # --- 提案トピック表示 ---
    proposed = st.session_state.get("proposed_topics")
    if proposed:
        st.markdown("")
        st.markdown(
            f'<div class="section-title">提案トピック ({len(proposed)}件)</div>',
            unsafe_allow_html=True,
        )

        selected_topics = []
        for i, t in enumerate(proposed):
            title = t.get("suggested_title", t.get("topic", f"トピック{i+1}"))
            angle = t.get("angle", "")
            checked = st.checkbox(
                f"{i+1}. {title}" + (f"  —  {angle}" if angle else ""),
                value=True,
                key=f"tp_{i}",
            )
            if checked:
                selected_topics.append(t)

        st.markdown("---")
        new_total = articles_count + len(selected_topics)
        st.markdown(
            f'<div class="goal-text">'
            f'<strong>{len(selected_topics)}</strong>件を生成 → '
            f'合計 <strong>{new_total}</strong> / 1,000 記事'
            f'</div>',
            unsafe_allow_html=True,
        )

        if st.button("選択したトピックで生成する", type="primary", use_container_width=True):
            if not selected_topics:
                st.warning("トピックを1つ以上選択してください。")
            else:
                _run_batch_generation(
                    s, db, selected_topics, sel_prof, prof_map, target, source_summary,
                )
    else:
        st.info(
            "「AIにトピックを提案させる」をクリックすると、"
            "収集済みソースをもとにAIが記事トピックを自動提案します。"
        )

    # --- 1,000記事プラン ---
    st.markdown("---")
    _render_article_plan(db, articles_count)


# ---------------------------------------------------------------------------
# 記事一覧
# ---------------------------------------------------------------------------

def page_articles():
    st.markdown('<div class="page-header">記事一覧</div>', unsafe_allow_html=True)
    db = get_db()
    if not db:
        return

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        search = st.text_input("キーワード検索", placeholder="タイトルで検索...")
    with c2:
        status_f = st.selectbox("ステータス", ["すべて", "draft", "reviewed", "published"])
    with c3:
        sort_f = st.selectbox("並び順", ["新しい順", "古い順", "文字数順"])

    q = "SELECT * FROM generated_articles WHERE 1=1"
    p = []
    if search:
        q += " AND title LIKE ?"
        p.append(f"%{search}%")
    if status_f != "すべて":
        q += " AND status = ?"
        p.append(status_f)
    q += {
        "新しい順": " ORDER BY created_at DESC",
        "古い順": " ORDER BY created_at ASC",
        "文字数順": " ORDER BY word_count DESC",
    }[sort_f]

    articles = db.fetch_all(q, tuple(p))
    st.markdown(f"**{len(articles)}件**の記事")

    if not articles:
        st.info("該当する記事がありません。")
        return

    with st.expander("一括操作"):
        if st.button("全記事を削除"):
            st.session_state["confirm_delete_all"] = True
        if st.session_state.get("confirm_delete_all"):
            st.warning("本当にすべての記事を削除しますか？")
            cy, cn = st.columns(2)
            with cy:
                if st.button("削除する", type="primary"):
                    db.execute("DELETE FROM generated_articles")
                    st.session_state["confirm_delete_all"] = False
                    st.rerun()
            with cn:
                if st.button("キャンセル"):
                    st.session_state["confirm_delete_all"] = False
                    st.rerun()

    for a in articles:
        status_jp = {"draft": "下書き", "reviewed": "確認済", "published": "公開済"}.get(a["status"], a["status"])
        with st.expander(f"{a['title']}   ({a['word_count']:,}文字 / {status_jp} / {a['created_at']})"):
            tp, te, tm = st.tabs(["プレビュー", "編集", "メタ情報"])
            with tp:
                st.markdown(a["content"])
            with te:
                nt = st.text_input("タイトル", value=a["title"], key=f"t_{a['id']}")
                nc = st.text_area("本文", value=a["content"], height=400, key=f"c_{a['id']}")
                ns = st.selectbox(
                    "ステータス",
                    ["draft", "reviewed", "published"],
                    index=["draft", "reviewed", "published"].index(a["status"]),
                    key=f"s_{a['id']}",
                )
                cs, cd = st.columns([3, 1])
                with cs:
                    if st.button("保存", key=f"sv_{a['id']}", type="primary"):
                        db.execute(
                            "UPDATE generated_articles SET title=?, content=?, status=?, word_count=? WHERE id=?",
                            (nt, nc, ns, len(nc), a["id"]),
                        )
                        st.success("保存しました")
                        st.rerun()
                with cd:
                    if st.button("削除", key=f"dl_{a['id']}"):
                        db.execute("DELETE FROM generated_articles WHERE id=?", (a["id"],))
                        st.rerun()
            with tm:
                st.json({"id": a["id"], "topic": a["topic"], "word_count": a["word_count"], "status": a["status"], "created_at": a["created_at"]})
                st.text_area("note.com貼り付け用", value=a["content"], height=200, key=f"cp_{a['id']}")


# ---------------------------------------------------------------------------
# スタイル設定
# ---------------------------------------------------------------------------

def page_style():
    st.markdown('<div class="page-header">スタイル設定</div>', unsafe_allow_html=True)
    s = get_settings()
    if not s:
        return
    db = get_db()

    profiles = db.fetch_all("SELECT * FROM style_profiles ORDER BY created_at DESC")
    if profiles:
        st.markdown('<div class="section-title">登録済みプロファイル</div>', unsafe_allow_html=True)
        for p in profiles:
            with st.expander(f"{p['name']}  ({p['created_at']})"):
                pd = json.loads(p["profile"])
                st.markdown(f"**語調:** {pd.get('tone', '未設定')}")
                expr = pd.get("characteristic_expressions", [])
                if expr:
                    st.markdown(f"**特徴的な表現:** {', '.join(expr[:5])}")
                instr = pd.get("writing_instructions", "")
                if instr:
                    st.markdown(f"**ライティング指示:**\n\n{instr}")
                st.json(pd)
                if st.button("削除", key=f"dp_{p['id']}"):
                    db.execute("DELETE FROM style_profiles WHERE id=?", (p["id"],))
                    st.rerun()

    st.markdown("---")
    st.markdown('<div class="section-title">新規プロファイル作成</div>', unsafe_allow_html=True)

    author = st.text_input("著者名", value="山崎拓巳")
    src_type = st.radio("分析ソース", ["テキスト入力", "URLから取得"], horizontal=True)

    if src_type == "テキスト入力":
        sample = st.text_area(
            "分析対象テキスト",
            placeholder="著者の文章を貼り付けてください。\n--- で区切ると複数記事として認識します。",
            height=280,
        )
    else:
        style_urls = st.text_area("URL（1行1つ）", placeholder="https://ameblo.jp/...", height=110)

    if st.button("スタイルを分析する", type="primary"):
        texts = []
        if src_type == "テキスト入力" and sample.strip():
            texts = [t.strip() for t in sample.split("---") if t.strip()]
        elif src_type == "URLから取得" and style_urls.strip():
            with st.spinner("URLからコンテンツを取得中..."):
                ing = URLIngester(request_delay=1.0)
                for u in style_urls.strip().split("\n"):
                    u = u.strip()
                    if u:
                        res = ing.ingest(u)
                        texts.extend(r.content for r in res)
        if not texts:
            st.warning("分析対象のテキストを入力してください。")
        else:
            with st.spinner(f"{len(texts)}件のテキストを分析中..."):
                ana = StyleAnalyzer(api_key=s.anthropic_api_key, model=s.model_name)
                prof = ana.analyze_sync(texts[:5], author)
            st.success(f"プロファイル「{author}」を作成しました")
            st.json(prof.profile_data)
            db.execute(
                "INSERT INTO style_profiles (name, profile, source_articles) VALUES (?, ?, ?)",
                (author, prof.to_json(), json.dumps([t[:200] for t in texts[:5]], ensure_ascii=False)),
            )
            st.rerun()


# ---------------------------------------------------------------------------
# ソース管理
# ---------------------------------------------------------------------------

def page_sources():
    st.markdown('<div class="page-header">ソース管理</div>', unsafe_allow_html=True)
    db = get_db()
    if not db:
        return

    st.markdown('<div class="section-title">ソースを追加</div>', unsafe_allow_html=True)
    add_type = st.radio("追加方法", ["テキスト入力", "URL取得", "ファイルアップロード"], horizontal=True)

    if add_type == "テキスト入力":
        title = st.text_input("タイトル", placeholder="例: 山崎拓巳 講演メモ")
        content = st.text_area("コンテンツ", height=280, placeholder="テキストを入力...")
        if st.button("追加する", type="primary"):
            if title and content:
                db.execute("INSERT INTO sources (type, title, content) VALUES (?, ?, ?)", ("text", title, content))
                st.success(f"「{title}」を追加しました")
                st.rerun()

    elif add_type == "URL取得":
        urls = st.text_area("URL（1行1つ）", placeholder="https://ameblo.jp/...", height=110)
        if st.button("取得して追加", type="primary"):
            if urls.strip():
                ing = URLIngester(request_delay=1.0)
                added = 0
                for u in urls.strip().split("\n"):
                    u = u.strip()
                    if not u:
                        continue
                    with st.spinner(f"取得中: {u[:60]}..."):
                        res = ing.ingest(u)
                        for r in res:
                            db.execute("INSERT INTO sources (type, title, content, url) VALUES (?, ?, ?, ?)", ("url", r.title, r.content, r.url))
                            added += 1
                st.success(f"{added}件のソースを追加しました")
                st.rerun()

    elif add_type == "ファイルアップロード":
        uploaded = st.file_uploader("テキストファイル", type=["txt", "md"], accept_multiple_files=True)
        if uploaded and st.button("追加する", type="primary"):
            for f in uploaded:
                c = f.read().decode("utf-8", errors="replace")
                db.execute("INSERT INTO sources (type, title, content) VALUES (?, ?, ?)", ("text", f.name, c))
            st.success(f"{len(uploaded)}ファイルを追加しました")
            st.rerun()

    st.markdown("---")
    st.markdown('<div class="section-title">登録済みソース</div>', unsafe_allow_html=True)
    sources = db.fetch_all("SELECT * FROM sources ORDER BY created_at DESC")
    if not sources:
        st.info("ソースが登録されていません。")
        return
    st.markdown(f"**{len(sources)}件**のソース")
    for src in sources:
        with st.expander(f"{src['title']}  ({src['type']} / {src['created_at']})"):
            st.text_area("内容", value=src["content"][:3000], height=180, key=f"sr_{src['id']}", disabled=True)
            if src["url"]:
                st.markdown(f"URL: {src['url']}")
            if st.button("削除", key=f"ds_{src['id']}"):
                db.execute("DELETE FROM sources WHERE id=?", (src["id"],))
                st.rerun()


# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------

def page_settings():
    st.markdown('<div class="page-header">設定</div>', unsafe_allow_html=True)
    env_path = PROJECT_ROOT / ".env"

    st.markdown('<div class="section-title">API設定</div>', unsafe_allow_html=True)
    cur = {}
    if env_path.exists():
        for line in env_path.read_text().strip().split("\n"):
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cur[k.strip()] = v.strip()

    api_key = st.text_input("APIキー", value=cur.get("ANTHROPIC_API_KEY", ""), type="password")
    model = st.selectbox("モデル", [
        "claude-sonnet-4-20250514",
        "claude-3-haiku-20240307",
        "claude-sonnet-4-5-20250514",
        "claude-3-5-sonnet-20241022",
    ])
    out_dir = st.text_input("出力ディレクトリ", value=cur.get("NOTE_GENERATOR_OUTPUT_DIR", "data/output"))

    if st.button("設定を保存", type="primary"):
        env_path.write_text(
            f"ANTHROPIC_API_KEY={api_key}\n"
            f"NOTE_GENERATOR_MODEL={model}\n"
            f"NOTE_GENERATOR_DB_PATH={cur.get('NOTE_GENERATOR_DB_PATH', 'data/note_generator.db')}\n"
            f"NOTE_GENERATOR_OUTPUT_DIR={out_dir}\n",
            encoding="utf-8",
        )
        st.session_state.settings = None
        st.session_state.db = None
        st.success("設定を保存しました")
        st.rerun()

    st.markdown("---")
    st.markdown('<div class="section-title">データベース</div>', unsafe_allow_html=True)
    s = get_settings()
    if s:
        db = get_db()
        st.markdown(f"パス: `{s.db_path}`")
        for tbl in ["sources", "style_profiles", "generated_articles", "scrape_cache"]:
            cnt = db.fetch_one(f"SELECT COUNT(*) as cnt FROM {tbl}")["cnt"]
            st.markdown(f"- {tbl}: **{cnt}** 行")


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main():
    init_session_state()
    render_sidebar()
    p = st.session_state.page
    {"dashboard": page_dashboard, "generate": page_generate, "articles": page_articles,
     "style": page_style, "sources": page_sources, "settings_page": page_settings,
    }.get(p, page_dashboard)()

if __name__ == "__main__":
    main()
