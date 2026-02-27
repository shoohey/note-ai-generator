#!/usr/bin/env python3
"""
デモスクリプト

note記事AI自動生成ツールのエンドツーエンドデモ。
以下のフローを実行する:

1. note.comから人気記事をスクレイピング
2. 書き方パターン分析
3. ブログ記事の取り込み（AmebloまたはサンプルURL）
4. Claude APIでスタイルプロファイル生成
5. 取り込みコンテンツからトピック抽出
6. 記事生成（Richプログレスバー表示）
7. Markdownファイル出力 + サマリー表示

使用方法:
    python scripts/demo.py
    python scripts/demo.py --skip-scrape  # スクレイピングをスキップ
    python scripts/demo.py --articles 5   # 生成記事数を指定
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from src.config import Settings
from src.db.database import Database
from src.generator.article_generator import ArticleGenerator
from src.generator.style_profile import StyleAnalyzer, StyleProfile
from src.ingester.url_ingester import URLIngester
from src.ingester.text_ingester import TextIngester
from src.output.markdown_writer import ExportManager, MarkdownWriter
from src.scraper.article_parser import ArticleParser
from src.scraper.models import NoteArticle, WritingPattern
from src.scraper.note_client import NoteClient
from src.scraper.trend_analyzer import TrendAnalyzer

console = Console()


# ---------------------------------------------------------------------------
# デモ設定
# ---------------------------------------------------------------------------

# note.comで検索するハッシュタグ
DEMO_HASHTAGS = [
    "自己成長",
    "コーチング",
    "モチベーション",
    "習慣化",
    "目標達成",
]

# 山﨑拓巳さんのnote/ブログクリエイター名（あれば）
DEMO_CREATOR = "takumi_yamazaki"

# デモ用サンプルブログURL（Ameblo等）
DEMO_BLOG_URLS = [
    "https://ameblo.jp/takumi-yamazaki/",
]

# 生成記事のデフォルト数
DEFAULT_ARTICLE_COUNT = 10


# ---------------------------------------------------------------------------
# デモ用サンプルデータ（スクレイピングできない場合のフォールバック）
# ---------------------------------------------------------------------------

SAMPLE_ARTICLES = [
    NoteArticle(
        id="sample_1",
        title="朝5分の習慣が人生を変える理由",
        body="""
        <p>「たった5分で何が変わるの？」そう思った方、ちょっと待ってください。</p>
        <p>私は3年前、毎朝5分だけ瞑想を始めました。最初は「こんなので変わるわけない」と半信半疑でした。</p>
        <h2>なぜ5分なのか</h2>
        <p>人間の脳は、新しい習慣を始めるとき、大きすぎる目標に抵抗します。30分の運動、1時間の読書...。ハードルが高すぎるのです。</p>
        <p>でも5分なら？「まあ、5分くらいならやってみるか」と思えませんか？</p>
        <h2>私の場合の変化</h2>
        <p>最初の1ヶ月は正直、何も変わらない気がしました。でも2ヶ月目あたりから、日中の集中力が明らかに違うことに気づいたんです。</p>
        <p>3ヶ月後には、朝の5分が10分になり、気づけば朝活の習慣そのものができていました。</p>
        <h2>あなたも今日から</h2>
        <p>大切なのは「完璧にやること」ではなく「続けること」です。今日の夜、明日の朝に何をするか、たった1つだけ決めてみてください。</p>
        <p>5分が、あなたの人生を変える最初の一歩になるかもしれません。</p>
        """,
        author="サンプル著者",
        url="https://note.com/sample/n/sample1",
        published_at="2024-01-15T10:00:00",
        metrics=__import__("src.scraper.models", fromlist=["ArticleMetrics"]).ArticleMetrics(
            like_count=245, comment_count=12
        ),
        hashtags=["朝活", "習慣化", "自己成長", "瞑想"],
    ),
    NoteArticle(
        id="sample_2",
        title="「やりたいこと」が見つからない人へ",
        body="""
        <p>20代の頃、私は「やりたいことが見つからない」と悩んでいました。</p>
        <p>周りの友人が起業したり、転職したり、海外に行ったり。みんなキラキラして見えて、自分だけが取り残されている気がしていました。</p>
        <h2>「やりたいこと」の正体</h2>
        <p>ある日、メンターに言われた言葉が忘れられません。</p>
        <p>「やりたいことは、探すものじゃない。やっているうちに見つかるものだ」</p>
        <p>目から鱗でした。私は「完璧なやりたいこと」を探していたのです。でも、そんなものは最初からわかるはずがない。</p>
        <h2>まずは「気になること」から</h2>
        <p>やりたいことがわからないなら、まず「ちょっと気になること」を3つ書き出してみてください。</p>
        <p>・最近読んで面白かった本のジャンル<br>
        ・SNSでつい見てしまうアカウントの分野<br>
        ・友人と話していて楽しくなるテーマ</p>
        <p>この中にヒントがあります。</p>
        <h2>完璧じゃなくていい</h2>
        <p>「やりたいこと」は途中で変わっていいんです。大切なのは、今日何か1つ、行動してみること。</p>
        <p>あなたの「やりたいこと」は、動き出した先にきっと見つかります。</p>
        """,
        author="サンプル著者",
        url="https://note.com/sample/n/sample2",
        published_at="2024-02-01T09:00:00",
        metrics=__import__("src.scraper.models", fromlist=["ArticleMetrics"]).ArticleMetrics(
            like_count=389, comment_count=24
        ),
        hashtags=["自己成長", "キャリア", "20代", "やりたいこと"],
    ),
    NoteArticle(
        id="sample_3",
        title="失敗を恐れない人がやっている3つのこと",
        body="""
        <p>失敗が怖い。誰だってそうです。</p>
        <p>でも、世の中で成功している人たちに共通しているのは「失敗を恐れないこと」ではなく、「失敗との付き合い方がうまいこと」なんです。</p>
        <h2>1. 失敗を「データ」として扱う</h2>
        <p>成功する人は、失敗したとき「自分はダメだ」とは思いません。「このやり方ではうまくいかない、ということがわかった」と捉えます。</p>
        <p>エジソンの有名な言葉がありますよね。「私は失敗したのではない。うまくいかない方法を1万通り見つけたのだ」と。</p>
        <h2>2. 「小さな失敗」を日常に組み込む</h2>
        <p>いきなり大きな挑戦をして大きく失敗すると、立ち直りに時間がかかります。</p>
        <p>だからこそ、日常の中で小さな挑戦をたくさんする。新しいお店に入ってみる。知らない人に話しかけてみる。そんな小さなことでいいんです。</p>
        <h2>3. 失敗を人に話す</h2>
        <p>失敗を隠そうとすると、それが重荷になります。信頼できる人に「こんな失敗しちゃって」と話してみてください。</p>
        <p>意外と「自分もそうだった」という共感が返ってきます。失敗は一人で抱え込むものではないのです。</p>
        <h2>今日からできること</h2>
        <p>まずは、最近の小さな失敗を1つ思い出して、「そこから何を学んだか」を考えてみてください。失敗が学びに変わる瞬間を体験できるはずです。</p>
        """,
        author="サンプル著者",
        url="https://note.com/sample/n/sample3",
        published_at="2024-02-10T08:30:00",
        metrics=__import__("src.scraper.models", fromlist=["ArticleMetrics"]).ArticleMetrics(
            like_count=512, comment_count=31
        ),
        hashtags=["失敗", "成功", "マインドセット", "自己成長", "挑戦"],
    ),
]

# 山﨑拓巳さん風のサンプルコンテンツ（スタイル分析用）
SAMPLE_YAMAZAKI_CONTENT = [
    """
    人生を変えるのに、特別な才能はいらない。

    僕がいつも思うのは、「成功する人と成功しない人の違い」って、実はすごくシンプルだってこと。

    それは「やるか、やらないか」。

    たったそれだけなんです。

    でもね、ほとんどの人は「やらない理由」を見つけるのが上手い。
    「時間がない」「お金がない」「才能がない」「もう遅い」...

    全部、言い訳です。厳しいことを言うようだけど、本当のことです。

    僕が20代の頃、ある経営者に言われた言葉があります。
    「拓巳、やりたいことがあるなら今日やれ。明日はもう別の人生だ」

    この言葉で僕は変わりました。

    あなたも今日、何か1つだけ「やりたかったけど先延ばしにしていたこと」をやってみてください。
    きっと、世界が少しだけ変わって見えるはずです。
    """,
    """
    「凡人こそ、最強」って知ってた？

    世の中では、天才ばかりがもてはやされる。
    でも僕は、本当にすごいのは「凡人なのに結果を出す人」だと思っている。

    なぜか？

    天才は、天才だから成功する。再現性がない。
    でも凡人が成功したら、それは「仕組み」で勝ったということ。
    仕組みは、誰にでも使える。

    僕自身、天才じゃない。学生時代の成績も普通。特別な才能もない。
    でもね、1つだけ人より上手くできることがあった。

    それは「続けること」。

    毎日1%でも成長すれば、1年後には37倍になる。
    これ、数学的に証明されているんです。

    だから僕は「天才になろう」とは思わない。
    「毎日1%」を積み重ねることだけを考えている。

    あなたの今日の1%は何ですか？
    """,
    """
    人は「言葉」で変わる。

    僕が講演やセミナーをやっていて、いつも感じることがある。
    同じ話を聞いても、変わる人と変わらない人がいる。

    その違いは何か。

    「自分ごと」として聞いているかどうか。

    「いい話だったな〜」で終わる人は変わらない。
    「これ、自分の場合はどうだろう？」と考える人は変わる。

    言葉には力がある。でも、その力を引き出すのはあなた自身なんです。

    今日あなたが出会う言葉の中に、人生を変える一言があるかもしれない。
    アンテナを立てて、過ごしてみてください。
    """,
]


# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------


def parse_args():
    """コマンドライン引数をパースする。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="note記事AI自動生成ツール デモ"
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="note.comスクレイピングをスキップしてサンプルデータを使用",
    )
    parser.add_argument(
        "--articles",
        type=int,
        default=DEFAULT_ARTICLE_COUNT,
        help=f"生成する記事数 (デフォルト: {DEFAULT_ARTICLE_COUNT})",
    )
    parser.add_argument(
        "--blog-urls",
        nargs="*",
        help="取り込むブログ記事のURL",
    )
    parser.add_argument(
        "--creator",
        type=str,
        default=DEMO_CREATOR,
        help="note.comクリエイター名",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# デモの各ステップ
# ---------------------------------------------------------------------------


def step1_scrape_articles(
    skip_scrape: bool = False, creator: str = DEMO_CREATOR
) -> list[NoteArticle]:
    """Step 1: note.comから人気記事をスクレイピング"""
    console.print(
        Panel(
            "[bold]Step 1: note.com 人気記事スクレイピング[/bold]",
            style="blue",
        )
    )

    if skip_scrape:
        console.print("[yellow]スクレイピングをスキップ。サンプルデータを使用します。[/yellow]")
        return SAMPLE_ARTICLES

    client = NoteClient(request_delay=2.0, max_retries=3)
    articles: list[NoteArticle] = []

    # クリエイターの記事を取得
    console.print(f"\n[cyan]クリエイター '{creator}' の記事を取得中...[/cyan]")
    try:
        raw_articles = client.get_creator_articles(creator, page=1, per_page=10)
        for raw in raw_articles:
            try:
                article = ArticleParser.parse_api_response(raw)
                # 本文が空なら詳細を取得
                if not article.body and article.id:
                    body = client.get_article_body(article.id)
                    if body:
                        article.body = body
                articles.append(article)
            except Exception as e:
                console.print(f"[yellow]記事パースエラー: {e}[/yellow]")
    except Exception as e:
        console.print(f"[yellow]クリエイター記事取得エラー: {e}[/yellow]")

    # ハッシュタグで記事検索
    for tag in DEMO_HASHTAGS[:3]:  # 最初の3タグのみ
        console.print(f"\n[cyan]ハッシュタグ '#{tag}' で検索中...[/cyan]")
        try:
            raw_results = client.search_by_hashtag(tag, page=1)
            for raw in raw_results[:5]:  # 各タグ最大5件
                try:
                    article = ArticleParser.parse_api_response(raw)
                    articles.append(article)
                except Exception as e:
                    console.print(f"[yellow]記事パースエラー: {e}[/yellow]")
        except Exception as e:
            console.print(f"[yellow]ハッシュタグ検索エラー (#{tag}): {e}[/yellow]")

    if not articles:
        console.print("[yellow]記事を取得できませんでした。サンプルデータを使用します。[/yellow]")
        return SAMPLE_ARTICLES

    console.print(f"\n[green]合計 {len(articles)} 件の記事を取得しました[/green]")
    return articles


def step2_analyze_patterns(articles: list[NoteArticle]) -> WritingPattern:
    """Step 2: 書き方パターン分析"""
    console.print(
        Panel(
            "[bold]Step 2: 書き方パターン分析[/bold]",
            style="blue",
        )
    )

    analyzer = TrendAnalyzer()
    analyzer.add_articles(articles)
    pattern = analyzer.analyze()
    return pattern


def step3_ingest_content(blog_urls: list[str] | None = None) -> list[str]:
    """Step 3: ブログ記事/コンテンツの取り込み"""
    console.print(
        Panel(
            "[bold]Step 3: コンテンツ取り込み[/bold]",
            style="blue",
        )
    )

    contents: list[str] = []

    # URLからの取り込み
    if blog_urls:
        console.print(f"[cyan]{len(blog_urls)} 件のURLからコンテンツを取り込み中...[/cyan]")
        ingester = URLIngester(request_delay=1.5)
        for url in blog_urls:
            try:
                source_contents = ingester.ingest(url)
                for sc in source_contents:
                    contents.append(sc.content)
                    console.print(f"  [green]取り込み完了: {sc.title[:50]}[/green]")
            except Exception as e:
                console.print(f"  [yellow]取り込みエラー ({url}): {e}[/yellow]")

    # data/sources/ にテキストファイルがあれば取り込む
    sources_dir = project_root / "data" / "sources"
    if sources_dir.exists():
        text_files = list(sources_dir.glob("*.txt")) + list(sources_dir.glob("*.md"))
        if text_files:
            console.print(f"\n[cyan]{len(text_files)} 件のテキストファイルを取り込み中...[/cyan]")
            ingester_text = TextIngester()
            for tf in text_files:
                try:
                    source_contents = ingester_text.ingest(str(tf))
                    for sc in source_contents:
                        contents.append(sc.content)
                        console.print(f"  [green]取り込み完了: {sc.title[:50]}[/green]")
                except Exception as e:
                    console.print(f"  [yellow]取り込みエラー ({tf.name}): {e}[/yellow]")

    # コンテンツが取得できなかった場合はサンプルを使用
    if not contents:
        console.print("[yellow]外部コンテンツなし。サンプルコンテンツを使用します。[/yellow]")
        contents = SAMPLE_YAMAZAKI_CONTENT

    console.print(f"\n[green]合計 {len(contents)} 件のコンテンツを取り込みました[/green]")
    return contents


def step4_create_style_profile(
    contents: list[str], settings: Settings
) -> StyleProfile:
    """Step 4: Claude APIでスタイルプロファイル生成"""
    console.print(
        Panel(
            "[bold]Step 4: スタイルプロファイル生成[/bold]",
            style="blue",
        )
    )

    analyzer = StyleAnalyzer(
        api_key=settings.anthropic_api_key,
        model=settings.model_name,
    )

    with console.status("[cyan]Claude APIでスタイルを分析中...[/cyan]"):
        profile = analyzer.analyze_sync(
            articles=contents[:5],  # 最大5記事で分析
            author_name="山﨑拓巳",
        )

    console.print(f"\n[green]スタイルプロファイル生成完了[/green]")
    console.print(f"  語調: {profile.tone}")
    if profile.characteristic_expressions:
        console.print(f"  特徴的な表現: {', '.join(profile.characteristic_expressions[:5])}")
    console.print(f"  プロファイルキー: {list(profile.profile_data.keys())}")

    return profile


def step5_extract_topics(
    contents: list[str], settings: Settings, count: int = 10
) -> list[dict]:
    """Step 5: トピック抽出"""
    console.print(
        Panel(
            "[bold]Step 5: トピック抽出[/bold]",
            style="blue",
        )
    )

    generator = ArticleGenerator(
        api_key=settings.anthropic_api_key,
        model=settings.model_name,
        prompts_dir="prompts",
    )

    # コンテンツを結合（最大10000文字）
    combined = "\n\n---\n\n".join(contents)
    if len(combined) > 10000:
        combined = combined[:10000] + "\n\n（以下省略）"

    with console.status(f"[cyan]Claude APIで {count} 件のトピックを抽出中...[/cyan]"):
        topics = generator.extract_topics(combined, count=count)

    # トピック一覧をテーブルで表示
    table = Table(title="抽出されたトピック")
    table.add_column("#", style="dim", width=3)
    table.add_column("トピック", style="cyan", max_width=30)
    table.add_column("切り口", max_width=30)
    table.add_column("タイトル案", style="green", max_width=40)

    for i, topic in enumerate(topics, 1):
        table.add_row(
            str(i),
            topic.get("topic", ""),
            topic.get("angle", ""),
            topic.get("suggested_title", ""),
        )

    console.print(table)
    return topics


def step6_generate_articles(
    topics: list[dict],
    contents: list[str],
    style_profile: StyleProfile,
    writing_pattern: WritingPattern,
    settings: Settings,
    count: int = 10,
) -> list[dict]:
    """Step 6: 記事生成"""
    console.print(
        Panel(
            f"[bold]Step 6: {count} 件の記事を生成[/bold]",
            style="blue",
        )
    )

    generator = ArticleGenerator(
        api_key=settings.anthropic_api_key,
        model=settings.model_name,
        prompts_dir="prompts",
    )

    # 参考コンテンツ（最大3000文字に制限）
    source_text = "\n\n".join(contents)
    if len(source_text) > 3000:
        source_text = source_text[:3000] + "\n\n（以下省略）"

    articles: list[dict] = []
    topics_to_use = topics[:count]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("記事生成中...", total=len(topics_to_use))

        for i, topic_data in enumerate(topics_to_use):
            topic = topic_data.get("topic", topic_data.get("suggested_title", f"トピック{i+1}"))
            progress.update(task, description=f"生成中: {topic[:30]}...")

            try:
                result = generator.generate_article(
                    topic=topic,
                    source_content=source_text,
                    style_profile=style_profile,
                    writing_pattern=writing_pattern,
                    target_length=2000,
                    min_length=settings.article_min_length,
                    max_length=settings.article_max_length,
                )
                articles.append(result)
                console.print(
                    f"  [green]#{i+1} 生成完了: {result['title'][:40]} "
                    f"({result['word_count']}文字)[/green]"
                )
            except Exception as e:
                console.print(f"  [red]#{i+1} 生成エラー ({topic[:30]}): {e}[/red]")

            progress.advance(task)

            # API レート制限を考慮して少し待機
            if i < len(topics_to_use) - 1:
                time.sleep(1)

    console.print(
        f"\n[green]{len(articles)} / {len(topics_to_use)} 件の記事を生成しました[/green]"
    )
    return articles


def step7_output_articles(articles: list[dict], settings: Settings) -> list[Path]:
    """Step 7: Markdownファイル出力 + サマリー表示"""
    console.print(
        Panel(
            "[bold]Step 7: Markdown出力 + サマリー[/bold]",
            style="blue",
        )
    )

    # バッチディレクトリ作成
    export_manager = ExportManager(settings.output_dir)
    batch_dir = export_manager.create_batch_dir()

    # Markdown出力
    writer = MarkdownWriter(str(batch_dir))
    paths = writer.write_batch(articles)

    # サマリー表示
    console.print(f"\n[green]出力先: {batch_dir}[/green]")

    table = Table(title="生成記事サマリー")
    table.add_column("#", style="dim", width=3)
    table.add_column("タイトル", style="cyan", max_width=40)
    table.add_column("文字数", justify="right", width=8)
    table.add_column("ハッシュタグ", max_width=30)
    table.add_column("ファイル", style="dim", max_width=30)

    total_chars = 0
    for i, (article, path) in enumerate(zip(articles, paths), 1):
        wc = article.get("word_count", 0)
        total_chars += wc
        tags = ", ".join(f"#{t}" for t in article.get("hashtags", [])[:3])
        table.add_row(
            str(i),
            article.get("title", "")[:40],
            f"{wc:,}",
            tags,
            path.name[:30],
        )

    console.print(table)

    console.print(
        Panel(
            f"[bold green]完了！[/bold green]\n"
            f"  生成記事数: {len(articles)} 件\n"
            f"  合計文字数: {total_chars:,} 文字\n"
            f"  平均文字数: {total_chars // max(len(articles), 1):,} 文字\n"
            f"  出力先:     {batch_dir}",
            title="結果",
            style="green",
        )
    )

    return paths


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------


def main():
    """デモのメイン実行関数。"""
    args = parse_args()

    console.print(
        Panel(
            "[bold magenta]note記事AI自動生成ツール[/bold magenta]\n"
            "山﨑拓巳さんスタイルでnote記事を自動生成するデモ",
            title="Demo",
            style="magenta",
        )
    )

    # --- 設定読み込み ---
    try:
        settings = Settings.from_env(env_path=project_root / ".env")
    except ValueError as e:
        console.print(f"[red]設定エラー: {e}[/red]")
        console.print("[yellow]ヒント: .env.example を .env にコピーしてAPIキーを設定してください[/yellow]")
        sys.exit(1)

    settings.ensure_directories()

    # --- DB初期化 ---
    db = Database(settings.db_path)
    db.initialize()
    console.print("[dim]データベース初期化完了[/dim]")

    start_time = time.time()

    # --- Step 1: スクレイピング ---
    articles = step1_scrape_articles(
        skip_scrape=args.skip_scrape,
        creator=args.creator,
    )

    # --- Step 2: パターン分析 ---
    writing_pattern = step2_analyze_patterns(articles)

    # --- Step 3: コンテンツ取り込み ---
    contents = step3_ingest_content(blog_urls=args.blog_urls)

    # --- Step 4: スタイルプロファイル ---
    style_profile = step4_create_style_profile(contents, settings)

    # --- Step 5: トピック抽出 ---
    topics = step5_extract_topics(
        contents, settings, count=args.articles
    )

    # --- Step 6: 記事生成 ---
    generated_articles = step6_generate_articles(
        topics=topics,
        contents=contents,
        style_profile=style_profile,
        writing_pattern=writing_pattern,
        settings=settings,
        count=args.articles,
    )

    # --- Step 7: 出力 ---
    if generated_articles:
        step7_output_articles(generated_articles, settings)
    else:
        console.print("[red]記事が生成されませんでした。[/red]")

    elapsed = time.time() - start_time
    console.print(f"\n[dim]総実行時間: {elapsed:.1f}秒[/dim]")


if __name__ == "__main__":
    main()
