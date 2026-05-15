#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class LinkRef:
  src_file: Path
  attr: str
  raw: str


class LinkParser(HTMLParser):
  def __init__(self, src_file: Path) -> None:
    super().__init__(convert_charrefs=True)
    self.src_file = src_file
    self.title_seen = False
    self._in_title = False
    self.links: list[LinkRef] = []

  def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
    if tag == "title":
      self._in_title = True
      return
    for key, value in attrs:
      if value is None:
        continue
      if key in ("href", "src"):
        self.links.append(LinkRef(src_file=self.src_file, attr=key, raw=value.strip()))

  def handle_endtag(self, tag: str) -> None:
    if tag == "title":
      self._in_title = False

  def handle_data(self, data: str) -> None:
    if self._in_title and data.strip():
      self.title_seen = True


def iter_html_files(site_root: Path) -> Iterable[Path]:
  for path in site_root.rglob("*.html"):
    if path.is_file():
      yield path


def is_external(url: str) -> bool:
  lower = url.lower()
  return lower.startswith(("http://", "https://", "mailto:", "tel:"))


def strip_fragment(url: str) -> str:
  return url.split("#", 1)[0]


def strip_query(url: str) -> str:
  return url.split("?", 1)[0]


def resolve_internal(site_root: Path, src_file: Path, raw: str) -> Path | None:
  raw = strip_query(strip_fragment(raw))
  if not raw or raw == "/":
    return None
  if is_external(raw):
    return None
  if raw.startswith("//"):
    return None

  if raw.startswith("/"):
    candidate = site_root / raw.lstrip("/")
  else:
    candidate = (src_file.parent / raw).resolve()

  try:
    candidate.relative_to(site_root.resolve())
  except Exception:
    return None

  return candidate


def main() -> int:
  site_root = Path(__file__).resolve().parents[1]
  if not (site_root / "index.html").exists():
    print(f"ERR: expected site root at {site_root}, missing index.html", file=sys.stderr)
    return 2

  broken: list[str] = []
  missing_title: list[str] = []

  for html_file in sorted(iter_html_files(site_root)):
    parser = LinkParser(html_file)
    try:
      parser.feed(html_file.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
      parser.feed(html_file.read_text(encoding="utf-8", errors="replace"))

    if not parser.title_seen:
      missing_title.append(str(html_file.relative_to(site_root)))

    for ref in parser.links:
      target = resolve_internal(site_root, ref.src_file, ref.raw)
      if target is None:
        continue
      if not target.exists():
        broken.append(
          f"{ref.src_file.relative_to(site_root)}: missing {ref.attr} -> {ref.raw}"
        )

  if missing_title:
    print("ERR: HTML missing <title>:", file=sys.stderr)
    for item in missing_title:
      print(f"  - {item}", file=sys.stderr)

  if broken:
    print("ERR: broken internal links/assets:", file=sys.stderr)
    for item in broken:
      print(f"  - {item}", file=sys.stderr)

  if missing_title or broken:
    return 1

  print(f"OK: checked {sum(1 for _ in iter_html_files(site_root))} HTML files; no broken internal links.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())

