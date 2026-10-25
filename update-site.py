#!/usr/bin/env python3
"""Regenerate the rose-os.org landing page.

Fills the "Recently merged" list in src/index.html with the last few
pull requests merged into blancolioni/rose, then writes the page and
its image to OUTDIR.  src/index.html is a page fragment (title, styles
and <main>), so the same file can be previewed as a Claude artifact;
this script adds the document wrapper.

Usage: update-site.py [--fragment] [OUTDIR]

OUTDIR defaults to /var/www/rose-os.org/html.  With --fragment, the
filled-in fragment is written instead of a full page, for previews.
Needs an authenticated gh.
"""

import argparse
import datetime
import filecmp
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = "blancolioni/rose"
COUNT = 5
# The default branch was renamed from master to main; merged pull
# requests keep the base they had.
BASES = ("main", "master")
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")


def merged_prs():
    result = subprocess.run(
        ["gh", "api",
         f"repos/{REPO}/pulls?state=closed&sort=updated"
         f"&direction=desc&per_page=50"],
        check=True, capture_output=True, text=True)
    prs = [pr for pr in json.loads(result.stdout)
           if pr["merged_at"] and pr["base"]["ref"] in BASES]
    prs.sort(key=lambda pr: pr["merged_at"], reverse=True)
    return prs[:COUNT]


def parse_time(stamp):
    return datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")


def day(when):
    return f"{when.day} {when:%b %Y}"


def render_pr(pr):
    merged = parse_time(pr["merged_at"])
    return (f'        <li><time datetime="{pr["merged_at"]}">{day(merged)}'
            f'</time><a href="{html.escape(pr["html_url"])}">'
            f'#{pr["number"]}</a><span>{html.escape(pr["title"])}'
            f'</span></li>\n')


def fill(text, marker, content):
    pattern = re.compile(f"(<!-- {marker}:start -->)(.*?)(<!-- {marker}:end -->)",
                         re.DOTALL)
    if not pattern.search(text):
        sys.exit(f"update-site: no {marker} markers in src/index.html")
    return pattern.sub(lambda m: m.group(1) + content + m.group(3), text,
                       count=1)


def wrap(fragment):
    """Turn the fragment into a full page: what precedes <main> is the head."""
    head, body = fragment.split("<main", 1)
    head = "".join(line for line in head.splitlines(keepends=True)
                   if "claude:viewport-fit-sides" not in line)
    return ("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
            "<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" "
            "content=\"width=device-width, initial-scale=1\">\n"
            f"{head}</head>\n<body>\n<main{body}</body>\n</html>\n")


def write_atomic(path, text):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".index-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fragment", action="store_true")
    parser.add_argument("outdir", nargs="?",
                        default="/var/www/rose-os.org/html")
    args = parser.parse_args()

    with open(os.path.join(SRC, "index.html"), encoding="utf-8") as f:
        page = f.read()

    now = datetime.datetime.now(datetime.timezone.utc)
    items = "".join(render_pr(pr) for pr in merged_prs())
    page = fill(page, "merged", "\n" + items)
    page = fill(page, "updated", f"Updated {day(now)}, {now:%H:%M} UTC")

    os.makedirs(args.outdir, exist_ok=True)
    if args.fragment:
        write_atomic(os.path.join(args.outdir, "index.html"), page)
    else:
        write_atomic(os.path.join(args.outdir, "index.html"), wrap(page))

    image = os.path.join(SRC, "rose.jpg")
    target = os.path.join(args.outdir, "rose.jpg")
    if not os.path.exists(target) or not filecmp.cmp(image, target,
                                                      shallow=False):
        shutil.copyfile(image, target)
        os.chmod(target, 0o644)


if __name__ == "__main__":
    main()
