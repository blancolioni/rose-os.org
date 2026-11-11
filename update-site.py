#!/usr/bin/env python3
"""Regenerate the rose-os.org landing page.

Fills the "Recently resolved" list in src/index.html with the issues
last closed as completed in the current milestone of blancolioni/rose
(the open milestone with the lowest version), with its progress, and
the download button with the version and size of the published ISO,
then writes the
page, its image and its icons to OUTDIR.  It also writes feed.xml
there, an Atom feed of the pull requests last merged into main.  src/index.html is a page
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
FEED_COUNT = 20
FEED_URL = "https://rose-os.org/feed.xml"
# The default branch was renamed from master to main; merged pull
# requests keep the base they had.
BASES = ("main", "master")
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


def gh_api(path, paginate=False):
    """The JSON at path. With paginate, every page of a list, as one
    list."""
    command = ["gh", "api", path]
    if paginate:
        command += ["--paginate", "--slurp"]
    result = subprocess.run(command,
                            check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    if paginate:
        data = [item for page in data for item in page]
    return data


def version_key(title):
    """(0, 4, 0) for "0.4.0" or "0.4.0 genki"; None for a milestone
    that is not a version."""
    try:
        return tuple(int(part) for part in title.split()[0].split("."))
    except (ValueError, IndexError):
        return None


def current_milestone():
    """The open milestone with the lowest version, or None."""
    milestones = [m for m in gh_api(f"repos/{REPO}/milestones?state=open"
                                    f"&per_page=100")
                  if version_key(m["title"])]
    return min(milestones, key=lambda m: version_key(m["title"]),
               default=None)


def milestone_issues(milestone):
    """The open issues and the issues closed as completed in milestone.
    The milestone's own counts can't be used: they include pull
    requests, and issues closed as not planned."""
    items = gh_api(f"repos/{REPO}/issues?milestone={milestone['number']}"
                   f"&state=all&per_page=100", paginate=True)
    return [item for item in items
            if "pull_request" not in item
            and (item["state"] == "open"
                 or item.get("state_reason") == "completed")]


def resolved_issues(issues):
    """The most recently completed of issues."""
    done = [issue for issue in issues if issue["state"] == "closed"]
    done.sort(key=lambda issue: issue["closed_at"], reverse=True)
    return done[:COUNT]


def merged_prs():
    # Merging a pull request updates it, so the most recently merged
    # ones are among the most recently updated.
    prs = [pr for pr in gh_api(f"repos/{REPO}/pulls?state=closed"
                               f"&sort=updated&direction=desc&per_page=100")
           if pr["merged_at"] and pr["base"]["ref"] in BASES]
    prs.sort(key=lambda pr: pr["merged_at"], reverse=True)
    return prs[:FEED_COUNT]


def summary(body):
    """The first paragraph of prose in a pull request's description, as
    plain text: headings, lists and "Closes #N." lines are skipped."""
    text = (body or "").replace("\r\n", "\n")
    for paragraph in text.split("\n\n"):
        lines = [line for line in paragraph.strip().splitlines()
                 if not line.startswith("#")]
        prose = " ".join(" ".join(lines).split())
        if (not prose or prose.startswith(("- ", "* ", "|", "```"))
                or re.fullmatch(r"(?i)((closes|fixes|resolves) #\d+\.?\s*)+",
                                prose)):
            continue
        prose = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", prose)
        return re.sub(r"\*\*|`", "", prose)
    return ""


def render_entry(pr):
    return (f'  <entry>\n'
            f'    <title>#{pr["number"]} {html.escape(pr["title"])}</title>\n'
            f'    <link href="{html.escape(pr["html_url"])}"/>\n'
            f'    <id>{html.escape(pr["html_url"])}</id>\n'
            f'    <updated>{pr["merged_at"]}</updated>\n'
            f'    <author><name>{html.escape(pr["user"]["login"])}</name>'
            f'</author>\n'
            f'    <summary>{html.escape(summary(pr["body"]))}</summary>\n'
            f'  </entry>\n')


def feed(prs):
    # The feed's time is its newest entry's, so the file only changes
    # when something is merged.
    updated = prs[0]["merged_at"] if prs else "1970-01-01T00:00:00Z"
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<feed xmlns="http://www.w3.org/2005/Atom">\n'
            '  <title>Rose: merged pull requests</title>\n'
            '  <subtitle>Pull requests merged into the Rose operating '
            'system</subtitle>\n'
            f'  <link rel="self" href="{FEED_URL}"/>\n'
            f'  <link rel="alternate" href="https://github.com/{REPO}/pulls'
            f'?q=is%3Apr+is%3Amerged"/>\n'
            f'  <id>{FEED_URL}</id>\n'
            f'  <updated>{updated}</updated>\n'
            + "".join(render_entry(pr) for pr in prs)
            + '</feed>\n')


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


def write_if_changed(path, text):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return
    write_atomic(path, text)


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
        issues = milestone_issues(milestone)
        done = sum(1 for issue in issues if issue["state"] == "closed")
        total = len(issues)
        page = fill(page, "milestone",
                    f' for <a href="{html.escape(milestone["html_url"])}">'
                    f'{html.escape(milestone["title"])}</a>')
        page = fill(page, "progress", f"{done} of {total} done · ")
        items = "".join(render_issue(i) for i in resolved_issues(issues))
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
    write_if_changed(os.path.join(args.outdir, "feed.xml"),
                     feed(merged_prs()))

    for name in ASSETS:
        source = os.path.join(SRC, name)
        target = os.path.join(args.outdir, name)
        if not os.path.exists(target) or not filecmp.cmp(source, target,
                                                          shallow=False):
            shutil.copyfile(source, target)
            os.chmod(target, 0o644)


if __name__ == "__main__":
    main()
