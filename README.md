# rose-os.org

The landing page for [Rose](https://github.com/blancolioni/rose), a persistent, capability-based operating system written in Ada.

## Layout

- `src/index.html`: the page. It is a fragment (title, styles and `<main>`), so it can also be previewed as a Claude artifact. The generator adds the document wrapper.
- `src/rose.jpg`: the rose photo, from `icons/rose-small.png` in the Rose repository.
- `src/rose-disc.webp`: the label art for the installation CD-ROM, the link to the ISO download, with its version and size beside it; 320 px wide, with a transparent background.
- `update-site.py`: fills in the "Recently merged" list with the last five pull requests merged into blancolioni/rose, the ISO download link with the version and size of the published ISO (`rose.iso.version`, written by `make publish-iso`), and the link to the latest nightly build, and writes `index.html` and `rose.jpg` to the web root.
- `nightly-build.sh`: keeps its own clones of rose, syn and idle in `~/nightly`, tracking `main`. Each night that any of them has moved, it builds idle and Rose, runs `test-boot` and the checkpoint log's tests (`test-log-wrap`, `test-log-clean`, `test-log-crash`), and if they all pass, publishes the ISO to `/nightly/` as `rose-DATE-COMMIT.iso`, with a `.txt` naming the three commits, `rose-latest.iso` pointing at it, and `SHA256SUMS`. It keeps the last seven, and the first of each month. `status.txt` says how the last night went; the logs are in `~/scratch/nightly/DATE` for a week.
- `update-book.sh`: keeps its own clone of Rose at `~/rose-book-src`, tracking `main`. When `main` has moved, it builds the Rose Book (`make adoc` in `doc/rose-book`) and publishes the HTML, PDF and EPUB to `/rose-book/`. Branches and worktrees never reach the website.
- `update-stats.sh`: builds a visitor report with GoAccess from `/var/log/nginx/rose-os.org.log` and its rotated copies, and writes it to `~/rose-stats/index.html`, outside the web root. IP addresses are anonymised; crawlers, 404s and query strings are left out.
- `systemd/`: user services and timers that run the generator and the book updater every 15 minutes, the stats report every hour, and the nightly build at 00:30 UTC.

The ISO (`/rose.iso`) is published separately, from the Rose repository, by `make publish-iso`.

## Running

The generator needs an authenticated `gh`, and write access to `/var/www/rose-os.org/html`.

```sh
./update-site.py                      # publish to /var/www/rose-os.org/html
./update-site.py staging              # write a full page to ./staging instead
./update-site.py --fragment preview   # write the filled-in fragment, for previews
```

## Installing the timer

The units run the generator from `~/rose-site`, so clone this repository there.

```sh
cp systemd/rose-site.service systemd/rose-site.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now rose-site.timer
```

Lingering must be on (`loginctl enable-linger`) for the timer to run while you are logged out. `journalctl --user -u rose-site.service` shows the output of each run.

Changes to `src/index.html` are published by the next run, or at once with `systemctl --user start rose-site.service`.

The book's timer is installed the same way, and needs `asciidoctor`, `asciidoctor-pdf`, `asciidoctor-epub3` and `python3-pyyaml`. The first run clones Rose, so give it a few minutes.

```sh
cp systemd/rose-book.service systemd/rose-book.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now rose-book.timer
```

The nightly build's timer is installed the same way. It needs what building and testing Rose needs (see Rose's README): `alr` in `~/bin`, GNAT, `qemu-system-x86`, `xorriso` and the GRUB tools. Its directory has to exist, be writable by the user, and be listed by nginx, with a block like this in the site's server block:

```nginx
location /nightly/ {
    autoindex on;
    autoindex_localtime off;
    location ~ \.iso$ {
        types { }
        default_type application/octet-stream;
        add_header Content-Disposition "attachment";
    }
}
```

```sh
mkdir -p /var/www/rose-os.org/html/nightly
cp systemd/rose-nightly.service systemd/rose-nightly.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now rose-nightly.timer
```

The first run clones the three repositories. A build and the tests take about four hours on two processors; `NIGHTLY_FORCE=1 ./nightly-build.sh` builds at once, even if nothing has moved.

The stats timer needs `goaccess`, and read access to `/var/log/nginx`: the user must be in the group that owns the logs (`weblogs`), and `/etc/logrotate.d/nginx` must create new logs with that group (`create 0640 nginx weblogs`). nginx writes the site's own log, set in its server block with `access_log /var/log/nginx/rose-os.org.log main;`.

```sh
cp systemd/rose-stats.service systemd/rose-stats.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now rose-stats.timer
```

The report is private; copy it with `scp thewhitelion.eu:rose-stats/index.html .`. A user service only sees a group added after login once the user manager restarts, so if the first run says "Permission denied", run `loginctl terminate-user fraser` and log in again.

## Licence

GNU General Public License v3, the same as Rose; see `LICENSE`.
