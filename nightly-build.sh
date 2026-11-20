#!/bin/sh
# Build Rose from the latest main branches of rose, syn and idle, test it,
# and publish its installation ISO to /nightly/ on the website.
#
# It keeps its own clones in ~/nightly, which only track origin/main, so
# branches, worktrees and the idle in ~/bin never reach a nightly build.
# Each night it:
#
#   1. fetches the three repositories, and stops if none of them has
#      moved since the last night's build, whether that passed or not;
#   2. builds idle with alr, and Rose with clean-build.sh;
#   3. runs scripts/test-boot, then the checkpoint log's tests,
#      test-log-wrap, test-log-clean and test-log-crash, each that the
#      Rose being built has, one after the other;
#   4. if all of them passed, copies images/rose.iso to
#      rose-DATE-COMMIT.iso, with a .txt file that names the three
#      commits, points rose-latest.iso at it, and updates SHA256SUMS;
#   5. keeps the last seven nightly ISOs, and the first of each month.
#
# status.txt says how the last night went, whether or not it published
# an ISO.  The logs are in ~/scratch/nightly/DATE, for a week.
#
# NIGHTLY, OUT and LOGS can be set in the environment, for testing; with
# NIGHTLY_FORCE=1 it builds even if nothing has moved, and NIGHTLY_TESTS
# replaces the list of tests.

set -eu

NIGHTLY=${NIGHTLY:-$HOME/nightly}
OUT=${OUT:-/var/www/rose-os.org/html/nightly}
LOGS=${LOGS:-$HOME/scratch/nightly}
KEEP=7
TESTS=${NIGHTLY_TESTS:-test-boot test-log-wrap test-log-clean test-log-crash}

today=$(date -u +%F)
log_dir=$LOGS/$today
mkdir -p "$NIGHTLY" "$OUT" "$log_dir"

# One build at a time: a build that runs past the next night's start
# makes that night's run stop here.
exec 9> "$NIGHTLY/.lock"
flock -n 9 || { echo "nightly: a build is already running"; exit 0; }

say () {
    echo "nightly: $*"
}

status () {
    # status RESULT: write status.txt, in place
    {
        echo "Nightly build of $today: $1"
        echo
        for repo in rose syn idle; do
            echo "$repo $(git -C "$NIGHTLY/$repo" log -1 \
                --format='%h %cs %s' 2> /dev/null || echo '(no clone)')"
        done
    } > "$OUT/.status.txt.new"
    chmod 644 "$OUT/.status.txt.new"
    mv -f "$OUT/.status.txt.new" "$OUT/status.txt"
}

failed () {
    # failed STEP: say that STEP failed, and stop
    say "$1 failed; the log is in $log_dir"
    status "failed: $1"
    exit 1
}

for repo in rose syn idle; do
    if [ ! -d "$NIGHTLY/$repo/.git" ]; then
        git clone -q "https://github.com/blancolioni/$repo.git" \
            "$NIGHTLY/$repo" || failed "cloning $repo"
    fi
    git -C "$NIGHTLY/$repo" fetch -q origin main || failed "fetching $repo"
    git -C "$NIGHTLY/$repo" reset -q --hard origin/main
    git -C "$NIGHTLY/$repo" clean -q -f -d -x
done

heads=$(for repo in rose syn idle; do
            git -C "$NIGHTLY/$repo" rev-parse HEAD
        done)
if [ "${NIGHTLY_FORCE:-0}" != 1 ] \
   && [ "$heads" = "$(cat "$NIGHTLY/.built" 2> /dev/null || true)" ]; then
    say "nothing has moved since the last build"
    exit 0
fi
echo "$heads" > "$NIGHTLY/.built"

say "building idle"
(cd "$NIGHTLY/idle" && alr -n build) > "$log_dir/idle.log" 2>&1 \
    || failed "building idle"

say "building Rose"
(cd "$NIGHTLY/rose" \
     && IDLE=$NIGHTLY/idle/bin/idle JOBS=${JOBS:-2} ./clean-build.sh) \
    > "$log_dir/build.log" 2>&1 \
    || failed "building Rose"

passed=""
for test in $TESTS; do
    [ -f "$NIGHTLY/rose/scripts/$test" ] || continue
    say "running $test"
    rm -rf "${log_dir:?}/$test"
    mkdir -p "$log_dir/$test"
    (cd "$NIGHTLY/rose" && ROSE_TEST_DIR=$log_dir/$test sh "scripts/$test") \
        > "$log_dir/$test.log" 2>&1 \
        || failed "$test"
    passed="$passed $test"
done

# Publish: each file goes to a temporary name and is renamed into place,
# so that a download never gets half a file.

commit=$(git -C "$NIGHTLY/rose" rev-parse --short=7 HEAD)
name=rose-$today-$commit
cp "$NIGHTLY/rose/images/rose.iso" "$OUT/.$name.iso.new"
chmod 644 "$OUT/.$name.iso.new"
mv -f "$OUT/.$name.iso.new" "$OUT/$name.iso"
{
    echo "Rose nightly build, $today"
    echo
    for repo in rose syn idle; do
        echo "$repo $(git -C "$NIGHTLY/$repo" log -1 --format='%H %cs %s')"
    done
    echo
    echo "Tests passed:$passed"
} > "$OUT/.$name.txt.new"
chmod 644 "$OUT/.$name.txt.new"
mv -f "$OUT/.$name.txt.new" "$OUT/$name.txt"
ln -sfn "$name.iso" "$OUT/.rose-latest.iso.new"
mv -fT "$OUT/.rose-latest.iso.new" "$OUT/rose-latest.iso"

# The last KEEP nightly ISOs, and the first of each month, stay.  The
# day of the month is characters 14 and 15 of rose-YYYY-MM-DD-....

ls "$OUT" | grep -E '^rose-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9a-f]+\.iso$' \
    | sort -r | awk -v keep=$KEEP '
        NR > keep && substr($0, 14, 2) != "01" { print }' \
    | while read -r old; do
          rm -f "$OUT/$old" "$OUT/${old%.iso}.txt"
      done

(cd "$OUT" \
     && sha256sum rose-[0-9]*.iso > .SHA256SUMS.new \
     && chmod 644 .SHA256SUMS.new \
     && mv -f .SHA256SUMS.new SHA256SUMS)

status "passed; published $name.iso"
say "published $name.iso"

# A week of logs; a test's directory is empty after it passes.
find "$LOGS" -mindepth 1 -maxdepth 1 -type d -mtime +7 -exec rm -rf {} +
