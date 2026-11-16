# War room web: the private serving contract (WRD4, #877)

How the War room page is served privately. It adds no product API, collection schema or
external consumer: one published file, read and served as it is.

## Artifact

- **What:** `war-room.html`, the page exactly as `page.render` wrote it for that tick: the
  original HTML, never a PNG wrapper or the `publish.drawable` transform. Its text is
  selectable; its charts are inline static SVG; its values, Sources and inventory are native
  `<details>` and tables; its headings font is embedded as `data:`. It has no script and
  makes no remote request; evidence links are plain links.
- **Where:** the root of the private `war-room` branch, beside `war-room.png`,
  `war-room-phone.png`, `README.md` and `samples/`.
- **Publication:** `publish.py publish` writes it in the same commit as the pictures and the
  README, after the privacy scan has read it, and pushes only `refs/heads/war-room`. A failed
  render, validation, scan or push publishes nothing, so the branch keeps its last good page
  and pictures together. A five-minute collection never changes it. Saved samples stay
  byte-for-byte.
- **Identity:** the `war-room` commit that holds it, and the sha256 of its bytes.

## Adapter: `web/serve.py`

```sh
python3 -I tools/war-room/web/serve.py fetch --remote URL --into DIR   # read-only; the caller authenticates git
python3 -I tools/war-room/web/serve.py serve --root DIR [--port N]     # loopback only; --port 0 prints the bound port
```

**fetch** reads `refs/heads/war-room` from `URL` (depth 1, never pushes) and accepts
`war-room.html` only if it is a plain file (`100644` blob) of at most 8 MiB, UTF-8, starting
`<!doctype html>`, with no `<script`, and carrying the page's own
`Content-Security-Policy` meta tag. It then replaces `DIR/war-room.html` and
`DIR/identity.json` (`commit`, `sha256`) atomically. Anything else (an unreachable remote,
no branch, no page, a link, a bad page) exits 1 and leaves `DIR` as it was: the last good
page stays served. Errors never echo the remote URL.

**serve** binds `127.0.0.1` only. Routes:

| Request | Answer |
| --- | --- |
| `GET` or `HEAD` `/` (any query) | `200`, the bytes of `DIR/war-room.html` |
| `GET` or `HEAD` `/` before any good fetch | `503` |
| any other path, including `/war-room.html`, `/identity.json`, `/samples/...` | `404` |
| any other method | `405` |

The `200` carries `Content-Type: text/html; charset=utf-8`, `Cache-Control: no-store`,
`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`,
`Content-Security-Policy` equal to the page's own policy plus `frame-ancestors 'none'`,
`ETag` (the sha256) and `X-War-Room-Commit` (the source commit, when `identity.json`
matches the bytes). Section links are in-page fragments, so a deep link is `/#sources`.

## Authentication boundary

The adapter authenticates nobody and reads no identity header or cookie. Access is the
existing tunnel's and Access's: Cloudflare Access at the edge, then `cloudflared`'s
`originRequest.access` check, in front of a loopback-only origin, as in the existing web
access model. Only the configured hostname routes to the port; there is no other alias. The
exact hostname, team and setup are private records.
