#!/usr/bin/env python3
"""Prepare a GitHub wiki working tree from markdown documentation."""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

WIKI_TITLE_RE = re.compile(
    r"<!--\s*wiki-(?:title|name)\s*:?\s*(.*?)\s*-->",
    re.IGNORECASE,
)
WIKI_CATEGORY_RE = re.compile(
    r"<!--\s*wiki-category\s*:?\s*(.*?)\s*-->",
    re.IGNORECASE,
)
H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
MARKDOWN_LINK_IN_TEXT_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
DEFAULT_CATEGORY = "Other"
DEFAULT_CATEGORY_ORDER = (
    "Installation",
    "High Availability",
    "CA Handlers",
    "Features",
    "Configuration",
    "Operations",
    "Development",
    "Architecture",
    "Other",
)
ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
GENERATED_NAMES = {"Home.md", "_Sidebar.md", "_Footer.md"}


@dataclass
class WikiPage:
    source: Path
    title: str
    slug: str
    category: str
    content: str
    relative_source: str


@dataclass
class PublishConfig:
    sources: list[Path]
    dest: Path
    workspace: Path
    recursive: bool = False
    exclude: list[str] = field(default_factory=list)
    generate_home: bool = False
    generate_sidebar: bool = False
    inject_nav: bool = True
    home_title: str = ""
    home_intro: str = ""
    sidebar_title: str = "Navigation"
    category_order: list[str] = field(default_factory=lambda: list(DEFAULT_CATEGORY_ORDER))
    sync: bool = False
    copy_assets: bool = True


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def split_multi(value: str | None) -> list[str]:
    if not value:
        return []
    items: list[str] = []
    for raw_line in value.replace(",", "\n").splitlines():
        item = raw_line.strip()
        if item:
            items.append(item)
    return items


def env_or_default(name: str, default: str = "") -> str:
    """Read an action input from the environment.

    Composite/JS actions expose ``INPUT_GENERATE_HOME``.
    Docker actions keep hyphens in the input name: ``INPUT_GENERATE-HOME``.
    """
    if name.startswith("INPUT_"):
        hyphenated = "INPUT_" + name[len("INPUT_") :].replace("_", "-")
    else:
        hyphenated = name.replace("_", "-")
    empty: str | None = None
    for candidate in (name, hyphenated):
        if candidate not in os.environ:
            continue
        value = os.environ[candidate]
        if value != "":
            return value
        if empty is None:
            empty = value
    if empty is not None:
        return empty
    return default


def slugify(title: str) -> str:
    """Turn a wiki title into a GitHub wiki page filename stem."""
    text = title.strip().lstrip("#").strip()
    text = text.replace("`", "")
    text = MARKDOWN_LINK_IN_TEXT_RE.sub(r"\1", text)
    text = text.replace("/", "-")
    text = re.sub(r"[^\w\s._+-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text.strip())
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-._") or "untitled"


def first_h1(content: str) -> str | None:
    match = H1_RE.search(content)
    if not match:
        return None
    heading = MARKDOWN_LINK_IN_TEXT_RE.sub(r"\1", match.group(1).strip())
    return heading.strip() or None


def extract_meta(content: str, fallback_title: str) -> tuple[str, str]:
    title_match = WIKI_TITLE_RE.search(content)
    category_match = WIKI_CATEGORY_RE.search(content)
    title = title_match.group(1).strip() if title_match else ""
    title = title.lstrip("#").strip()
    if not title:
        title = first_h1(content) or fallback_title
    category = category_match.group(1).strip() if category_match else DEFAULT_CATEGORY
    return title, category or DEFAULT_CATEGORY


def is_excluded(relative_path: str, patterns: Sequence[str]) -> bool:
    posix = relative_path.replace(os.sep, "/")
    name = Path(posix).name
    for pattern in patterns:
        normalized = pattern.replace(os.sep, "/").lstrip("./")
        if fnmatch.fnmatch(posix, normalized) or fnmatch.fnmatch(name, normalized):
            return True
        if normalized.endswith("/**") and posix.startswith(normalized[:-3]):
            return True
    return False


def iter_markdown_files(source: Path, recursive: bool) -> Iterable[Path]:
    if recursive:
        yield from sorted(path for path in source.rglob("*.md") if path.is_file())
        return
    yield from sorted(path for path in source.glob("*.md") if path.is_file())


def iter_asset_files(source: Path, recursive: bool) -> Iterable[Path]:
    iterator = source.rglob("*") if recursive else source.glob("*")
    for path in sorted(iterator):
        if path.is_file() and path.suffix.lower() in ASSET_SUFFIXES:
            yield path


def collect_pages(config: PublishConfig) -> list[WikiPage]:
    pages: list[WikiPage] = []
    seen_slugs: dict[str, Path] = {}
    for source in config.sources:
        if not source.exists():
            raise FileNotFoundError(f"Source path does not exist: {source}")
        if not source.is_dir():
            raise NotADirectoryError(f"Source path is not a directory: {source}")
        for path in iter_markdown_files(source, config.recursive):
            relative = str(path.relative_to(source)).replace(os.sep, "/")
            if is_excluded(relative, config.exclude):
                continue
            content = path.read_text(encoding="utf-8")
            title, category = extract_meta(content, path.stem.replace("_", " ").replace("-", " "))
            slug = slugify(title)
            if slug.lower() + ".md" in {name.lower() for name in GENERATED_NAMES}:
                raise ValueError(f"Refusing to publish {path} as reserved wiki page {slug}.md")
            duplicate = next((existing for existing in seen_slugs if existing.lower() == slug.lower()), None)
            if duplicate is not None:
                raise ValueError(
                    f"Duplicate wiki slug '{slug}' from {seen_slugs[duplicate]} and {path}"
                )
            seen_slugs[slug] = path
            pages.append(
                WikiPage(
                    source=path,
                    title=title,
                    slug=slug,
                    category=category,
                    content=content,
                    relative_source=relative,
                )
            )
    return pages


def build_link_map(pages: Sequence[WikiPage]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for page in pages:
        resolved = str(page.source.resolve())
        mapping[resolved] = page.slug
        mapping[page.source.name] = page.slug
        mapping[page.source.stem] = page.slug
        mapping[page.relative_source] = page.slug
        mapping[Path(page.relative_source).name] = page.slug
    return mapping


def rewrite_markdown_links(content: str, source: Path, link_map: Mapping[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        text, target = match.group(1), match.group(2).strip()
        if not target or target.startswith(("#", "mailto:", "http://", "https://", "<")):
            return match.group(0)
        path_part, anchor = _split_anchor(target)
        if not path_part.lower().endswith(".md") and "/" not in path_part and "\\" not in path_part:
            # Leave wiki-style or in-page references alone unless we know the source file.
            lookup = link_map.get(path_part) or link_map.get(Path(path_part).name)
            if lookup:
                return f"[{text}]({lookup}{anchor})"
            return match.group(0)
        candidate = (source.parent / path_part).resolve()
        slug = link_map.get(str(candidate))
        if slug is None:
            slug = link_map.get(Path(path_part).name)
        if slug is None:
            return match.group(0)
        return f"[{text}]({slug}{anchor})"

    return MD_LINK_RE.sub(replace, content)


def _split_anchor(target: str) -> tuple[str, str]:
    if target.startswith("#"):
        return "", target
    if "#" not in target:
        return target, ""
    path_part, anchor = target.split("#", 1)
    return path_part, f"#{anchor}"


def sort_pages(pages: Sequence[WikiPage], category_order: Sequence[str]) -> list[WikiPage]:
    order = {name.lower(): index for index, name in enumerate(category_order)}
    fallback = len(order)

    def key(page: WikiPage) -> tuple[int, str, str]:
        return (
            order.get(page.category.lower(), fallback),
            page.category.lower(),
            page.title.lower(),
        )

    return sorted(pages, key=key)


def grouped_pages(
    pages: Sequence[WikiPage], category_order: Sequence[str]
) -> list[tuple[str, list[WikiPage]]]:
    grouped: dict[str, list[WikiPage]] = {}
    for page in sort_pages(pages, category_order):
        grouped.setdefault(page.category, []).append(page)
    labels = list(dict.fromkeys(page.category for page in sort_pages(pages, category_order)))
    return [(label, grouped[label]) for label in labels]


def render_index(
    pages: Sequence[WikiPage],
    category_order: Sequence[str],
    title: str,
    intro: str,
    heading: str = "#",
) -> str:
    lines = [f"{heading} {title}".rstrip(), ""]
    if intro.strip():
        lines.extend([intro.strip(), ""])
    groups = grouped_pages(pages, category_order)
    if not groups:
        lines.append("No documentation pages were published.")
        lines.append("")
        return "\n".join(lines)
    for category, group in groups:
        lines.append(f"## {category}")
        lines.append("")
        for page in group:
            lines.append(f"- [{page.title}]({page.slug})")
        lines.append("")
    return "\n".join(lines)


def render_in_page_nav(
    pages: Sequence[WikiPage],
    category_order: Sequence[str],
    sidebar_title: str = "Navigation",
) -> str:
    """Grouped nav baked into each wiki page as markdown.

    GitHub's current wiki UI does not show `_Sidebar.md` as a side column,
    and it often strips HTML tables, so this uses markdown lists.
    """
    lines = [f"**{sidebar_title.strip() or 'Navigation'}**", "", "- [Home](Home)"]
    for category, group in grouped_pages(pages, category_order):
        lines.append(f"- **{category}**")
        for page in group:
            lines.append(f"  - [{page.title}]({page.slug})")
    lines.extend(["", "---", ""])
    return "\n".join(lines)


def insert_nav(content: str, nav: str) -> str:
    if not nav:
        return content
    match = H1_RE.search(content)
    if not match:
        return nav + "\n" + content
    heading_end = match.end()
    if heading_end < len(content) and content[heading_end] == "\n":
        heading_end += 1
    return content[:heading_end] + "\n" + nav + content[heading_end:]


def render_sidebar(
    pages: Sequence[WikiPage],
    category_order: Sequence[str],
    sidebar_title: str = "Navigation",
) -> str:
    """GitHub Wiki renders `_Sidebar.md` as the right-hand page navigation."""
    lines: list[str] = []
    if sidebar_title.strip():
        lines.extend([f"# {sidebar_title.strip()}", ""])
    lines.append("- [Home](Home)")
    for category, group in grouped_pages(pages, category_order):
        lines.append(f"- **{category}**")
        for page in group:
            lines.append(f"  - [{page.title}]({page.slug})")
    lines.append("")
    return "\n".join(lines)


def copy_assets(config: PublishConfig) -> list[Path]:
    copied: list[Path] = []
    if not config.copy_assets:
        return copied
    for source in config.sources:
        for path in iter_asset_files(source, config.recursive):
            relative = str(path.relative_to(source)).replace(os.sep, "/")
            if is_excluded(relative, config.exclude):
                continue
            destination = config.dest / path.name
            shutil.copy2(path, destination)
            copied.append(destination)
    return copied


def publish(config: PublishConfig) -> list[WikiPage]:
    config.dest.mkdir(parents=True, exist_ok=True)
    pages = collect_pages(config)
    link_map = build_link_map(pages)
    written: set[str] = set()

    nav = (
        render_in_page_nav(pages, config.category_order, config.sidebar_title)
        if config.inject_nav
        else ""
    )
    for page in pages:
        rewritten = rewrite_markdown_links(page.content, page.source, link_map)
        if nav:
            rewritten = insert_nav(rewritten, nav)
        destination = config.dest / f"{page.slug}.md"
        destination.write_text(rewritten, encoding="utf-8")
        written.add(destination.name)

    home_title = config.home_title or config.workspace.name or "Wiki"
    if config.generate_home:
        home = render_index(pages, config.category_order, home_title, config.home_intro)
        (config.dest / "Home.md").write_text(home, encoding="utf-8")
        written.add("Home.md")
    if config.generate_sidebar:
        sidebar = render_sidebar(pages, config.category_order, config.sidebar_title)
        (config.dest / "_Sidebar.md").write_text(sidebar, encoding="utf-8")
        written.add("_Sidebar.md")

    copy_assets(config)

    if config.sync:
        for existing in config.dest.glob("*.md"):
            if existing.name not in written:
                existing.unlink()
    return pages


def config_from_env(dest: Path, workspace: Path, sources: Sequence[str] | None = None) -> PublishConfig:
    raw_sources = sources if sources else split_multi(env_or_default("INPUT_PATH"))
    if not raw_sources:
        raise ValueError("No source path provided (input 'path' is required)")
    resolved_sources = [(workspace / source).resolve() if not Path(source).is_absolute() else Path(source) for source in raw_sources]
    category_order = split_multi(env_or_default("INPUT_CATEGORY_ORDER")) or list(DEFAULT_CATEGORY_ORDER)
    home_title = env_or_default("INPUT_HOME_TITLE").strip()
    if not home_title:
        repository = env_or_default("GITHUB_REPOSITORY")
        home_title = repository.split("/")[-1] if repository else workspace.name
    return PublishConfig(
        sources=resolved_sources,
        dest=dest,
        workspace=workspace,
        recursive=parse_bool(env_or_default("INPUT_RECURSIVE"), False),
        exclude=split_multi(env_or_default("INPUT_EXCLUDE")),
        generate_home=parse_bool(env_or_default("INPUT_GENERATE_HOME"), False),
        generate_sidebar=parse_bool(env_or_default("INPUT_GENERATE_SIDEBAR"), False),
        inject_nav=parse_bool(env_or_default("INPUT_INJECT_NAV"), True),
        home_title=home_title,
        home_intro=env_or_default("INPUT_HOME_INTRO"),
        sidebar_title=env_or_default("INPUT_SIDEBAR_TITLE", "Navigation"),
        category_order=category_order,
        sync=parse_bool(env_or_default("INPUT_SYNC"), False),
        copy_assets=parse_bool(env_or_default("INPUT_COPY_ASSETS"), True),
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="*", help="Source directories (defaults to INPUT_PATH)")
    parser.add_argument("--dest", required=True, help="Wiki working tree directory")
    parser.add_argument("--workspace", default=os.environ.get("GITHUB_WORKSPACE", os.getcwd()))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    workspace = Path(args.workspace).resolve()
    dest = Path(args.dest).resolve()
    try:
        config = config_from_env(dest=dest, workspace=workspace, sources=list(args.path) or None)
        pages = publish(config)
    except Exception as exc:  # noqa: BLE001 - surface a concise action error
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    print(
        "Wiki publish config: "
        f"generate_home={config.generate_home} "
        f"generate_sidebar={config.generate_sidebar} "
        f"inject_nav={config.inject_nav} "
        f"sync={config.sync} "
        f"sources={[str(path) for path in config.sources]}"
    )
    for page in sort_pages(pages, config.category_order):
        print(f"  [{page.category}] {page.title} -> {page.slug}.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
