#!/usr/bin/env python3
"""Génère cdf.html : les dernières parutions audio-vidéo du Collège de France.

Autonome : relit le flux RSS officiel, télécharge les vignettes (embarquées en
data URI car le CSP des artifacts bloque les images externes), résout les titres
de séries depuis les pages du site, et écrit cdf.html à côté de ce script.
Lancé par la tâche planifiée « cdf-audiovisuel-refresh » qui republie ensuite
l'artifact https://claude.ai/code/artifact/7b06793a-187a-4932-8037-f5837c9788f7
"""
import xml.etree.ElementTree as ET
import re, html, base64, os, sys, datetime
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FEED = 'https://www.college-de-france.fr/fr/audio-video-rss.xml'
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh) cdf-audiovisuel/1.0'}

KIND_LABELS = {
    'colloque': 'Colloque',
    'conferencier-invite': 'Conférencier invité',
    'cours': 'Cours',
    'seminaire': 'Séminaire',
    'lecon-inaugurale': 'Leçon inaugurale',
    'lecon-de-cloture': 'Leçon de clôture',
    'grand-evenement': 'Grand événement',
    'conference': 'Conférence',
    'symposium': 'Symposium',
}

MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
        'août', 'septembre', 'octobre', 'novembre', 'décembre']


def get(url, timeout=25):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def parse_feed(xml_bytes):
    items = []
    for it in ET.fromstring(xml_bytes).findall('.//item'):
        title = html.unescape((it.findtext('title') or '')).strip()
        link = it.findtext('link') or ''
        desc = it.findtext('description') or ''
        paras = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', p)).strip()
                 for p in re.findall(r'<p>(.*?)</p>', desc, re.S)]
        when, speaker, fmts = '', '', []
        if paras:
            m = re.search(r'du\s+(.+)$', paras[0])
            when = m.group(1) if m else paras[0]
        for p in paras[1:]:
            if p.startswith('Par '):
                speaker = p[4:].strip()
            elif p.startswith('Disponible au format'):
                if 'Audio' in p:
                    fmts.append('Audio')
                if 'Vidéo' in p:
                    fmts.append('Vidéo')
        thumbs = re.findall(
            r'https://www\.college-de-france\.fr/sites/default/files/styles/'
            r'16_9_audiovisual_s/[^\s"&]+\?h=[0-9a-f]+&amp;itok=[\w-]+', desc)
        parts = link.split('/')
        items.append(dict(
            title=title, link=link, when=when, speaker=speaker, fmts=fmts,
            thumb=thumbs[0].replace('&amp;', '&') if thumbs else None,
            kind=parts[5] if len(parts) > 6 else '',
            series=parts[6] if len(parts) > 7 else link,
        ))
    return items


def fetch_thumbs(items):
    cache = {}
    for o in items:
        u = o.pop('thumb')
        if u and u not in cache:
            try:
                cache[u] = 'data:image/jpeg;base64,' + base64.b64encode(get(u)).decode()
            except Exception as e:
                print(f'vignette KO ({e}): {u}', file=sys.stderr)
                cache[u] = None
        o['thumb_b64'] = cache.get(u)


def series_title(items_of_series):
    """Titre de la série : lu sur la page de l'événement, sinon slug embelli."""
    link = items_of_series[0]['link']
    url = link.rsplit('/', 1)[0]
    try:
        page = get(url).decode('utf-8', 'replace')
        m = (re.search(r'property="og:title"\s+content="([^"]+)"', page)
             or re.search(r'<title>([^<]+)</title>', page))
        if m:
            t = html.unescape(m.group(1))
            return re.sub(r'\s*[|–-]\s*Collège de France\s*$', '', t).strip()
    except Exception as e:
        print(f'titre de série KO ({e}): {url}', file=sys.stderr)
    return items_of_series[0]['series'].replace('-', ' ').capitalize()


def parse_when(w):
    m = re.match(r'(?:(\w+)\s+)?(\d{1,2}(?:er)?\s+\S+\s+\d{4}),?\s*(\d{2}:\d{2})?', w)
    if not m:
        return w, ''
    return m.group(2) or w, m.group(3) or ''


def sort_key(o):
    date, t = parse_when(o['when'])
    m = re.match(r'(\d{1,2})(?:er)?\s+(\S+)\s+(\d{4})', date or '')
    if not m:
        return (0, t)
    mois = m.group(2).lower()
    mnum = MOIS.index(mois) + 1 if mois in MOIS else 0
    return (int(m.group(3)) * 10000 + mnum * 100 + int(m.group(1)), t)


def font_b64(name):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        return None
    return base64.b64encode(open(p, 'rb').read()).decode()


def card(o):
    date, t = parse_when(o['when'])
    kind = KIND_LABELS.get(o['kind'], o['kind'].replace('-', ' ').capitalize())
    img = (f'<img src="{o["thumb_b64"]}" alt="" loading="lazy" width="388" height="218">'
           if o['thumb_b64'] else '<div class="noimg">Docet omnia</div>')
    fmts = ''.join(f'<span class="fmt">{f}</span>' for f in o['fmts'])
    return f'''<a class="card" href="{html.escape(o['link'])}" target="_blank" rel="noopener">
  <div class="thumb">{img}</div>
  <div class="card-body">
    <p class="meta"><span class="ktag">{html.escape(kind)}</span>{html.escape(date)}{('<span class="dot">·</span>' + t) if t else ''}</p>
    <h3>{html.escape(o['title'])}</h3>
    <p class="speaker">{html.escape(o['speaker'])}</p>
    <p class="foot">{fmts}<span class="go">Écouter / regarder<span class="arr">&nbsp;→</span></span></p>
  </div>
</a>'''


def build():
    items = parse_feed(get(FEED))
    fetch_thumbs(items)

    order, groups = [], {}
    for o in items:
        if o['series'] not in groups:
            groups[o['series']] = []
            order.append(o['series'])
        groups[o['series']].append(o)

    sections = []
    for s in order:
        g = sorted(groups[s], key=sort_key)
        kinds = []
        for o in g:
            k = KIND_LABELS.get(o['kind'], o['kind'])
            if k not in kinds:
                kinds.append(k)
        n = len(g)
        cards = '\n'.join(card(o) for o in g)
        sections.append(f'''<section>
  <header class="series">
    <p class="eyebrow">{html.escape(' & '.join(kinds))}<span class="count">{n} séance{'s' if n > 1 else ''}</span></p>
    <h2>{html.escape(series_title(g))}</h2>
  </header>
  <div class="grid">
{cards}
  </div>
</section>''')

    faces = []
    latin = font_b64('marcellus-latin.woff2')
    ext = font_b64('marcellus-latin-ext.woff2')
    if latin:
        faces.append(f'''@font-face {{
  font-family: 'Marcellus'; font-style: normal; font-weight: 400; font-display: swap;
  src: url(data:font/woff2;base64,{latin}) format('woff2');
  unicode-range: U+0000-00FF, U+2013-2014, U+2018-201A, U+201C-201E, U+2026, U+00A0;
}}''')
    if ext:
        faces.append(f'''@font-face {{
  font-family: 'Marcellus'; font-style: normal; font-weight: 400; font-display: swap;
  src: url(data:font/woff2;base64,{ext}) format('woff2');
  unicode-range: U+0100-02BA, U+1E00-1EFF, U+2113;
}}''')

    today = datetime.date.today()
    jour = f"{'1er' if today.day == 1 else today.day} {MOIS[today.month - 1]} {today.year}"

    head = f'''<meta charset="utf-8">
<title>Audiovisuel du Collège de France</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
{chr(10).join(faces)}
:root {{
  --paper: #f1f1ed;
  --panel: #fafaf7;
  --ink: #23241f;
  --ink-soft: #5c5d54;
  --line: #d4d4cb;
  --garnet: #7c2231;
  --garnet-ink: #7c2231;
  --bronze: #8a6a33;
  --thumb-bg: #e3e3da;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --paper: #181914;
    --panel: #1f201a;
    --ink: #e8e7de;
    --ink-soft: #a3a394;
    --line: #38392f;
    --garnet: #c96a77;
    --garnet-ink: #d98b96;
    --bronze: #c1a05e;
    --thumb-bg: #26271f;
  }}
}}
:root[data-theme="dark"] {{
  --paper: #181914;
  --panel: #1f201a;
  --ink: #e8e7de;
  --ink-soft: #a3a394;
  --line: #38392f;
  --garnet: #c96a77;
  --garnet-ink: #d98b96;
  --bronze: #c1a05e;
  --thumb-bg: #26271f;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}}
.wrap {{ max-width: 1060px; margin: 0 auto; padding: 0 24px 72px; }}
.masthead {{
  padding: 56px 0 36px;
  border-bottom: 3px double var(--line);
  text-align: center;
}}
.motto {{
  font-family: 'Marcellus', Georgia, serif;
  font-size: .8rem; letter-spacing: .38em; text-transform: uppercase;
  color: var(--bronze); margin: 0 0 14px;
}}
.masthead h1 {{
  font-family: 'Marcellus', Georgia, serif;
  font-weight: 400;
  font-size: clamp(1.9rem, 4.5vw, 3rem);
  margin: 0 0 12px;
  letter-spacing: .01em;
  text-wrap: balance;
}}
.masthead p.sub {{
  color: var(--ink-soft); margin: 0 auto; max-width: 58ch; font-size: .95rem;
}}
.masthead p.sub a {{ color: var(--garnet-ink); text-decoration-thickness: 1px; text-underline-offset: 3px; }}
section {{ margin-top: 52px; }}
.series {{ display: flex; flex-direction: column; gap: 4px; margin-bottom: 20px; }}
.eyebrow {{
  margin: 0;
  font-size: .72rem; letter-spacing: .22em; text-transform: uppercase;
  color: var(--garnet-ink); font-weight: 600;
  display: flex; align-items: baseline; gap: 12px;
}}
.count {{ color: var(--ink-soft); letter-spacing: .08em; font-weight: 400; font-variant-numeric: tabular-nums; }}
.series h2 {{
  font-family: 'Marcellus', Georgia, serif; font-weight: 400;
  font-size: clamp(1.25rem, 2.6vw, 1.7rem); margin: 0;
  text-wrap: balance;
  border-bottom: 1px solid var(--line); padding-bottom: 12px;
}}
.grid {{
  display: grid; gap: 18px;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
}}
.card {{
  display: flex; flex-direction: column;
  background: var(--panel);
  border: 1px solid var(--line);
  text-decoration: none; color: inherit;
  transition: border-color .15s ease, transform .15s ease;
}}
.card:hover, .card:focus-visible {{ border-color: var(--garnet); transform: translateY(-2px); }}
.card:focus-visible {{ outline: 2px solid var(--garnet); outline-offset: 2px; }}
@media (prefers-reduced-motion: reduce) {{
  .card, .card:hover {{ transition: none; transform: none; }}
}}
.thumb {{ aspect-ratio: 16/9; background: var(--thumb-bg); overflow: hidden; }}
.thumb img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.noimg {{
  display: flex; align-items: center; justify-content: center; height: 100%;
  font-family: 'Marcellus', Georgia, serif; color: var(--ink-soft);
  letter-spacing: .25em; text-transform: uppercase; font-size: .75rem;
}}
.card-body {{ display: flex; flex-direction: column; gap: 6px; padding: 14px 16px 16px; flex: 1; }}
.meta {{
  margin: 0; font-size: .72rem; letter-spacing: .12em; text-transform: uppercase;
  color: var(--bronze); font-variant-numeric: tabular-nums;
}}
.meta .dot {{ margin: 0 .45em; color: var(--line); }}
.ktag {{ color: var(--garnet-ink); margin-right: .8em; font-weight: 600; }}
.card h3 {{
  font-family: 'Marcellus', Georgia, serif; font-weight: 400;
  font-size: 1.02rem; line-height: 1.35; margin: 0;
  text-wrap: balance;
}}
.speaker {{ margin: 0; color: var(--ink-soft); font-size: .88rem; }}
.foot {{
  margin: auto 0 0; padding-top: 12px;
  display: flex; align-items: center; gap: 6px; font-size: .75rem;
}}
.fmt {{
  border: 1px solid var(--line); color: var(--ink-soft);
  padding: 1px 8px; letter-spacing: .06em;
}}
.go {{ margin-left: auto; color: var(--garnet-ink); font-weight: 600; letter-spacing: .04em; }}
.arr {{ display: inline-block; transition: transform .15s ease; }}
.card:hover .arr {{ transform: translateX(3px); }}
footer.colophon {{
  margin-top: 64px; padding-top: 20px; border-top: 3px double var(--line);
  color: var(--ink-soft); font-size: .8rem; text-align: center;
}}
footer.colophon a {{ color: var(--garnet-ink); }}
</style>'''

    body = f'''<div class="wrap">
  <header class="masthead">
    <p class="motto">Docet omnia · depuis 1530</p>
    <h1>Audiovisuel du Collège de France</h1>
    <p class="sub">Les {len(items)} dernières parutions audio et vidéo des cours, séminaires et colloques,
    d'après le <a href="https://www.college-de-france.fr/fr/audio-video-rss.xml" target="_blank" rel="noopener">flux RSS officiel</a>.
    Chaque séance est en accès libre sur college-de-france.fr.</p>
  </header>
{chr(10).join(sections)}
  <footer class="colophon">
    <p>Flux relevé le {jour}, mis à jour chaque matin ·
    <a href="https://www.college-de-france.fr/fr/audios-videos" target="_blank" rel="noopener">Toutes les ressources audiovisuelles</a></p>
  </footer>
</div>
'''
    # cdf.html : fragment pour l'artifact claude.ai (qui ajoute lui-même le squelette).
    # index.html : page complète autonome pour GitHub Pages.
    frag = os.path.join(HERE, 'cdf.html')
    open(frag, 'w').write(head + '\n' + body)
    standalone = os.path.join(HERE, 'index.html')
    open(standalone, 'w').write(
        f'<!doctype html>\n<html lang="fr">\n<head>\n{head}\n</head>\n<body>\n{body}</body>\n</html>\n')
    print(f'{frag} — {os.path.getsize(frag)} octets, {len(items)} séances, {len(order)} séries')
    print(f'{standalone} — {os.path.getsize(standalone)} octets')


if __name__ == '__main__':
    build()
