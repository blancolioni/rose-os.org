#!/usr/bin/env python3
"""Regenerate the rose-os.org landing page.

Fills the "Recently resolved" list in src/index.html with the issues
last closed as completed in the current milestone of blancolioni/rose
(the open milestone with the lowest version), with its progress, and
the download button with the version and size of the published ISO,
then writes the
page, its image and its icons to OUTDIR.  src/index.html is a page
fragment (title, styles and <main>), so the same file can be previewed
as a Claude artifact; this script adds the document wrapper.

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
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
# Copied beside the page as they are.
ASSETS = ("rose.jpg", "rose-disc.webp", "favicon.svg", "apple-touch-icon.png")
# Published from the Rose repository ("make publish-iso"), not by this
# script; its size goes on the download button.
ISO = "/var/www/rose-os.org/html/rose.iso"
# Written next to the ISO by "make publish-iso": the ISO's Rose
# version, such as 0.2.0, which goes on the download button before
# its size.
ISO_VERSION = ISO + ".version"


def gh_api(path):
    result = subprocess.run(["gh", "api", path],
                            check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def version_key(title):
    """(0, 3, 0) for "0.3.0"; None for a milestone that is not a version."""
    try:
        return tuple(int(part) for part in title.split("."))
    except ValueError:
        return None


def current_milestone():
    """The open milestone with the lowest version, or None."""
    milestones = [m for m in gh_api(f"repos/{REPO}/milestones?state=open"
                                    f"&per_page=100")
                  if version_key(m["title"])]
    return min(milestones, key=lambda m: version_key(m["title"]),
               default=None)


def resolved_issues(milestone):
    # Closing an issue updates it, so the most recently closed ones are
    # among the most recently updated.
    issues = gh_api(f"repos/{REPO}/issues?milestone={milestone['number']}"
                    f"&state=closed&sort=updated&direction=desc"
                    f"&per_page=100")
    issues = [issue for issue in issues
              if "pull_request" not in issue
              and issue.get("state_reason") == "completed"]
    issues.sort(key=lambda issue: issue["closed_at"], reverse=True)
    return issues[:COUNT]


def day(when):
    return f"{when.day} {when:%b %Y}"


def render_issue(issue):
    return (f'          <li><a class="issue" '
            f'href="{html.escape(issue["html_url"])}">'
            f'#{issue["number"]}</a>'
            f'<span>{html.escape(issue["title"])}</span></li>\n')


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
    milestone = current_milestone()
    if milestone:
        done = milestone["closed_issues"]
        total = done + milestone["open_issues"]
        page = fill(page, "milestone",
                    f' for <a href="{html.escape(milestone["html_url"])}">'
                    f'{html.escape(milestone["title"])}</a>')
        page = fill(page, "progress", f"{done} of {total} done · ")
        items = "".join(render_issue(i) for i in resolved_issues(milestone))
        page = fill(page, "resolved", "\n" + items + "          ")
    page = fill(page, "updated", f"Updated {day(now)}, {now:%H:%M} UTC")
    if os.path.exists(ISO):
        megabytes = round(os.path.getsize(ISO) / 2 ** 20)
        page = fill(page, "isosize", f"{megabytes} MB")
    if os.path.exists(ISO_VERSION):
        with open(ISO_VERSION, encoding="utf-8") as f:
            version = f.read().strip()
        if version:
            page = fill(page, "isoversion",
                        f"{html.escape(version)} · ")

    os.makedirs(args.outdir, exist_ok=True)
    if args.fragment:
        write_atomic(os.path.join(args.outdir, "index.html"), page)
    else:
        write_atomic(os.path.join(args.outdir, "index.html"), wrap(page))

    for name in ASSETS:
        source = os.path.join(SRC, name)
        target = os.path.join(args.outdir, name)
        if not os.path.exists(target) or not filecmp.cmp(source, target,
                                                          shallow=False):
            shutil.copyfile(source, target)
            os.chmod(target, 0o644)


if __name__ == "__main__":
    main()
