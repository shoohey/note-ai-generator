"""
コンテンツチャンク分割モジュール

大量のテキストをLLMが処理しやすいサイズに分割する。
段落や文の区切りを尊重し、オーバーラップにより文脈を維持する。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ContentChunker:
    """大量テキストのチャンク分割。

    段落区切り（\\n\\n）を優先し、段落が大きすぎる場合は
    文区切り（。）でさらに分割する。オーバーラップにより
    前後のチャンク間で文脈の連続性を維持する。
    """

    def __init__(self, chunk_size: int = 3000, overlap: int = 200) -> None:
        """ContentChunker を初期化する。

        Args:
            chunk_size: 1チャンクあたりの最大文字数。
            overlap: チャンク間のオーバーラップ文字数。

        Raises:
            ValueError: overlap が chunk_size 以上の場合。
        """
        if overlap >= chunk_size:
            raise ValueError(
                f"overlap ({overlap}) は chunk_size ({chunk_size}) より小さくなければなりません"
            )
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[str]:
        """テキストを意味のある単位でチャンク分割する。

        分割の優先順位:
        1. 段落区切り（\\n\\n）で分割
        2. 段落が chunk_size を超える場合は文（。）で分割
        3. 文でも超える場合は文字数で強制分割

        オーバーラップにより前後のチャンクの文脈を維持する。

        Args:
            text: 分割対象のテキスト。

        Returns:
            チャンクのリスト。
        """
        if not text or not text.strip():
            return []

        text = text.strip()

        # chunk_size 以下ならそのまま返す
        if len(text) <= self.chunk_size:
            return [text]

        # まず段落で分割
        paragraphs = self._split_into_paragraphs(text)

        # 段落をチャンクにまとめる
        chunks = self._merge_segments_into_chunks(paragraphs)

        return chunks

    def chunk_with_metadata(self, text: str, title: str = "") -> list[dict]:
        """メタデータ付きチャンク分割を行う。

        各チャンクにインデックス、総数、タイトルのメタデータを付与する。

        Args:
            text: 分割対象のテキスト。
            title: チャンクに付与するタイトル。

        Returns:
            メタデータ付きチャンクのリスト。各要素は以下の形式:
            {"content": str, "index": int, "total": int, "title": str}
        """
        chunks = self.chunk(text)
        total = len(chunks)

        return [
            {
                "content": chunk_text,
                "index": i,
                "total": total,
                "title": title,
            }
            for i, chunk_text in enumerate(chunks)
        ]

    def _split_into_paragraphs(self, text: str) -> list[str]:
        """テキストを段落に分割する。

        段落区切り（\\n\\n）で分割し、各段落が chunk_size を超える場合は
        さらに文単位で分割する。

        Args:
            text: 分割対象のテキスト。

        Returns:
            セグメント（段落または文）のリスト。
        """
        raw_paragraphs = text.split("\n\n")
        segments: list[str] = []

        for paragraph in raw_paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            if len(paragraph) <= self.chunk_size:
                segments.append(paragraph)
            else:
                # 段落が大きすぎる場合は文で分割
                sentences = self._split_into_sentences(paragraph)
                segments.extend(sentences)

        return segments

    def _split_into_sentences(self, text: str) -> list[str]:
        """テキストを文単位で分割する。

        日本語の句点（。）、感嘆符（！）、疑問符（？）で分割する。
        それでも chunk_size を超える場合は文字数で強制分割する。

        Args:
            text: 分割対象のテキスト。

        Returns:
            文のリスト。
        """
        # 日本語の文区切りで分割
        sentences: list[str] = []
        current = ""

        for char in text:
            current += char
            if char in "。！？!?":
                sentences.append(current.strip())
                current = ""

        # 残りがあれば追加
        if current.strip():
            sentences.append(current.strip())

        # chunk_size を超える文は強制分割
        result: list[str] = []
        for sentence in sentences:
            if len(sentence) <= self.chunk_size:
                result.append(sentence)
            else:
                # 文字数で強制分割
                result.extend(self._force_split(sentence))

        return result

    def _force_split(self, text: str) -> list[str]:
        """テキストを文字数で強制的に分割する。

        改行位置を優先して分割ポイントを決定する。

        Args:
            text: 分割対象のテキスト。

        Returns:
            分割されたテキストのリスト。
        """
        chunks: list[str] = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            if end >= len(text):
                chunks.append(text[start:])
                break

            # 改行位置を探して、なるべくそこで区切る
            newline_pos = text.rfind("\n", start, end)
            if newline_pos > start:
                chunks.append(text[start:newline_pos].strip())
                start = newline_pos + 1
            else:
                chunks.append(text[start:end].strip())
                start = end

        return [c for c in chunks if c]

    def _merge_segments_into_chunks(self, segments: list[str]) -> list[str]:
        """セグメントをチャンクサイズ以内にまとめる。

        セグメントを順に結合し、chunk_size を超えたら新しいチャンクを開始する。
        オーバーラップにより前チャンクの末尾テキストを次チャンクの先頭に含める。

        Args:
            segments: 段落または文のリスト。

        Returns:
            まとめられたチャンクのリスト。
        """
        if not segments:
            return []

        chunks: list[str] = []
        current_chunk: list[str] = []
        current_length = 0

        for segment in segments:
            segment_length = len(segment)
            # 区切り文字（\n\n）の長さも考慮
            separator_length = 2 if current_chunk else 0
            new_length = current_length + separator_length + segment_length

            if new_length <= self.chunk_size:
                current_chunk.append(segment)
                current_length = new_length
            else:
                # 現在のチャンクを確定
                if current_chunk:
                    chunk_text = "\n\n".join(current_chunk)
                    chunks.append(chunk_text)

                    # オーバーラップ: 前チャンクの末尾からoverlap文字を取得
                    overlap_text = self._get_overlap_text(chunk_text)

                    # 新しいチャンクをオーバーラップ付きで開始
                    if overlap_text:
                        current_chunk = [overlap_text, segment]
                        current_length = len(overlap_text) + 2 + segment_length
                    else:
                        current_chunk = [segment]
                        current_length = segment_length
                else:
                    # 単一セグメントがchunk_sizeを超える場合
                    chunks.append(segment)
                    overlap_text = self._get_overlap_text(segment)
                    if overlap_text:
                        current_chunk = [overlap_text]
                        current_length = len(overlap_text)
                    else:
                        current_chunk = []
                        current_length = 0

        # 残りのチャンクを追加
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def _get_overlap_text(self, text: str) -> str:
        """チャンクの末尾からオーバーラップ用テキストを取得する。

        Args:
            text: 対象テキスト。

        Returns:
            オーバーラップテキスト。overlap が 0 の場合は空文字。
        """
        if self.overlap <= 0:
            return ""

        if len(text) <= self.overlap:
            return text

        return text[-self.overlap :]
