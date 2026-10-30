#!/bin/sh
# Rebuild the Rose Book from the main branch of Rose, and publish it.
#
# The book is built in a clone that only tracks origin/main, so branches
# and worktrees never reach the website.  Nothing is built unless main
# has moved since the last publication.  Each file is copied to a
# temporary name and renamed into place, so a download never gets a
# half-written book.
#
# SRC and OUT can be set in the environment, for testing.

set -eu

REPO=https://github.com/blancolioni/rose.git
SRC=${SRC:-$HOME/rose-book-src}
OUT=${OUT:-/var/www/rose-os.org/html/rose-book}
STAMP=$SRC/.published

[ -d "$SRC/.git" ] || git clone -q "$REPO" "$SRC"
cd "$SRC"
git fetch -q origin main
git reset -q --hard origin/main

head=$(git rev-parse HEAD)
if [ "$(cat "$STAMP" 2>/dev/null || true)" = "$head" ]; then
    exit 0
fi

make -C doc/rose-book adoc

build=doc/rose-book/build
publish() {
    cp "$build/$1" "$OUT/.$2.new"
    mv -f "$OUT/.$2.new" "$OUT/$2"
}
publish rose-book.html rose-book.html
publish rose-book.html index.html
publish rose-book.pdf rose-book.pdf
publish rose-book.epub rose-book.epub

echo "$head" > "$STAMP"
echo "Published the Rose Book from $head"
