#!/usr/bin/env python3
"""Dependency-free HTML, internal-link, metadata and asset checks. No build step."""
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1] / 'public'
ORIGIN = 'https://matiashaderspock.com'
VOID = set('area base br col embed hr img input link meta param source track wbr'.split())
errors = []


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.path, self.stack, self.ids, self.refs = path, [], set(), []
        self.meta, self.alternates, self.languages = {}, {}, []
        self.canonical, self.h1, self.main, self.title, self.doctype = [], 0, 0, '', False
        self.source = path.read_text(encoding='utf-8')
        self.feed(self.source)
        self.close()
        if self.stack:
            self.fail(f'unclosed tags: {self.stack}')

    def fail(self, message):
        errors.append(f'{self.path.relative_to(ROOT)}:{self.getpos()[0]}: {message}')

    def handle_decl(self, decl):
        self.doctype = decl.lower() == 'doctype html'

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in VOID:
            self.stack.append(tag)
        if 'id' in attrs:
            if attrs['id'] in self.ids:
                self.fail(f'duplicate id: {attrs["id"]}')
            self.ids.add(attrs['id'])
        if tag == 'html':
            self.languages.append(attrs.get('lang'))
        if tag == 'h1':
            self.h1 += 1
        if tag == 'main':
            self.main += 1
        if tag == 'img' and 'alt' not in attrs:
            self.fail('image missing alt text')
        if tag == 'a' and (not attrs.get('href') or attrs['href'] == '#'):
            self.fail('empty or placeholder link; supply a real URL or remove the link')
        if tag == 'meta':
            key = attrs.get('name', attrs.get('property'))
            if key:
                self.meta[key] = attrs.get('content', '')
        if tag == 'link':
            if attrs.get('rel') == 'canonical':
                self.canonical.append(attrs.get('href'))
            if attrs.get('rel') == 'alternate':
                self.alternates[attrs.get('hreflang')] = attrs.get('href')
        for attr in ('href', 'src'):
            if attrs.get(attr):
                self.refs.append(attrs[attr])
        if tag == 'meta' and attrs.get('property') == 'og:image':
            self.refs.append(attrs.get('content', ''))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.fail(f'unexpected closing tag: {tag}')

    def handle_data(self, data):
        if 'TODO' in data:
            self.fail('unfinished placeholder text')
        if self.stack and self.stack[-1] == 'title':
            self.title += data


def resolve(page, url):
    parsed = urlsplit(url)
    if parsed.netloc and parsed.netloc != urlsplit(ORIGIN).netloc:
        return None, None
    if parsed.scheme and parsed.scheme not in ('http', 'https'):
        return None, None
    path = unquote(parsed.path)
    target = ROOT / path.lstrip('/') if path.startswith('/') else page.parent / path if path else page
    target = target.resolve()
    if not target.is_relative_to(ROOT):
        errors.append(f'{page.relative_to(ROOT)}: link escapes public/: {url}')
        return None, None
    if target.is_dir():
        target /= 'index.html'
    elif not target.suffix and not target.exists():
        target = target.with_suffix('.html')  # Cloudflare clean HTML URLs
    return target, unquote(parsed.fragment)


for path in sorted(ROOT.rglob('*')):
    if path.is_file() and (path.suffix in {'.html', '.css', '.js', '.svg', '.xml', '.txt'} or path.name == '_headers'):
        if 'TODO' in path.read_text(encoding='utf-8'):
            errors.append(f'{path.relative_to(ROOT)}: unfinished placeholder text')

pages = {path.resolve(): Page(path.resolve()) for path in sorted(ROOT.rglob('*.html'))}
if not pages:
    errors.append('No HTML pages found')
for path, page in pages.items():
    expected_lang = 'es' if path.relative_to(ROOT).parts[0] == 'es' else 'en'
    if not page.doctype or page.languages != [expected_lang] or page.h1 != 1 or page.main != 1 or not page.title.strip():
        page.fail('expected doctype, correct html lang, one h1, one main and a title')
    for key in ('viewport', 'description', 'og:title', 'og:description', 'og:locale', 'og:image', 'og:image:alt', 'twitter:card'):
        if not page.meta.get(key):
            page.fail(f'missing metadata: {key}')
    if len(page.canonical) != 1 or page.meta.get('og:url') != page.canonical[0]:
        page.fail('canonical URL and og:url must agree')
    if set(page.alternates) != {'en', 'es', 'x-default'}:
        page.fail('expected English, Spanish and x-default hreflang links')
    for lang, url in page.alternates.items():
        target, _ = resolve(path, url)
        if target in pages and lang in ('en', 'es') and pages[target].languages != [lang]:
            page.fail(f'hreflang {lang} points to wrong language')
        if target in pages and pages[target].alternates != page.alternates:
            page.fail('hreflang links must be reciprocal')
    for url in page.refs:
        target, fragment = resolve(path, url)
        if target is None:
            continue
        if not target.is_file():
            page.fail(f'missing local target: {url}')
        elif fragment and target in pages and fragment not in pages[target].ids:
            page.fail(f'missing fragment in {url}')
    if path.name == '404.html' and page.meta.get('robots') != 'noindex, follow':
        page.fail('404 page must be noindex')

for css in ROOT.rglob('*.css'):
    for url in re.findall(r'url\([\'\"]?([^\)\'\"]+)', css.read_text(encoding='utf-8')):
        target, _ = resolve(css, url)
        if target and not target.is_file():
            errors.append(f'{css.name}: missing asset: {url}')

try:
    sitemap = ET.parse(ROOT / 'sitemap.xml')
    ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    locations = {element.text for element in sitemap.findall('.//s:loc', ns)}
    expected = {page.canonical[0] for page in pages.values() if page.path.name != '404.html'}
    if locations != expected:
        errors.append('Sitemap must list all indexable canonical URLs')
except (ET.ParseError, FileNotFoundError) as error:
    errors.append(f'Sitemap error: {error}')

js_bytes = sum(path.stat().st_size for path in ROOT.rglob('*.js'))
if js_bytes > 12_000:
    errors.append(f'JavaScript budget exceeded: {js_bytes} > 12000 bytes')

if errors:
    print('\n'.join(errors), file=sys.stderr)
    sys.exit(1)
print(f'PASS: {len(pages)} HTML pages, all local links/fragments, bilingual metadata, sitemap and assets.')
print(f'JavaScript: {js_bytes:,} bytes (budget: 12,000). External links are not fetched by CI.')
