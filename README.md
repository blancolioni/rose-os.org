# rose-os.org

The landing page for [Rose](https://github.com/blancolioni/rose), a persistent, capability-based operating system written in Ada.

## Layout

- `src/index.html`: the page. It is a fragment (title, styles and `<main>`), so it can also be previewed as a Claude artifact. The generator adds the document wrapper.
- `src/rose.jpg`: the rose photo, from `icons/rose-small.png` in the Rose repository.
- `src/rose-disc.webp`: the label art for the installation CD-ROM, shown beside the ISO download; 320 px wide, with a transparent background.
- `update-site.py`: fills in the "Recently merged" list with the last five pull requests merged into blancolioni/rose, and the download button with the version and size of the published ISO (`rose.iso.version`, written by `make publish-iso`), and writes `index.html` and `rose.jpg` to the web root.
- `systemd/`: a user service and timer that run the generator every 15 minutes.

The Rose Book (`/rose-book/`) and the ISO (`/rose.iso`) are published separately, from the Rose repository: the book by `make` in `doc/rose-book`, and the ISO by `make publish-iso`.

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

## Licence

GNU General Public License v3, the same as Rose; see `LICENSE`.
