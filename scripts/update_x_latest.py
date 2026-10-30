#!/usr/bin/env python3
"""Public-only X v2 feed. Stdlib only; --sample is a network-free dry run."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'public/data/x-latest.json'
USERNAME = 'pandasczos'
# Conservative exclusions: never copy financial/account disclosures or credentials.
SENSITIVE = re.compile(
    r'\b(?:balance|balances|saldo|saldos|equity|net\s*worth|account\s*(?:value|number)|'
    r'buying\s*power|p\s*[&/]\s*l|pnl|profit|profits|loss|losses|ganancia\w*|pérdida\w*|'
    r'api[ _-]?key|secret|password|contraseña|bearer|x-access-token)\b|'
    r'(?:ghp_|github_pat_|sk-)[\w-]+|[\w.+-]+@[\w.-]+\.[a-z]{2,}|'
    r'(?:[$€£¥]|\b(?:USD|BOB|Bs\.?))\s*[\d,.]+|'
    r'\d[\d\s().+-]{8,}\d|[?&](?:token|key|auth|signature|secret)=', re.I)


def sample_feed():
    texts = [
        'Sample post: small tools that make everyday work clearer.',
        'Sample quote: useful systems start with a well-defined routine.',
        'Sample repost: an idea about building with AI.',
        'Sample post: turning a recurring task into a reusable script.',
        'Sample post: a little structure, room to do more.',
    ]
    return {'sample': True, 'posts': [
        {'text': text, 'type': kind, 'created_date': None,
         'link': f'https://x.com/{USERNAME}', 'thumbnail': None}
        for text, kind in zip(texts, ['post', 'quote', 'repost', 'post', 'post'])]}


def safe_text(text):
    return isinstance(text, str) and bool(text.strip()) and not SENSITIVE.search(text)


def post_text(post):
    note = post.get('note_tweet', post.get('note_post', {})) or {}
    return note.get('text') or post.get('text', '')


def thumbnail_for(post, media):
    for key in post.get('attachments', {}).get('media_keys', []):
        item = media.get(key, {})
        # alt_text is checked too; URLs must be public X image CDN resources.
        if item.get('alt_text') and not safe_text(item['alt_text']):
            continue
        value = item.get('preview_image_url') or item.get('url')
        if not isinstance(value, str):
            continue
        parsed = urlsplit(value)
        if (parsed.scheme == 'https' and parsed.netloc == 'pbs.twimg.com'
                and parsed.path.startswith(('/media/', '/ext_tw_video_thumb/', '/amplify_video_thumb/', '/tweet_video_thumb/'))):
            return value
    return None


def shape_feed(payload):
    """Whitelist fields; keep latest posts, quotes and reposts, never replies."""
    includes = payload.get('includes', {})
    references = {str(p['id']): p for p in includes.get('tweets', includes.get('posts', [])) if 'id' in p}
    media = {m['media_key']: m for m in includes.get('media', []) if 'media_key' in m}
    result, seen = [], set()
    for post in payload.get('data', []):
        identity = str(post.get('id', ''))
        refs = post.get('referenced_tweets', post.get('referenced_posts', [])) or []
        if (not re.fullmatch(r'\d{1,19}', identity) or identity in seen or post.get('possibly_sensitive')
                or post.get('withheld') or any(r.get('type') == 'replied_to' for r in refs)):
            continue
        try:
            stamp = datetime.fromisoformat(post['created_at'].replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        kind, source, text = 'post', post, post_text(post)
        ref = next((r for r in refs if r.get('type') == 'retweeted'), None)
        if ref:
            kind = 'repost'
            source = references.get(str(ref.get('id')), post)
            text = post_text(source)
        else:
            ref = next((r for r in refs if r.get('type') == 'quoted'), None)
            if ref:
                kind = 'quote'
                quoted = references.get(str(ref.get('id')))
                if quoted:
                    text += '\n\n↳ ' + post_text(quoted)
                    if quoted.get('possibly_sensitive') or quoted.get('withheld'):
                        continue
        if source.get('possibly_sensitive') or source.get('withheld') or not safe_text(text):
            continue
        link_id = str(source.get('id', identity)) if kind == 'repost' else identity
        if not re.fullmatch(r'\d{1,19}', link_id):
            continue
        link = f'https://x.com/i/status/{link_id}' if kind == 'repost' else f'https://x.com/{USERNAME}/status/{link_id}'
        result.append((stamp.astimezone(timezone.utc), identity, {
            'text': text.strip(), 'type': kind, 'created_date': stamp.date().isoformat(),
            'link': link, 'thumbnail': thumbnail_for(source, media),
        }))
        seen.add(identity)
    result.sort(key=lambda entry: (entry[0], int(entry[1])), reverse=True)
    return {'sample': False, 'posts': [entry[2] for entry in result[:5]]}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Do not forward Authorization to a redirect target.


def api_get(path, token, query=None):
    url = 'https://api.x.com/2/' + path
    if query:
        url += '?' + urlencode(query)
    request = Request(url, headers={'Authorization': 'Bearer ' + token, 'User-Agent': 'portfolio-public-feed/1.0'})
    with build_opener(NoRedirect).open(request, timeout=30) as response:
        return json.load(response)


def fetch_feed(token):
    user = api_get('users/by/username/' + USERNAME, token, {'user.fields': 'protected'})
    data = user.get('data', {})
    identity = str(data.get('id', ''))
    if data.get('protected') is not False or not re.fullmatch(r'\d{1,19}', identity):
        raise ValueError('Public profile unavailable')
    payload = api_get(f'users/{identity}/tweets', token, {
        'max_results': '100', 'exclude': 'replies',
        'tweet.fields': 'created_at,referenced_tweets,attachments,possibly_sensitive,note_tweet,withheld',
        'expansions': 'referenced_tweets.id,attachments.media_keys',
        'media.fields': 'url,preview_image_url,type,alt_text',
    })
    if payload.get('errors'):
        raise ValueError('Incomplete X response')
    # Media on referenced posts can require a separate public lookup.
    refs = [str(r.get('id')) for p in payload.get('data', []) for r in p.get('referenced_tweets', [])
            if r.get('type') in ('retweeted', 'quoted') and re.fullmatch(r'\d{1,19}', str(r.get('id', '')))]
    if refs:
        expanded = api_get('tweets', token, {
            'ids': ','.join(dict.fromkeys(refs)),
            'tweet.fields': 'attachments,possibly_sensitive,note_tweet,withheld',
            'expansions': 'attachments.media_keys',
            'media.fields': 'url,preview_image_url,type,alt_text',
        })
        includes = payload.setdefault('includes', {})
        includes.setdefault('tweets', []).extend(expanded.get('data', []))
        includes.setdefault('media', []).extend(expanded.get('includes', {}).get('media', []))
    return shape_feed(payload)


def write_feed(feed, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--sample', action='store_true', help='Write samples without network access')
    mode.add_argument('--fixture', type=Path, help='Shape a local X API JSON fixture without network access')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    token = os.environ.get('X_BEARER_TOKEN', '').strip()
    try:
        if args.fixture:
            feed = shape_feed(json.loads(args.fixture.read_text(encoding='utf-8')))
        elif args.sample or not token:
            feed = sample_feed()
            print('Sample feed enabled; no X API request made.')
        else:
            feed = fetch_feed(token)
        write_feed(feed, args.output)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError) as error:
        # Never log API response bodies, request headers, tokens, or post text.
        print(f'X feed update failed ({type(error).__name__}); existing data left unchanged.')
        return 1
    print(f'Wrote {len(feed["posts"])} public feed cards (sample={feed["sample"]}).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
