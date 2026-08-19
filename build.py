#!/usr/bin/env python3
"""Génère la page « Audiovisuel du Collège de France ».

Autonome : relit le flux RSS officiel des séances et les flux des 8 chaînes
YouTube du Collège, classe chaque parution dans son domaine thématique
(taxonomie « area » des chaires du site), télécharge les vignettes (embarquées
en data URI car le CSP des artifacts bloque les images externes), et écrit à
côté de ce script :
  - index.html : page complète autonome, déployée sur GitHub Pages ;
  - cdf.html   : le même contenu en fragment, pour l'artifact claude.ai
                 https://claude.ai/code/artifact/7b06793a-187a-4932-8037-f5837c9788f7

La page est un fil unique de cartes par thème : séances du site et vidéos
YouTube mélangées, triées par date décroissante, badge de provenance sur
chaque carte.
"""
import xml.etree.ElementTree as ET
import re, html, base64, os, sys, time, datetime
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = 'https://www.college-de-france.fr'
FEED = SITE + '/fr/audio-video-rss.xml'
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

AUTRES = 'Autres enseignements'
GENERALE = 'Collège de France'

# Les 8 chaînes YouTube du Collège (une par domaine + la chaîne générale),
# listées sur /fr/le-college/diffusion-numerique-des-savoirs
YT_CHANNELS = [
    'UCzZiy3EANVAx7h2XYqXsVbw',  # Collège de France (générale)
    'UCQHCy-zCD-luzeNQiSc_4Mg',  # Histoire et archéologie
    'UCyZnBE2D98VgMqTgIFksX9g',  # Sciences sociales
    'UCedamoEQgcR4kF_l_Zgipqg',  # Lettres, langage, philosophie
    'UCENYlRe2MNqSsK38QYG4W4Q',  # Physique et chimie
    'UCdhpyHOyliFNArgEaO6dAqw',  # Sciences de la vie
    'UCk58LsWC9j892FUMBwN5AsQ',  # Mathématiques et informatique
    'UCZzYTanB9FqpERKdmG3ja8A',  # Sciences de l'Univers
]
YT_PER_CHANNEL = 6


def get(url, timeout=25, tries=3):
    for i in range(tries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=timeout).read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))
    raise RuntimeError('unreachable')


def slugify(s):
    s = re.sub(r'[^a-z0-9]+', '-', s.lower()
               .translate(str.maketrans('àâäéèêëîïôöùûüç', 'aaaeeeeiioouuuc')))
    return s.strip('-') or 'autres'


def parse_feed(xml_bytes):
    items = []
    for it in ET.fromstring(xml_bytes).findall('.//item'):
        title = html.unescape((it.findtext('title') or '')).strip()
        link = it.findtext('link') or ''
        desc = it.findtext('description') or ''
        paras = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', p)).strip()
                 for p in re.findall(r'<p>(.*?)</p>', desc, re.S)]
        when, speaker = '', ''
        if paras:
            m = re.search(r'du\s+(.+)$', paras[0])
            when = m.group(1) if m else paras[0]
        for p in paras[1:]:
            if p.startswith('Par '):
                speaker = p[4:].strip()
        thumbs = re.findall(
            r'https://www\.college-de-france\.fr/sites/default/files/styles/'
            r'16_9_audiovisual_s/[^\s"&]+\?h=[0-9a-f]+&amp;itok=[\w-]+', desc)
        parts = link.split('/')
        items.append(dict(
            title=title, link=link, when=when, speaker=speaker,
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


def parse_channel(cid):
    """Chaîne YouTube : nom, domaine (= nom sans le suffixe) et dernières vidéos."""
    ns = {'a': 'http://www.w3.org/2005/Atom', 'media': 'http://search.yahoo.com/mrss/'}
    root = ET.fromstring(get(f'https://www.youtube.com/feeds/videos.xml?channel_id={cid}'))
    name = root.findtext('a:title', default='', namespaces=ns).strip()
    area = re.sub(r'\s*-\s*Collège de France\s*$', '', name).strip() or GENERALE
    videos = []
    for e in root.findall('a:entry', ns):
        m = e.find('media:group', ns)
        thumb = m.find('media:thumbnail', ns) if m is not None else None
        stats = m.find('media:community/media:statistics', ns) if m is not None else None
        link = e.find("a:link[@rel='alternate']", ns)
        views = stats.get('views') if stats is not None else None
        videos.append(dict(
            title=(e.findtext('a:title', default='', namespaces=ns)).strip(),
            link=link.get('href') if link is not None else '',
            published=e.findtext('a:published', default='', namespaces=ns),
            thumb=thumb.get('url') if thumb is not None else None,
            views=int(views) if views else None,
        ))
    return dict(name=name, area=area,
                url=f'https://www.youtube.com/channel/{cid}', videos=videos)


def yt_split(title):
    """« Titre (21) - Edouard Bard (2025-2026) » → (« Titre », « Edouard Bard », 21).

    Gère aussi « Titre - Jean-Jacques Hublin » et « Titre (5) - 2026 ».
    """
    t, speaker = title.strip(), ''
    m = re.match(r'(.+)\s-\s(.+?)\s*\(\d{4}(?:-\d{4})?\)$', t)
    if m:
        t, speaker = m.group(1).strip(), m.group(2).strip()
    elif (m := re.match(r'(.+)\s-\s\d{4}$', t)):
        t = m.group(1).strip()
    elif (m := re.match(r'(.+)\s-\s([A-ZÀ-Ý][^,;:0-9]*)$', t)) and len(m.group(2).split()) <= 4:
        t, speaker = m.group(1).strip(), m.group(2).strip()
    num = None
    if (m := re.search(r'\((\d{1,3})\)\s*$', t)):
        num = int(m.group(1))
        t = t[:m.start()].strip()
    return re.sub(r'\.{3}\s*$', '…', t), speaker, num


def norm_title(s):
    s = s.lower().translate(str.maketrans('àâäéèêëîïôöùûüç', 'aaaeeeeiioouuuc'))
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def fr_date(y, m, d):
    return f"{'1er' if d == 1 else d} {MOIS[m - 1]} {y}"


def yt_views(n):
    if n is None:
        return ''
    if n >= 1_000_000:
        s = f'{n / 1_000_000:.1f}'.rstrip('0').rstrip('.')
        return s.replace('.', ',') + ' M de vues'
    if n >= 1000:
        return f'{n:,}'.replace(',', ' ') + ' vues'
    return f'{n} vues'


_chaire_cache = {}


def chaire_area(path):
    """Domaine (label, couleur) d'une chaire, d'après la taxonomie du site."""
    if path not in _chaire_cache:
        area = None
        try:
            h = get(SITE + path).decode('utf-8', 'replace')
            m = re.search(r'area-label__label">([^<]+)<', h)
            if m:
                c = re.search(r'area-label__color"\s+style="--color:\s*(#[0-9a-fA-F]{3,8})', h)
                area = (html.unescape(m.group(1)).strip(), c.group(1) if c else None)
        except Exception as e:
            print(f'chaire KO ({e}): {path}', file=sys.stderr)
        _chaire_cache[path] = area
    return _chaire_cache[path]


def series_meta(g):
    """Titre, domaine et couleur d'une série, lus sur la page de l'événement."""
    url = g[0]['link'].rsplit('/', 1)[0]
    title = g[0]['series'].replace('-', ' ').capitalize()
    area, color = AUTRES, None
    try:
        page = get(url).decode('utf-8', 'replace')
        m = (re.search(r'property="og:title"\s+content="([^"]+)"', page)
             or re.search(r'<title>([^<]+)</title>', page))
        if m:
            title = re.sub(r'\s*[|–-]\s*Collège de France\s*$',
                           '', html.unescape(m.group(1))).strip()
        for path in dict.fromkeys(re.findall(r'/fr/chaire/[\w-]+', page)):
            found = chaire_area(path)
            if found:
                area, color = found
                break
    except Exception as e:
        print(f'série KO ({e}): {url}', file=sys.stderr)
    return dict(title=title, area=area, color=color)


def site_date(when):
    """« Vendredi 26 juin 2026, 06:15 - 06:30 » → (clé de tri, « 26 juin 2026 »)."""
    m = re.search(r'(\d{1,2})(?:er)?\s+(\S+)\s+(\d{4})', when or '')
    if not m:
        return 0, when
    d, mois, y = int(m.group(1)), m.group(2).lower(), int(m.group(3))
    mnum = MOIS.index(mois) + 1 if mois in MOIS else 0
    return y * 10000 + mnum * 100 + d, fr_date(y, mnum, d) if mnum else when


def font_b64(name):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        return None
    return base64.b64encode(open(p, 'rb').read()).decode()


def card(e):
    img = (f'<img src="{e["thumb_b64"]}" alt="" loading="lazy" width="480" height="270">'
           if e.get('thumb_b64') else '<div class="noimg">Docet omnia</div>')
    extra = f'<span class="dot">·</span>{e["extra"]}' if e['extra'] else ''
    who = html.escape(' · '.join(x for x in (e['who'], e['context']) if x))
    return f'''<a class="card" href="{html.escape(e['link'])}" target="_blank" rel="noopener">
  <div class="thumb">{img}</div>
  <div class="card-body">
    <p class="meta"><span class="ktag{' is-yt' if e['yt'] else ''}">{html.escape(e['kind'])}</span>{e['date']}{extra}</p>
    <h3>{html.escape(e['title'])}</h3>
    <p class="who" title="{who}">{who}</p>
    <p class="foot"><span class="go">{'Regarder sur YouTube' if e['yt'] else 'Écouter / regarder'}<span class="arr">&nbsp;→</span></span></p>
  </div>
</a>'''


def build():
    items = parse_feed(get(FEED))
    if not items:
        sys.exit('flux du site vide : on ne remplace pas la page existante')
    fetch_thumbs(items)

    channels = []
    for cid in YT_CHANNELS:
        try:
            channels.append(parse_channel(cid))
        except Exception as e:
            print(f'chaîne YouTube KO ({e}): {cid}', file=sys.stderr)
    # YouTube bloque les IP de datacenter (404 systématique depuis GitHub
    # Actions) : un build sans aucune chaîne est dégradé, on abandonne plutôt
    # que d'écraser une bonne version
    if not channels:
        sys.exit('aucune chaîne YouTube récupérée : build abandonné')

    order, groups = [], {}
    for o in items:
        if o['series'] not in groups:
            groups[o['series']] = []
            order.append(o['series'])
        groups[o['series']].append(o)
    metas = {s: series_meta(groups[s]) for s in order}

    # un seul fil d'entrées par domaine : séances du site + vidéos YouTube
    areas = {}

    def area_info(a):
        return areas.setdefault(a, dict(entries=[], color=None))

    for s in order:
        meta = metas[s]
        info = area_info(meta['area'])
        info['color'] = info['color'] or meta['color']
        for o in groups[s]:
            key, date = site_date(o['when'])
            info['entries'].append(dict(
                key=key, yt=False, date=date,
                kind=KIND_LABELS.get(o['kind'], o['kind'].replace('-', ' ').capitalize()),
                title=o['title'], who=o['speaker'], context=meta['title'],
                extra='', link=o['link'], thumb_b64=o['thumb_b64'],
            ))
    # doublons : les chaînes thématiques republient les séances du site sous un
    # titre générique « Série (N) - Titulaire (2025-2026) » ; si la série est
    # déjà présente via le flux du site, sa vidéo YouTube n'apporte rien
    site_titles = [norm_title(metas[s]['title']) for s in order]

    def is_dup(yt_title):
        n = norm_title(yt_title)
        return len(n) >= 12 and any(st.startswith(n) or n.startswith(st)
                                    for st in site_titles)

    nvid = 0
    for ch in channels:
        info = area_info(ch['area'])
        kept = 0
        for v in ch['videos']:
            if kept >= YT_PER_CHANNEL:
                break
            t, who, num = yt_split(v['title'])
            if is_dup(t):
                continue
            kept += 1
            m = re.match(r'(\d{4})-(\d{2})-(\d{2})', v['published'] or '')
            key, date = 0, ''
            if m:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                key, date = y * 10000 + mo * 100 + d, fr_date(y, mo, d)
            who_parts = [x for x in (who, f'séance {num}' if num else '') if x]
            info['entries'].append(dict(
                key=key, yt=True, date=date, kind='YouTube',
                title=t, who=' · '.join(who_parts) or ch['name'], context='',
                extra=yt_views(v['views']), link=v['link'], thumb=v['thumb'],
            ))
        nvid += kept
    fetch_thumbs([e for e in
                  (x for a in areas.values() for x in a['entries']) if 'thumb' in e])

    # domaines triés par volume, « Autres » puis la chaîne générale en dernier
    area_order = sorted(areas, key=lambda a: (a == GENERALE, a == AUTRES,
                                              -len(areas[a]['entries'])))
    total = len(items) + nvid

    chips, sections = [], []
    chips.append(f'<button class="chip is-active" data-area="*" aria-pressed="true">'
                 f'Tout<span class="n">{total}</span></button>')
    for a in area_order:
        info = areas[a]
        n = len(info['entries'])
        slug = slugify(a)
        dot = (f'<span class="adot" style="--c:{info["color"]}"></span>'
               if info['color'] else '<span class="adot"></span>')
        chips.append(f'<button class="chip" data-area="{slug}" aria-pressed="false">'
                     f'{dot}{html.escape(a)}<span class="n">{n}</span></button>')
        cards = '\n'.join(card(e) for e in
                          sorted(info['entries'], key=lambda e: -e['key']))
        sections.append(f'''<section class="theme-group" id="theme-{slug}" data-area="{slug}">
  <h2 class="theme-head">{dot}{html.escape(a)}<span class="count">{n} parution{'s' if n > 1 else ''}</span></h2>
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
    jour = fr_date(today.year, today.month, today.day)

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
  padding: 56px 0 32px;
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
.themes {{
  position: sticky; top: 0; z-index: 10;
  background: var(--paper);
  border-top: 3px double var(--line);
  border-bottom: 1px solid var(--line);
  padding: 10px 0;
  display: flex; flex-wrap: wrap; gap: 8px; justify-content: center;
}}
.chip {{
  font: inherit; font-size: .8rem;
  display: inline-flex; align-items: center; gap: 7px;
  background: var(--panel); color: var(--ink);
  border: 1px solid var(--line); border-radius: 999px;
  padding: 4px 14px; cursor: pointer;
}}
.chip:hover {{ border-color: var(--garnet); }}
.chip:focus-visible {{ outline: 2px solid var(--garnet); outline-offset: 2px; }}
.chip.is-active {{
  background: var(--ink); color: var(--paper); border-color: var(--ink);
}}
.chip .n {{
  font-size: .7rem; color: var(--ink-soft); font-variant-numeric: tabular-nums;
}}
.chip.is-active .n {{ color: var(--paper); opacity: .7; }}
.adot {{
  width: 9px; height: 9px; border-radius: 50%; flex: none;
  background: var(--c, var(--bronze));
}}
.theme-group {{ margin-top: 48px; }}
.theme-head {{
  font-family: 'Marcellus', Georgia, serif; font-weight: 400;
  font-size: clamp(1.4rem, 3vw, 1.9rem); margin: 0 0 20px;
  display: flex; align-items: center; gap: 12px;
  border-bottom: 1px solid var(--line); padding-bottom: 12px;
}}
.theme-head .adot {{ width: 12px; height: 12px; }}
.theme-head .count {{
  margin-left: auto; font-size: .78rem;
  letter-spacing: .1em; text-transform: uppercase; color: var(--ink-soft);
  font-variant-numeric: tabular-nums;
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
.ktag.is-yt {{ color: var(--ink-soft); }}
.card h3 {{
  font-family: 'Marcellus', Georgia, serif; font-weight: 400;
  font-size: 1.02rem; line-height: 1.35; margin: 0;
  text-wrap: balance;
}}
.who {{
  margin: 0; color: var(--ink-soft); font-size: .85rem;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.foot {{
  margin: auto 0 0; padding-top: 12px;
  display: flex; align-items: center; font-size: .75rem;
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
    <p class="sub">Les {total} dernières parutions du Collège, par thème et par date :
    séances des cours, séminaires et colloques
    (<a href="https://www.college-de-france.fr/fr/audio-video-rss.xml" target="_blank" rel="noopener">flux officiel</a>)
    et vidéos des <a href="https://www.college-de-france.fr/fr/le-college/diffusion-numerique-des-savoirs" target="_blank" rel="noopener">{len(channels)} chaînes YouTube</a>.
    Tout est en accès libre.</p>
  </header>
  <nav class="themes" aria-label="Filtrer par thème">
{chr(10).join(chips)}
  </nav>
{chr(10).join(sections)}
  <footer class="colophon">
    <p>Flux relevés le {jour}, mis à jour chaque matin ·
    <a href="https://www.college-de-france.fr/fr/audios-videos" target="_blank" rel="noopener">Toutes les ressources audiovisuelles</a></p>
  </footer>
</div>
<script>
(function () {{
  var chips = Array.prototype.slice.call(document.querySelectorAll('.chip'));
  var groups = Array.prototype.slice.call(document.querySelectorAll('.theme-group'));
  var calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  chips.forEach(function (c) {{
    c.addEventListener('click', function () {{
      chips.forEach(function (x) {{
        x.classList.toggle('is-active', x === c);
        x.setAttribute('aria-pressed', String(x === c));
      }});
      var a = c.dataset.area;
      groups.forEach(function (g) {{ g.hidden = (a !== '*' && g.dataset.area !== a); }});
      scrollTo({{ top: 0, behavior: calm ? 'auto' : 'smooth' }});
    }});
  }});
}})();
</script>
'''
    # cdf.html : fragment pour l'artifact claude.ai (qui ajoute lui-même le squelette).
    # index.html : page complète autonome pour GitHub Pages.
    frag = os.path.join(HERE, 'cdf.html')
    open(frag, 'w').write(head + '\n' + body)
    standalone = os.path.join(HERE, 'index.html')
    open(standalone, 'w').write(
        f'<!doctype html>\n<html lang="fr">\n<head>\n{head}\n</head>\n<body>\n{body}</body>\n</html>\n')
    themes = ', '.join(f'{a} ({len(areas[a]["entries"])})' for a in area_order)
    print(f'{frag} — {os.path.getsize(frag)} octets, {len(items)} séances, {len(order)} séries, '
          f'{nvid} vidéos YouTube ({len(channels)} chaînes)')
    print(f'thèmes : {themes}')


if __name__ == '__main__':
    build()
