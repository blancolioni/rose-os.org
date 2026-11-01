#!/bin/sh
# Builds the rose-os.org visitor report from the nginx log.
set -eu

log=/var/log/nginx/rose-os.org.log
out=${1:-$HOME/rose-stats}

mkdir -p "$out"

{
    for f in "$log"-*; do
        [ -e "$f" ] && zcat -f "$f"
    done
    cat "$log"
} | goaccess - --log-format=COMBINED --anonymize-ip --ignore-crawlers \
    --ignore-status=404 --no-query-string -o "$out/index.html"
