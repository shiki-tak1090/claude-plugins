# /// script
# requires-python = ">=3.10"
# dependencies = ["pypandoc-binary==1.17"]  # pandoc 3.9 を同梱
# [tool.uv]
# exclude-newer = "2026-10-28T00:00:00Z"
# ///
"""設計書 Markdown を Word（docx）に変換する。

pandoc で変換し、書式は参照用 docx（reference.docx）から取る。
Mermaid の図は mmdc で PNG にしてから埋め込む。内容には手を加えない。

誰が変換しても同じ出力になるよう、pandoc は pypandoc-binary に同梱された版だけを使い、
PATH 上の pandoc は使わない。版を上げるときは dependencies を変え、全員で同時に切り替える。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mdmodel import (  # noqa: E402
    EMBED, MERMAID_FENCE, WIKILINK, expand_sources, is_image, output_path, render_mermaid,
    resolve_embed, wikilink_text,
)

HERE = Path(__file__).parent


def obsidian_to_gfm(text: str, src_dir: Path) -> str:
    """Obsidian の画像埋め込みを通常の画像に、[[リンク]] を表示名の文字列に置き換える。"""
    def embed(m):
        name = m.group(1)
        if not is_image(name):
            return name
        path = resolve_embed(name, src_dir)
        return f"![]({path.resolve().as_posix()})" if path else f"[画像が見つかりません: {name}]"

    return WIKILINK.sub(wikilink_text, EMBED.sub(embed, text))


def find_pandoc() -> str:
    try:
        import pypandoc
        return pypandoc.get_pandoc_path()
    except Exception:
        sys.exit("同梱の pandoc が見つかりません。`uv run md_to_docx.py ...` の形で実行してください。")


def convert(pandoc: str, src: Path, out: Path, reference: Path | None) -> None:
    text = obsidian_to_gfm(src.read_text(encoding="utf-8"), src.parent)
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        count = 0

        def replace(m):
            nonlocal count
            count += 1
            png = tmpdir / f"diagram{count}.png"
            render_mermaid(m.group(1), png)
            return f"![]({png.as_posix()})"

        text = MERMAID_FENCE.sub(replace, text)
        tmp_md = tmpdir / "input.md"
        tmp_md.write_text(text, encoding="utf-8")
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [pandoc, str(tmp_md), "-f", "gfm", "-t", "docx", "-o", str(out),
               "--lua-filter", str(HERE / "br.lua"),
               f"--resource-path={src.parent}{os.pathsep}{tmpdir}"]
        if reference:
            cmd += ["--reference-doc", str(reference)]
        subprocess.run(cmd, check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src", nargs="+", help="変換する Markdown ファイルまたはフォルダ")
    ap.add_argument("--src-root", default=".", help="出力先の相対パスを決める基準")
    ap.add_argument("--out-root", default="exports/docx")
    ap.add_argument("--reference-doc", default="99_テンプレート/export/reference.docx")
    args = ap.parse_args()

    pandoc = find_pandoc()
    reference = Path(args.reference_doc)
    if not reference.exists():
        print(f"[注意] {reference} がないため、pandoc 既定の書式で出力します。", file=sys.stderr)
        reference = None
    for src in expand_sources(args.src):
        out = output_path(src, Path(args.src_root), Path(args.out_root), ".docx")
        convert(pandoc, src, out, reference)
        print(f"{src} -> {out}")


if __name__ == "__main__":
    main()
