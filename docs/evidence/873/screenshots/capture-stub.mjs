// Reference-capture stub: serves apps/web/out and one synthetic setup report.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
const [root, port, mode] = process.argv.slice(2);
const ids = mode === 'new' ? ['cloudroom','harness','personal_github','github_app','project','remote_access']
  : ['cloudroom','harness','personal_github','github_app','project','engine','remote_access'];
const text = { cloudroom: ['CloudRoom is signed in on this host.', 'Nothing to do.'], harness: ['Claude Code is listed with its model and effort.', 'Nothing to do.'],
  personal_github: ['synthetic-owner can push to synthetic-owner/first-idea.', 'Nothing to do.'], github_app: ['The OpenWiz GitHub App can reach synthetic-owner/first-idea.', 'Nothing to do.'],
  project: ['synthetic-owner/first-idea is set up with CI and review.', 'Nothing to do.'],
  engine: ['No engine has been selected or activated.', 'Choose Cloud or Local after reviewing costs and the proposed effects.'],
  remote_access: ['Authenticated phone access has not been verified.', 'Use a named Cloudflare Tunnel with owner-only Access, or authenticated Tailscale.'] };
const state = (id) => id === 'engine' ? 'missing' : id === 'remote_access' ? 'unknown' : 'verified';
const setup = { schema: 'openwiz.setup.v1', ready: mode === 'new', components: ids.map((id) => ({ id, state: state(id), reason: text[id][0], next: text[id][1] })),
  engine: 'unselected', cost: { provenance: 'unknown', credits: null, window_s: null, monthly_projection: null, free_allowance: null, reason: 'Cloud Credits have not been measured.' }, operations: [] };
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.woff2': 'font/woff2', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webmanifest': 'application/manifest+json' };
createServer(async (req, res) => {
  const path = new URL(req.url, 'http://x').pathname;
  if (path === '/api/v1/setup') { res.writeHead(200, { 'content-type': 'application/json' }); return res.end(JSON.stringify(setup)); }
  if (path.startsWith('/api/')) { res.writeHead(503, { 'content-type': 'application/json' }); return res.end('{"error":"synthetic: not served"}'); }
  let file = normalize(join(root, path === '/' ? 'index.html' : path));
  if (!extname(file)) file += '.html';
  try { const body = await readFile(file); res.writeHead(200, { 'content-type': types[extname(file)] ?? 'application/octet-stream' }); res.end(body); }
  catch { res.writeHead(404); res.end('no'); }
}).listen(Number(port), '127.0.0.1');
