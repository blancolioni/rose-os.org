# rose-os.org

The landing page for [Rose](https://github.com/blancolioni/rose), a persistent, capability-based operating system written in Ada.

## Layout

- `src/index.html`: the page. It is a fragment (title, styles and `<main>`), so it can also be previewed as a Claude artifact. The generator adds the document wrapper.
- `src/rose.jpg`: the rose photo, from `icons/rose-small.png` in the Rose repository.
- `src/rose-disc.webp`: the label art for the installation CD-ROM, the link to the ISO download, with its version and size beside it; 320 px wide, with a transparent background.
- `update-site.py`: fills in the "Recently merged" list with the last five pull requests merged into blancolioni/rose, and the ISO download link with the version and size of the published ISO (`rose.iso.version`, written by `make publish-iso`), and writes `index.html` and `rose.jpg` to the web root.
- `update-book.sh`: keeps its own clone of Rose at `~/rose-book-src`, tracking `main`. When `main` has moved, it builds the Rose Book (`make adoc` in `doc/rose-book`) and publishes the HTML, PDF and EPUB to `/rose-book/`. Branches and worktrees never reach the website.
- `systemd/`: user services and timers that run the generator and the book updater every 15 minutes.

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

## Licence

GNU General Public License v3, the same as Rose; see `LICENSE`.
