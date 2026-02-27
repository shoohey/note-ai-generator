"""
CLI エントリポイント

Click を使った note 記事 AI 自動生成ツールのコマンドラインインタフェース。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import click
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
from src.ingester.text_ingester import TextIngester
from src.ingester.url_ingester import URLIngester
from src.output.markdown_writer import ExportManager, MarkdownWriter
from src.scraper.article_parser import ArticleParser
from src.scraper.note_client import NoteClient
from src.scraper.trend_analyzer import TrendAnalyzer

console = Console()


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def _load_settings(ctx: click.Context) -> Settings:
    """Clickコンテキストから設定を取得する。"""
    return ctx.obj["settings"]


def _get_db(settings: Settings) -> Database:
    """データベースインスタンスを取得・初期化する。"""
    db = Database(settings.db_path)
    db.initialize()
    return db


# ---------------------------------------------------------------------------
# CLIグループ
# ---------------------------------------------------------------------------


@click.group()
@click.option(
    "--env-file",
    type=click.Path(exists=False),
    default=None,
    help=".envファイルのパス",
)
@click.pass_context
def cli(ctx: click.Context, env_file: str | None) -> None:
    """note記事AI自動生成ツール"""
    ctx.ensure_object(dict)
    try:
        settings = Settings.from_env(env_path=env_file)
        settings.ensure_directories()
        ctx.obj["settings"] = settings
    except ValueError as e:
        console.print(f"[red]設定エラー: {e}[/red]")
        console.print(
            "[yellow]ヒント: .env.example を .env にコピーしてAPIキーを設定してください[/yellow]"
        )
        ctx.exit(1)


# ---------------------------------------------------------------------------
# scrape コマンド
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--creator", "-c", required=True, help="note.comクリエイター名")
@click.option("--pages", "-p", type=int, default=2, help="取得ページ数")
@click.option("--hashtags", "-t", multiple=True, help="検索するハッシュタグ")
@click.pass_context
def scrape(
    ctx: click.Context,
    creator: str,
    pages: int,
    hashtags: tuple[str, ...],
) -> None:
    """note.comから記事をスクレイピングする"""
    settings = _load_settings(ctx)

    console.print(
        Panel(f"[bold]note.com スクレイピング: {creator}[/bold]", style="blue")
    )

    client = NoteClient(
        request_delay=settings.request_delay,
        max_retries=settings.max_retries,
    )

    articles = []

    # クリエイター記事の取得
    for page in range(1, pages + 1):
        console.print(f"[cyan]ページ {page}/{pages} を取得中...[/cyan]")
        raw_articles = client.get_creator_articles(creator, page=page)
        for raw in raw_articles:
            try:
                article = ArticleParser.parse_api_response(raw)
                articles.append(article)
            except Exception as e:
                console.print(f"[yellow]パースエラー: {e}[/yellow]")

    # ハッシュタグ検索
    for tag in hashtags:
        console.print(f"[cyan]ハッシュタグ '#{tag}' を検索中...[/cyan]")
        raw_results = client.search_by_hashtag(tag)
        for raw in raw_results[:10]:
            try:
                article = ArticleParser.parse_api_response(raw)
                articles.append(article)
            except Exception as e:
                console.print(f"[yellow]パースエラー: {e}[/yellow]")

    console.print(f"[green]合計 {len(articles)} 件の記事を取得しました[/green]")

    # パターン分析
    if articles:
        analyzer = TrendAnalyzer()
        analyzer.add_articles(articles)
        pattern = analyzer.analyze()

        # パターンをJSONで保存
        pattern_path = Path(settings.output_dir) / "writing_pattern.json"
        pattern_data = {
            "avg_paragraph_length": pattern.avg_paragraph_length,
            "avg_heading_count": pattern.avg_heading_count,
            "common_opening_styles": pattern.common_opening_styles,
            "common_closing_styles": pattern.common_closing_styles,
            "avg_word_count": pattern.avg_word_count,
            "hashtag_frequency": pattern.hashtag_frequency,
            "structural_patterns": pattern.structural_patterns,
        }
        pattern_path.write_text(
            json.dumps(pattern_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        console.print(f"[green]パターン分析結果を保存: {pattern_path}[/green]")


# ---------------------------------------------------------------------------
# ingest コマンド
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("sources", nargs=-1, required=True)
@click.option(
    "--type",
    "source_type",
    type=click.Choice(["url", "text", "auto"]),
    default="auto",
    help="ソースタイプ",
)
@click.pass_context
def ingest(
    ctx: click.Context,
    sources: tuple[str, ...],
    source_type: str,
) -> None:
    """コンテンツを取り込む（URL、テキストファイル）"""
    settings = _load_settings(ctx)

    console.print(
        Panel(f"[bold]コンテンツ取り込み: {len(sources)} 件[/bold]", style="blue")
    )

    all_contents = []

    for source in sources:
        # ソースタイプの自動判別
        if source_type == "auto":
            if source.startswith(("http://", "https://")):
                actual_type = "url"
            else:
                actual_type = "text"
        else:
            actual_type = source_type

        try:
            if actual_type == "url":
                ingester = URLIngester(request_delay=settings.request_delay)
            else:
                ingester = TextIngester()

            results = ingester.ingest(source)
            all_contents.extend(results)
            console.print(f"  [green]{source}: {len(results)} 件取り込み[/green]")

        except Exception as e:
            console.print(f"  [red]{source}: エラー - {e}[/red]")

    # 取り込み結果をDBに保存
    if all_contents:
        db = _get_db(settings)
        for content in all_contents:
            db.execute(
                "INSERT INTO sources (type, title, content, url, metadata) VALUES (?, ?, ?, ?, ?)",
                (
                    content.content_type,
                    content.title,
                    content.content,
                    content.url,
                    json.dumps(content.metadata, ensure_ascii=False),
                ),
            )

    console.print(f"\n[green]合計 {len(all_contents)} 件のコンテンツを取り込みました[/green]")


# ---------------------------------------------------------------------------
# analyze-style コマンド
# ---------------------------------------------------------------------------


@cli.command("analyze-style")
@click.option("--author", "-a", required=True, help="著者名")
@click.option("--source-dir", "-d", help="分析対象テキストのディレクトリ")
@click.option("--source-urls", "-u", multiple=True, help="分析対象のURL")
@click.option("--output", "-o", help="プロファイル出力先（JSON）")
@click.pass_context
def analyze_style(
    ctx: click.Context,
    author: str,
    source_dir: str | None,
    source_urls: tuple[str, ...],
    output: str | None,
) -> None:
    """著者のスタイルを分析してプロファイルを生成する"""
    settings = _load_settings(ctx)

    console.print(
        Panel(f"[bold]スタイル分析: {author}[/bold]", style="blue")
    )

    # コンテンツ収集
    texts: list[str] = []

    if source_dir:
        ingester = TextIngester()
        results = ingester.ingest(source_dir)
        texts.extend(r.content for r in results)

    for url in source_urls:
        ingester_url = URLIngester()
        results = ingester_url.ingest(url)
        texts.extend(r.content for r in results)

    # DBからも取得
    if not texts:
        db = _get_db(settings)
        rows = db.fetch_all("SELECT content FROM sources ORDER BY created_at DESC LIMIT 10")
        texts.extend(row["content"] for row in rows)

    if not texts:
        console.print("[red]分析対象のコンテンツがありません。[/red]")
        ctx.exit(1)
        return

    console.print(f"[cyan]{len(texts)} 件のテキストを分析中...[/cyan]")

    analyzer = StyleAnalyzer(
        api_key=settings.anthropic_api_key,
        model=settings.model_name,
    )

    with console.status("[cyan]Claude APIでスタイルを分析中...[/cyan]"):
        profile = analyzer.analyze_sync(texts[:5], author)

    # 結果表示
    console.print(f"\n[green]スタイルプロファイル生成完了: {author}[/green]")
    console.print(f"  語調: {profile.tone}")
    if profile.characteristic_expressions:
        console.print(f"  特徴的な表現: {', '.join(profile.characteristic_expressions[:5])}")

    # ファイル出力
    output_path = output or str(
        Path(settings.output_dir) / f"style_profile_{author}.json"
    )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(profile.to_json(), encoding="utf-8")
    console.print(f"[green]プロファイルを保存: {output_path}[/green]")

    # DBに保存
    db = _get_db(settings)
    db.execute(
        "INSERT INTO style_profiles (name, profile, source_articles) VALUES (?, ?, ?)",
        (
            author,
            profile.to_json(),
            json.dumps([t[:200] for t in texts[:5]], ensure_ascii=False),
        ),
    )


# ---------------------------------------------------------------------------
# generate コマンド
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--topic", "-t", help="記事のトピック（指定しない場合は自動抽出）")
@click.option("--count", "-n", type=int, default=1, help="生成する記事数")
@click.option("--style-profile", "-s", type=click.Path(exists=True), help="スタイルプロファイルJSONファイル")
@click.option("--pattern-file", type=click.Path(exists=True), help="書き方パターンJSONファイル")
@click.option("--source-file", type=click.Path(exists=True), help="参考コンテンツファイル")
@click.pass_context
def generate(
    ctx: click.Context,
    topic: str | None,
    count: int,
    style_profile: str | None,
    pattern_file: str | None,
    source_file: str | None,
) -> None:
    """記事を生成する"""
    settings = _load_settings(ctx)

    console.print(
        Panel(f"[bold]記事生成: {count} 件[/bold]", style="blue")
    )

    # スタイルプロファイル読み込み
    profile = None
    if style_profile:
        profile_json = Path(style_profile).read_text(encoding="utf-8")
        profile = StyleProfile.from_json("loaded", profile_json)
        console.print(f"[dim]スタイルプロファイル読み込み: {style_profile}[/dim]")

    # 書き方パターン読み込み
    from src.scraper.models import WritingPattern

    writing_pattern = None
    if pattern_file:
        pattern_data = json.loads(Path(pattern_file).read_text(encoding="utf-8"))
        writing_pattern = WritingPattern(**pattern_data)
        console.print(f"[dim]書き方パターン読み込み: {pattern_file}[/dim]")

    # 参考コンテンツ
    source_content = ""
    if source_file:
        source_content = Path(source_file).read_text(encoding="utf-8")
    else:
        # DBから取得
        db = _get_db(settings)
        rows = db.fetch_all(
            "SELECT content FROM sources ORDER BY created_at DESC LIMIT 5"
        )
        source_content = "\n\n".join(row["content"][:1000] for row in rows)

    generator = ArticleGenerator(
        api_key=settings.anthropic_api_key,
        model=settings.model_name,
    )

    # トピック指定がない場合は自動抽出
    topics: list[str] = []
    if topic:
        topics = [topic] * count
    else:
        if source_content:
            console.print("[cyan]トピックを自動抽出中...[/cyan]")
            with console.status("[cyan]Claude APIでトピック抽出中...[/cyan]"):
                extracted = generator.extract_topics(source_content, count=count)
            topics = [t.get("topic", t.get("suggested_title", "")) for t in extracted]
        else:
            console.print("[red]トピックまたは参考コンテンツを指定してください。[/red]")
            ctx.exit(1)
            return

    # 記事生成
    writer = MarkdownWriter(settings.output_dir)
    articles: list[dict] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("記事生成中...", total=len(topics))

        for i, t in enumerate(topics):
            progress.update(task, description=f"生成中: {t[:30]}...")

            try:
                result = generator.generate_article(
                    topic=t,
                    source_content=source_content[:3000],
                    style_profile=profile,
                    writing_pattern=writing_pattern,
                    target_length=2000,
                )
                articles.append(result)

                # ファイル出力
                path = writer.write_article(
                    title=result["title"],
                    body=result["body"],
                    hashtags=result.get("hashtags"),
                )
                console.print(
                    f"  [green]#{i+1} {result['title'][:40]} "
                    f"({result['word_count']}文字) → {path.name}[/green]"
                )

                # DBに保存
                db = _get_db(settings)
                db.execute(
                    "INSERT INTO generated_articles (title, content, topic, word_count, status) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (result["title"], result["body"], t, result["word_count"], "draft"),
                )

            except Exception as e:
                console.print(f"  [red]#{i+1} エラー: {e}[/red]")

            progress.advance(task)
            if i < len(topics) - 1:
                time.sleep(1)

    console.print(f"\n[green]{len(articles)} 件の記事を生成しました[/green]")


# ---------------------------------------------------------------------------
# list コマンド
# ---------------------------------------------------------------------------


@cli.command("list")
@click.pass_context
def list_articles(ctx: click.Context) -> None:
    """生成済み記事の一覧を表示する"""
    settings = _load_settings(ctx)

    export_manager = ExportManager(settings.output_dir)
    summary = export_manager.get_summary()

    if summary["total_files"] == 0:
        console.print("[yellow]生成済み記事がありません。[/yellow]")
        return

    table = Table(title=f"生成済み記事 ({summary['total_files']} 件)")
    table.add_column("#", style="dim", width=3)
    table.add_column("ファイル名", style="cyan", max_width=50)
    table.add_column("文字数", justify="right", width=8)
    table.add_column("更新日時", width=20)

    for i, f in enumerate(summary["files"], 1):
        table.add_row(str(i), f["name"], f"{f['chars']:,}", f["modified"])

    console.print(table)
    console.print(
        f"\n合計文字数: {summary['total_chars']:,} / "
        f"平均: {summary['total_chars'] // max(summary['total_files'], 1):,}"
    )


# ---------------------------------------------------------------------------
# status コマンド
# ---------------------------------------------------------------------------


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """プロジェクトの状態を表示する"""
    settings = _load_settings(ctx)

    db = _get_db(settings)

    # 各テーブルの件数を取得
    sources_count = db.fetch_one("SELECT COUNT(*) as cnt FROM sources")
    profiles_count = db.fetch_one("SELECT COUNT(*) as cnt FROM style_profiles")
    articles_count = db.fetch_one("SELECT COUNT(*) as cnt FROM generated_articles")
    cache_count = db.fetch_one("SELECT COUNT(*) as cnt FROM scrape_cache")

    # 出力ファイル数
    export_manager = ExportManager(settings.output_dir)
    output_summary = export_manager.get_summary()

    table = Table(title="プロジェクトステータス")
    table.add_column("項目", style="cyan")
    table.add_column("値", justify="right")

    table.add_row("取り込みソース", f"{sources_count['cnt']} 件")
    table.add_row("スタイルプロファイル", f"{profiles_count['cnt']} 件")
    table.add_row("生成記事 (DB)", f"{articles_count['cnt']} 件")
    table.add_row("スクレイプキャッシュ", f"{cache_count['cnt']} 件")
    table.add_row("出力ファイル", f"{output_summary['total_files']} 件")
    table.add_row("総文字数", f"{output_summary['total_chars']:,}")
    table.add_row("モデル", settings.model_name)
    table.add_row("DBパス", settings.db_path)
    table.add_row("出力先", settings.output_dir)

    console.print(table)


if __name__ == "__main__":
    cli()
