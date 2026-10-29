"""設計書 Markdown（design-export の references/markdown-rules.md の範囲）をブロック列に分解する共通モジュール。

変換スクリプトと照合スクリプトが同じ解釈で Markdown を読むために使う。
"""
from __future__ import annotations

import html
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Block:
    kind: str  # heading / paragraph / list_item / table / code / mermaid / image
    text: str = ""
    level: int = 0
    rows: list[list[str]] = field(default_factory=list)
    lang: str = ""


FENCE = re.compile(r"^\s*(```|~~~)\s*([\w-]*)\s*$")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LIST_ITEM = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+(.*)$")
TABLE_SEP = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
HR = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")
MERMAID_FENCE = re.compile(r"^```mermaid[ \t]*\r?\n(.*?)^```[ \t]*\r?$", re.M | re.S)
TASK = re.compile(r"^\[([ xX])\]\s+")
# Obsidian の埋め込み ![[file|size]] とリンク [[target|alias]]（表の中では | を \| と書く）
EMBED = re.compile(r"!\[\[([^\]|\\]+)(?:\\?\|[^\]]*)?\]\]")
WIKILINK = re.compile(r"(?<!!)\[\[([^\]|\\]+)(?:\\?\|([^\]]+))?\]\]")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".jfif", ".gif", ".svg", ".webp", ".bmp"}

# FR-FAV-01、ADM-NEWS-01、UC-RP-03、U-1.1 のような ID。
# 日本語に隣接する ID も拾えるよう、\b ではなく英数字の前後否定で区切る
DEFAULT_ID_PATTERN = r"(?<![A-Za-z0-9-])[A-Z][A-Z0-9]*(?:-[A-Z][A-Z0-9]*)*-\d+(?:\.\d+)*(?![0-9])"


def is_image(name: str) -> bool:
    return Path(name).suffix.lower() in IMAGE_EXT


def resolve_embed(name: str, src_dir: Path, root: Path = Path(".")) -> Path | None:
    """Obsidian と同じく、相対パス → リポジトリ直下 → リポジトリ内のファイル名の順に探す。"""
    for cand in (src_dir / name, root / name):
        if cand.exists():
            return cand
    hits = [p for p in root.rglob(Path(name).name) if ".git" not in p.parts]
    return hits[0] if hits else None


def wikilink_text(m: re.Match) -> str:
    return (m.group(2) or m.group(1)).strip()


def split_row(line: str) -> list[str]:
    # [[リンク|表示名]] の | はセルの区切りとみなさない（Obsidian と同じ扱い）
    s = re.sub(r"\[\[[^\]]*\]\]", lambda m: m.group(0).replace("\\|", "|").replace("|", "\\|"), line.strip())
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def parse(md: str) -> list[Block]:
    lines = md.splitlines()
    blocks: list[Block] = []
    para: list[str] = []

    def flush() -> None:
        if para:
            blocks.append(Block("paragraph", " ".join(s.strip() for s in para)))
            para.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        if m := FENCE.match(line):
            flush()
            fence, lang = m.group(1), m.group(2)
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence):
                body.append(lines[i])
                i += 1
            i += 1
            blocks.append(Block("mermaid" if lang == "mermaid" else "code", "\n".join(body), lang=lang))
            continue
        if not line.strip():
            flush()
            i += 1
            continue
        if m := HEADING.match(line):
            flush()
            blocks.append(Block("heading", m.group(2), level=len(m.group(1))))
            i += 1
            continue
        if HR.match(line) and not para:
            i += 1
            continue
        if line.lstrip().startswith("|") and i + 1 < len(lines) and TABLE_SEP.match(lines[i + 1]):
            flush()
            rows = [split_row(line)]
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            blocks.append(Block("table", rows=rows))
            continue
        if m := IMAGE.match(line.strip()):
            flush()
            blocks.append(Block("image", m.group(1), lang=m.group(2)))
            i += 1
            continue
        if (m := EMBED.fullmatch(line.strip())) and is_image(m.group(1)):
            flush()
            blocks.append(Block("image", "", lang=m.group(1)))
            i += 1
            continue
        if m := LIST_ITEM.match(line):
            flush()
            text, task = m.group(2), ""
            if (e := EMBED.fullmatch(text.strip())) and is_image(e.group(1)):
                blocks.append(Block("image", "", lang=e.group(1)))  # 箇条書きの中の画像も図として扱う
                i += 1
                continue
            if t := TASK.match(text):
                text, task = text[t.end():], ("done" if t.group(1) in "xX" else "todo")
            blocks.append(Block("list_item", text, level=len(m.group(1).expandtabs(4)) // 2, lang=task))
            i += 1
            continue
        para.append(line.lstrip().lstrip(">").strip() if line.lstrip().startswith(">") else line)
        i += 1
    flush()
    return blocks


def plain(text: str) -> str:
    """インラインの Markdown 記法を外し、変換後に表示される文字列に近づける。"""
    t = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    t = EMBED.sub(lambda m: "" if is_image(m.group(1)) else m.group(1), t)
    t = WIKILINK.sub(wikilink_text, t)
    t = re.sub(r"!\[([^\]]*)\]\([^)]*\)", "", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|<>])", r"\1", t)
    return html.unescape(t)


def norm(text: str) -> str:
    """照合用に空白（全角スペースを含む）をすべて取り除く。"""
    return re.sub(r"\s+", "", text)


def find_mmdc() -> str | None:
    return shutil.which("mmdc") or shutil.which("mmdc.cmd")


def render_mermaid(code: str, out_png: Path) -> None:
    mmdc = find_mmdc()
    if not mmdc:
        raise RuntimeError(
            "Mermaid の図がありますが mmdc が見つかりません。"
            "`npm install -g @mermaid-js/mermaid-cli` でインストールしてください。"
        )
    src = out_png.with_suffix(".mmd")
    src.write_text(code, encoding="utf-8")
    subprocess.run([mmdc, "-i", str(src), "-o", str(out_png), "-b", "white", "-s", "2"],
                   check=True, capture_output=True)


SKIP_DIRS = {".git", ".obsidian", ".claude", "exports", "99_テンプレート"}


def expand_sources(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            files.extend(f for f in sorted(p.rglob("*.md")) if not SKIP_DIRS & set(f.parts))
        else:
            files.append(p)
    return files


def output_path(src: Path, src_root: Path, out_root: Path, suffix: str) -> Path:
    try:
        rel = src.resolve().relative_to(src_root.resolve())
    except ValueError:
        rel = Path(src.name)
    return (out_root / rel).with_suffix(suffix)
