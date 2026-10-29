# feeds

Atom feeds I want that nobody publishes. For now that means Hacker News
stories whose titles match terms I care about. Built hourly by a GitHub
Action and served at `https://stevenfazzio.com/feeds/`.

| Feed | URL |
|---|---|
| HN: where you can help | <https://stevenfazzio.com/feeds/hn-help.xml> |
| Show HN: your areas | <https://stevenfazzio.com/feeds/hn-show.xml> |
| HN: where you're curious | <https://stevenfazzio.com/feeds/hn-curious.xml> |
| HN: Wikipedia | <https://stevenfazzio.com/feeds/hn-wikipedia.xml> |

`https://stevenfazzio.com/feeds/feeds.opml` lists all of them for a feed
reader's import.

## How it works

`build.py` reads `feeds.toml` and searches the
[HN Algolia API](https://hn.algolia.com/api) once per term: titles only, no
typo matching, exact phrases. It then keeps only the titles that contain the
term as whole words, and writes one Atom file per feed into `site/`. Each
entry links to the HN thread, not the article, since the point is the
discussion. Entries leave out points and comment counts, so a reader never
treats an old story as new.

To change what a feed matches, edit `feeds.toml` and push. To build locally:

    uv run build.py

No dependencies beyond the standard library.

## Why not hnrss.org

It returned 502s for most requests on 2026-10-28, first for bursts like a
feed reader's refresh, then for single requests too. Algolia, which hnrss
uses behind the scenes, answered every request.

## Keeping the schedule alive

GitHub disables scheduled workflows in a public repo after 60 days without
repository activity, and doesn't define activity. The workflow pushes an empty
commit when the last commit is more than 45 days old. If the feeds ever stop
updating, check the Actions tab and run `gh workflow enable build.yml`.
