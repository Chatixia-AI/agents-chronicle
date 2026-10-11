"""MkDocs hooks: publish the repository's Markdown as the documentation site without changing it.

README.md and README.ja.md become the English and Japanese home pages, in place of docs/README.md and
docs/ja/README.md (indexes for browsing on GitHub; the site's navigation does their job). Every relative
link is resolved from the file's place in the repository, so links that leave docs/ (the READMEs,
CHANGELOG.md, LICENSE, source files) point at the home pages or at GitHub instead of breaking. MkDocs turns
Markdown links to .md files into page URLs but leaves raw HTML (the READMEs' quick links) alone, so those get
the target page's URL here. The "← Interlatch · Docs index" line atop each page is dropped: the site's
navigation does its job too.
"""

import posixpath
import re
from pathlib import Path

from mkdocs.structure.files import File
from mkdocs.utils import get_relative_url

ROOT = Path(__file__).resolve().parents[2]
GITHUB = "https://github.com/Chatixia-AI/interlatch"
ICON = "packaging/macos/icon.png"
HOMES = {"index.md": "README.md", "ja/index.md": "README.ja.md"}
SITE_PATHS = {"README.md": "index.md", "docs/README.md": "index.md",
              "README.ja.md": "ja/index.md", "docs/ja/README.md": "ja/index.md", ICON: "assets/icon.png"}
LINK = re.compile(r'(\]\(|(?:href|src)=")([^)"#\s]+)')  # Markdown link targets and HTML href/src values


def on_files(files, config):
    for index in ("README.md", "ja/README.md"):
        files.remove(files.get_file_from_path(index))
    for uri, readme in HOMES.items():
        files.append(File.generated(config, uri, content=(ROOT / readme).read_text(encoding="utf-8")))
    files.append(File.generated(config, "assets/icon.png", abs_src_path=str(ROOT / ICON)))
    return files


def on_page_markdown(markdown, page, config, files):
    uri = page.file.src_uri
    source = HOMES.get(uri, "docs/" + uri)  # where this page lives in the repository
    here = posixpath.dirname(uri) or "."

    def rewrite(m):
        target = m.group(2)
        if re.match(r"[a-z][a-z0-9+.-]*:", target) or target.startswith("/"):
            return m.group(0)
        path = posixpath.normpath(posixpath.join(posixpath.dirname(source), target))
        site = SITE_PATHS.get(path) or (path[5:] if path.startswith("docs/") else None)
        if site is None:
            kind = "raw" if path.endswith((".png", ".svg", ".jpg", ".gif")) else "blob"
            return f"{m.group(1)}{GITHUB}/{kind}/main/{path}"
        built = files.get_file_from_path(site)
        if m.group(1) != "](" and built is not None:  # raw HTML: MkDocs leaves its hrefs alone, so link the URL
            return m.group(1) + get_relative_url(built.url, page.url)
        return m.group(1) + posixpath.relpath(site, here)

    markdown = re.sub(r"^\[← .*\n+", "", markdown, count=1, flags=re.M)
    return LINK.sub(rewrite, markdown)
