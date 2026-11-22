#!/usr/bin/env python3
# Red scaffold for #2379: sends the request with no checks at all.
import http.client, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


class Refused(Exception):
    pass


def registry():
    with open(os.path.join(HERE, 'hosts.json')) as f:
        return json.load(f)


def find_key(entry, environ):
    return environ.get(entry['variable'], '')


def send(origin, method, path, body, key):
    scheme, _, rest = origin.partition('://')
    host, _, port = rest.partition(':')
    conn = (http.client.HTTPSConnection if scheme == 'https' else http.client.HTTPConnection)(host, int(port))
    conn.request(method, path, body=None if body is None else json.dumps(body),
                 headers={'Authorization': 'Bearer ' + key})
    r = conn.getresponse()
    return r.status, r.read()


def main():
    req = json.loads(sys.stdin.read())
    entry = registry()[req['host']]
    origin = os.environ.get('OPENWIZ_HOSTKEY_TEST_ORIGIN') or entry['origin']
    status, raw = send(origin, req['method'], req['path'], req.get('body'), find_key(entry, os.environ))
    try:
        body = json.loads(raw)
    except ValueError:
        body = None
    print(json.dumps({'status': status, 'body': body}))


if __name__ == '__main__':
    main()
