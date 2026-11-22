#!/bin/sh
# Builds the rose-os.org visitor report from the nginx log.
#
#   update-stats.sh [OUT]
#
# The report is OUT/index.html, ~/rose-stats by default. logrotate keeps
# ten days of logs, so the report keeps its own history: each rotated log,
# once complete, is added to a GoAccess database (STATS_DB, by default
# ~/.local/share/rose-stats), once only. The report is that history and
# the current log, which is read each time and not saved.
#
# The rotated logs are opened by their dated names, rose-os.org.log-DATE
# or rose-os.org.log-DATE.gz, without listing /var/log/nginx: an update of
# nginx-filesystem resets the directory to root:root 0711, which can be
# entered but not listed, and the report then lost everything but the
# current log each night.
set -eu

log=/var/log/nginx/rose-os.org.log
out=${1:-$HOME/rose-stats}
db=${STATS_DB:-$HOME/.local/share/rose-stats}
done_list=$db/added
days=${STATS_DAYS:-30}
# How many days back to look for rotated logs that haven't been added:
# more than logrotate keeps, in case the timer didn't run for a while.

[ -r "$log" ] || { echo "update-stats.sh: cannot read $log" >&2; exit 1; }

mkdir -p "$out" "$db"
touch "$done_list"

goaccess_options="--log-format=COMBINED --anonymize-ip --ignore-crawlers
    --ignore-status=404 --no-query-string --db-path=$db"

# Add each complete rotated log that isn't in the history yet, oldest
# first. logrotate names a log by the day it rotated it, today's included,
# and the history records that date, so a log that logrotate compresses a
# day later (delaycompress) isn't added again.

i=$days
while [ "$i" -ge 0 ]; do
    date=$(date -u -d "-$i day" +%Y%m%d)
    i=$((i - 1))
    grep -qx "$date" "$done_list" && continue
    if [ -r "$log-$date.gz" ]; then
        file=$log-$date.gz
    elif [ -r "$log-$date" ]; then
        file=$log-$date
    else
        continue
    fi
    restore=
    [ -s "$done_list" ] && restore=--restore
    # shellcheck disable=SC2086
    zcat -f "$file" | goaccess - $goaccess_options $restore --persist \
        -o "$db/last-added.html"
    echo "$date" >> "$done_list"
done

# The report: the history, and the current log, which isn't saved.

restore=
[ -s "$done_list" ] && restore=--restore
# shellcheck disable=SC2086
goaccess "$log" $goaccess_options $restore -o "$out/index.html"
