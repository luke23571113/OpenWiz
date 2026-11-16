# War room web: the private serving contract (WRD4, #877; WRD5, #883)

How the War room site is served privately. It adds no product API, collection schema or
external consumer: six published files, read and served as they are.

## Artifact

- **What:** `war-room.html`, the page exactly as `page.render` wrote it for that tick: the
  original HTML, never a PNG wrapper or the `publish.drawable` transform. Its text is
  selectable; its charts are inline static SVG; its values, Sources and inventory are native
  `<details>` and tables; its headings font is embedded as `data:`. It has no script and
  makes no remote request; evidence links are plain links.
- **WRD5 site:** `war-room.html` is the home page, and five child pages sit beside it,
  each written by `page.site` in the same way and with the same properties:

  | Route | File |
  | --- | --- |
  | `/` | `war-room.html` (home) |
  | `/speed` | `war-room-speed.html` |
  | `/health` | `war-room-health.html` |
  | `/cost` | `war-room-cost.html` |
  | `/quality` | `war-room-quality.html` |
  | `/skills` | `war-room-skills.html` |

  These six names are the whole site; there is no other HTML artifact. Page links are
  relative to the site root (`./`, `speed`, `health#bench-main_ci`), so they need no host.
- **Where:** the root of the private `war-room` branch, beside `war-room.png`,
  `war-room-phone.png`, `README.md` and `samples/`.
- **Publication:** `publish.py publish` renders all six pages from one saved sample and one
  chart bundle and writes them in the same commit as the pictures and the README, after the
  privacy scan has read every one, and pushes only `refs/heads/war-room`. A failed render
  (of any page), validation, scan or push publishes nothing, so the branch keeps its last
  good site and pictures together; a new home never joins old children. A five-minute
  collection never changes them. Saved samples stay byte-for-byte.
- **Identity:** the `war-room` commit that holds them, and the sha256 of each page's bytes.

## Adapter: `web/serve.py`

```sh
python3 -I tools/war-room/web/serve.py fetch --remote URL --into DIR   # read-only; the caller authenticates git
python3 -I tools/war-room/web/serve.py serve --root DIR [--port N]     # loopback only; --port 0 prints the bound port
```

**fetch** reads `refs/heads/war-room` from `URL` (depth 1, never pushes) and accepts the
site only if each of the six files is a plain file (`100644` blob) of at most 8 MiB, UTF-8,
starting `<!doctype html>`, with no `<script`, and carrying the page's own
`Content-Security-Policy` meta tag. It writes them, with `identity.json` (`commit`, and
`sha256` per file name), into a new folder `DIR/site-*`, then replaces the link
`DIR/current` to point at it in one rename; the folder it replaced is kept and older ones are
removed. Anything else (an unreachable remote, no branch, a missing child, a link, one bad
page) exits 1 and leaves `DIR/current` as it was: the last good site stays served, every
route from the same generation. Errors never echo the remote URL. A `DIR` that WRD4's
adapter filled (`DIR/war-room.html`, no `current`) serves nothing until the first good site
fetch, so the site is published before the adapter is switched.

**serve** binds `127.0.0.1` only. Routes, matched exactly on the request's own target:

| Request | Answer |
| --- | --- |
| `GET` or `HEAD` one of the six routes (any query) | `200`, the bytes of its file in `DIR/current` |
| `GET` or `HEAD` a route before any good fetch | `503` |
| any other path, including `/war-room.html`, `/war-room-speed.html`, `/speed/`, `//health`, `/identity.json`, `/samples/...` | `404` |
| any other method | `405` |

The `200` carries `Content-Type: text/html; charset=utf-8`, `Cache-Control: no-store`,
`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`,
`Content-Security-Policy` equal to the page's own policy plus `frame-ancestors 'none'`,
`ETag` (the sha256) and `X-War-Room-Commit` (the source commit, when `identity.json`
matches the bytes). A deep link is a route and a fragment, such as `/speed#fig-10`; a home
row links to its bench's Sources on its child page (`/health#bench-main_ci`), and the
browser opens that closed disclosure itself.

## Authentication boundary

The adapter authenticates nobody and reads no identity header or cookie. Access is the
existing tunnel's and Access's: Cloudflare Access at the edge, then `cloudflared`'s
`originRequest.access` check, in front of a loopback-only origin, as in the existing web
access model. Only the configured hostname routes to the port; there is no other alias. All
six routes sit behind that same boundary; WRD5 adds no host, path rule, account, DNS or
Access change. The exact hostname, team and setup are private records.
