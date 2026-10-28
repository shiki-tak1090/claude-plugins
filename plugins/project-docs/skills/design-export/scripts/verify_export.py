# /// script
# requires-python = ">=3.10"
# dependencies = ["python-docx==1.2.0", "openpyxl==3.1.5", "pillow==13.0.0"]  # pillow がないと openpyxl は画像を読み飛ばす
# [tool.uv]
# exclude-newer = "2026-10-28T00:00:00Z"
# ///
"""変換後の docx / xlsx から文字を抜き出し、正本の Markdown と突き合わせる。

確認すること:
  1. 本文の欠落と順序: Markdown の見出し・段落・箇条書き・表のセル・コードの各行が、
     変換後のファイルに同じ順序で現れるか（空白の違いは無視する）
  2. ID の出現回数: 要件 ID などが Markdown と同じ回数だけ現れるか
  3. 構造（docx のみ）: 見出しの並び、表の数と各表の行数・列数、図の数が一致するか

エラーが 1 件でもあれば終了コード 1 を返す。
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mdmodel import DEFAULT_ID_PATTERN, Block, norm, parse, plain  # noqa: E402


def source_tokens(blocks: list[Block], normalize: bool = True) -> list[str]:
    tokens: list[str] = []
    for b in blocks:
        if b.kind in ("heading", "paragraph", "list_item"):
            tokens.append(plain(b.text))
        elif b.kind == "table":
            tokens += [plain(c) for row in b.rows for c in row]
        elif b.kind == "code":
            tokens += b.text.splitlines()
    return [t for t in (norm(x) if normalize else x for x in tokens) if t.strip()]


def docx_content(path: Path) -> dict:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(str(path))
    pieces, headings, tables = [], [], []
    for el in doc.element.body.iterchildren():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(el, doc)
            pieces.append(p.text)
            name = (p.style.name if p.style is not None else "").lower()
            if name.startswith("heading") or name.startswith("見出し") or name == "title":
                headings.append(p.text)
        elif tag == "tbl":
            t = Table(el, doc)
            tables.append((len(t.rows), len(t.columns)))
            pieces += [cell.text for row in t.rows for cell in row.cells]
    return {"pieces": pieces, "headings": headings, "tables": tables, "images": len(doc.inline_shapes)}


def xlsx_content(path: Path) -> dict:
    from openpyxl import load_workbook

    wb = load_workbook(str(path))
    pieces, images = [], 0
    for ws in wb.worksheets:
        images += len(getattr(ws, "_images", []))
        for row in ws.iter_rows(values_only=True):
            pieces += [str(v) for v in row if v is not None]
    return {"pieces": pieces, "images": images}


def verify(src: Path, out: Path, id_pattern: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    blocks = parse(src.read_text(encoding="utf-8"))
    content = docx_content(out) if out.suffix == ".docx" else xlsx_content(out)
    # 太字にならずに残った ** は照合では無視し、見た目の問題として警告する
    pieces = [norm(p).replace("**", "") for p in content["pieces"]]
    if leftovers := [p.strip()[:40] for p in content["pieces"] if "**" in p]:
        warnings.append(f"強調記号 ** がそのまま出力されています（{len(leftovers)} 箇所。例: {leftovers[0]}）。"
                        "閉じの ** の直前が括弧・句読点だと太字になりません")

    # 1. 本文の欠落と順序（同じ段落・セルに複数のトークンが入る場合があるため、同じ位置からの再検索を許す）
    pos = 0
    for token in source_tokens(blocks):
        hit = next((k for k in range(pos, len(pieces)) if token in pieces[k]), None)
        if hit is not None:
            pos = hit
        elif any(token in p for p in pieces):
            errors.append(f"順序違い: {token[:60]}")
        else:
            errors.append(f"欠落: {token[:60]}")

    # 2. ID の出現回数（Mermaid の中の ID は画像になるため数えない）
    id_re = re.compile(id_pattern)
    src_ids = Counter(id_re.findall("\n".join(source_tokens(blocks, normalize=False))))
    out_ids = Counter(id_re.findall("\n".join(content["pieces"])))
    for id_, n in sorted((src_ids | out_ids).items()):
        s, o = src_ids.get(id_, 0), out_ids.get(id_, 0)
        if o < s:
            errors.append(f"ID の不足: {id_}（Markdown {s} 回 / 出力 {o} 回）")
        elif o > s:
            warnings.append(f"ID の増加: {id_}（Markdown {s} 回 / 出力 {o} 回）。テンプレートの表紙などに含まれていないか確認")
    mermaid_ids = {i for b in blocks if b.kind == "mermaid" for i in id_re.findall(b.text)}
    if only_in_diagram := sorted(mermaid_ids - set(src_ids)):
        warnings.append(f"図にしか書かれていない ID: {', '.join(only_in_diagram)}（本文か表にも書くこと）")

    # 3. 構造
    n_figures = sum(1 for b in blocks if b.kind in ("mermaid", "image"))
    if content["images"] != n_figures:
        errors.append(f"図の数が不一致: Markdown {n_figures} / 出力 {content['images']}")
    if out.suffix == ".docx":
        src_heads = [norm(plain(b.text)) for b in blocks if b.kind == "heading"]
        out_heads = [norm(h) for h in content["headings"]]
        if src_heads != out_heads:
            missing = [h for h in src_heads if h not in out_heads]
            extra = [h for h in out_heads if h not in src_heads]
            errors.append(f"見出しの並びが不一致（不足 {missing[:5]} / 余分 {extra[:5]}）")
        src_tables = [(len(b.rows), max(len(r) for r in b.rows)) for b in blocks if b.kind == "table"]
        if src_tables != content["tables"]:
            errors.append(f"表の数または行数・列数が不一致: Markdown {src_tables} / 出力 {content['tables']}")
    return errors, warnings


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="正本の Markdown")
    ap.add_argument("out", help="変換後の docx または xlsx")
    ap.add_argument("--id-pattern", default=DEFAULT_ID_PATTERN, help="ID とみなす正規表現")
    args = ap.parse_args()

    errors, warnings = verify(Path(args.src), Path(args.out), args.id_pattern)
    status = "NG" if errors else "OK"
    print(f"## {status}: {args.src} -> {args.out}")
    for e in errors:
        print(f"- [エラー] {e}")
    for w in warnings:
        print(f"- [警告] {w}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
