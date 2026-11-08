import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlparse

RSS_URL = "https://feeds.bbci.co.uk/sport/rss.xml"
MAX_STORIES = 12
MEDIA_NS = {"media": "http://search.yahoo.com/mrss/"}
FALLBACK_IMAGES = (
    "https://images.unsplash.com/photo-1522778119026-d647f0596c20?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1517649763962-0c623066013b?auto=format&fit=crop&w=1200&q=80",
)


def clean_text(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]*>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def safe_bbc_link(value):
    parsed = urlparse((value or "").strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "https" and (host == "bbc.com" or host.endswith(".bbc.com") or host == "bbc.co.uk" or host.endswith(".bbc.co.uk")):
        return parsed.geturl()
    return "https://www.bbc.com/sport"


def find_image(item, index):
    candidates = []
    for tag in ("thumbnail", "content"):
        candidates.extend(node.get("url", "") for node in item.findall(f"media:{tag}", MEDIA_NS))
    enclosure = item.find("enclosure")
    if enclosure is not None and enclosure.get("type", "").startswith("image/"):
        candidates.append(enclosure.get("url", ""))
    for candidate in candidates:
        parsed = urlparse(candidate)
        host = (parsed.hostname or "").lower()
        allowed = host.endswith("bbc.co.uk") or host.endswith("bbci.co.uk") or host.endswith("bbc.com")
        if parsed.scheme == "https" and allowed:
            return parsed.geturl()
    return FALLBACK_IMAGES[index % len(FALLBACK_IMAGES)]


def category_for(title, description):
    text = f"{title} {description}".lower()
    keywords = {
        "Football": ("football", "premier league", "champions league", "arsenal", "chelsea", "liverpool", "man city", "spurs"),
        "Tennis": ("tennis", "wimbledon", "atp", "wta"),
        "Formula 1": ("formula 1", "formula one", "f1", "grand prix"),
        "Cricket": ("cricket", "ashes", "test match", "t20"),
        "Rugby": ("rugby", "six nations"),
    }
    return next((name for name, terms in keywords.items() if any(term in text for term in terms)), "Other")


def render_story(item, index):
    title = clean_text(item.findtext("title"))
    if not title:
        return ""
    description = clean_text(item.findtext("description")) or "Read the full report from BBC Sport."
    link = safe_bbc_link(item.findtext("link"))
    image = find_image(item, index)
    category = category_for(title, description)
    try:
        published = datetime.strptime(item.findtext("pubDate", ""), "%a, %d %b %Y %H:%M:%S %z")
        date_label = published.astimezone(timezone.utc).strftime("%d %b %Y")
        iso_date = published.astimezone(timezone.utc).isoformat()
    except ValueError:
        date_label, iso_date = "Latest", ""

    return f'''<article class="story-card" data-category="{html.escape(category, quote=True)}">
      <a class="story-image" href="{html.escape(link, quote=True)}" target="_blank" rel="noopener noreferrer" tabindex="-1" aria-hidden="true">
        <img src="{html.escape(image, quote=True)}" alt="" loading="lazy">
        <span class="category">{html.escape(category)}</span>
      </a>
      <div class="story-body">
        <div class="story-meta"><span>BBC SPORT</span><time datetime="{html.escape(iso_date, quote=True)}">{html.escape(date_label)}</time>
          <button class="save-button" type="button" aria-label="Save story" title="Save story">♡</button></div>
        <h2><a href="{html.escape(link, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(title)}</a></h2>
        <p>{html.escape(description)}</p>
        <a class="read-more" href="{html.escape(link, quote=True)}" target="_blank" rel="noopener noreferrer">Read story <span aria-hidden="true">↗</span></a>
      </div>
    </article>'''


def fetch_stories():
    request = urllib.request.Request(RSS_URL, headers={"User-Agent": "Skysport/1.0 (+https://github.com/aslaykii/skysport)"})
    with urllib.request.urlopen(request, timeout=20) as response:
        root = ET.fromstring(response.read())
    stories = [render_story(item, index) for index, item in enumerate(root.findall("./channel/item"))]
    stories = [story for story in stories if story][:MAX_STORIES]
    if not stories:
        raise ValueError("The RSS feed did not contain usable stories")
    return "\n".join(stories)


def build_page(stories, updated):
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="The latest global sports headlines, photos and reports from BBC Sport.">
  <meta name="theme-color" content="#091321">
  <title>Skysport — Global Sports News</title>
  <style>
    :root {{ color-scheme:dark; --bg:#091321; --surface:#111f32; --surface2:#172941; --text:#f4f7fc; --muted:#a9b7ca; --accent:#ff493d; --line:#ffffff16; }}
    :root.light {{ color-scheme:light; --bg:#f3f6fb; --surface:#fff; --surface2:#e8eef7; --text:#162238; --muted:#5e6d82; --line:#1327471a; }}
    * {{ box-sizing:border-box; }} html {{ scroll-behavior:smooth; }} body {{ margin:0; background:var(--bg); color:var(--text); font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif; }}
    a {{ color:inherit; }} button,input {{ font:inherit; }} .wrap {{ width:min(1160px,calc(100% - 36px)); margin:auto; }}
    .masthead {{ background:linear-gradient(90deg,#081321f2,#091321aa),url("https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=2000&q=80") center 48%/cover; border-bottom:1px solid var(--line); }}
    .nav {{ min-height:76px; display:flex; align-items:center; justify-content:space-between; gap:20px; }} .brand {{ display:flex; align-items:center; gap:12px; text-decoration:none; }} .brand-mark {{ display:grid; place-items:center; width:42px; height:42px; border-radius:12px; background:linear-gradient(135deg,var(--accent),#ff8b42); font-weight:900; font-size:22px; }} .brand-name {{ color:#fff; font-weight:850; letter-spacing:.12em; text-transform:uppercase; font-size:1.2rem; }}
    .nav-right {{ display:flex; align-items:center; gap:14px; }} .live {{ color:#e4ffec; font-size:.75rem; font-weight:750; letter-spacing:.09em; text-transform:uppercase; }} .live:before {{ content:""; display:inline-block; width:8px; height:8px; margin-right:8px; border-radius:50%; background:#4ade80; }} .theme-button {{ width:40px; height:40px; border:1px solid #ffffff50; border-radius:50%; color:white; background:#07101d75; cursor:pointer; }}
    .hero {{ padding:58px 0 64px; color:#fff; }} .eyebrow {{ color:#ffbcb6; text-transform:uppercase; letter-spacing:.17em; font-weight:800; font-size:.74rem; }} .hero h1 {{ max-width:790px; margin:12px 0; font-size:clamp(2.4rem,6vw,4.7rem); line-height:1.02; letter-spacing:-.05em; }} .hero p {{ max-width:630px; margin:0; color:#d5deeb; font-size:1.05rem; }}
    .ticker {{ background:var(--accent); color:#fff; }} .ticker .wrap {{ min-height:40px; display:flex; align-items:center; gap:12px; font-size:.8rem; font-weight:750; }} .ticker-label {{ border:1px solid #ffffff75; padding:2px 8px; border-radius:4px; font-size:.68rem; letter-spacing:.08em; }}
    .section-head {{ display:flex; align-items:end; justify-content:space-between; gap:18px; flex-wrap:wrap; padding:30px 0 15px; }} .section-head h2 {{ margin:0; font-size:1.55rem; }} .section-head p {{ margin:3px 0 0; color:var(--muted); font-size:.83rem; }} .search {{ width:min(320px,100%); padding:11px 14px; color:var(--text); background:var(--surface); border:1px solid var(--line); border-radius:10px; outline:none; }} .search:focus {{ border-color:var(--accent); box-shadow:0 0 0 3px #ff493d25; }}
    .filters {{ display:flex; gap:8px; overflow-x:auto; padding:0 0 20px; }} .filter {{ flex:none; border:1px solid var(--line); border-radius:999px; padding:8px 14px; color:var(--muted); background:var(--surface); font-size:.84rem; font-weight:650; cursor:pointer; }} .filter:hover,.filter.active {{ color:var(--text); border-color:#ff493d88; background:#ff493d1c; }}
    .news-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:19px; padding-bottom:44px; }} .story-card {{ overflow:hidden; background:var(--surface); border:1px solid var(--line); border-radius:16px; box-shadow:0 12px 32px #00000018; transition:transform .2s,border-color .2s; }} .story-card:hover {{ transform:translateY(-3px); border-color:#ff493d70; }} .story-image {{ display:block; position:relative; aspect-ratio:16/9; overflow:hidden; background:var(--surface2); }} .story-image img {{ width:100%; height:100%; display:block; object-fit:cover; transition:transform .35s; }} .story-card:hover .story-image img {{ transform:scale(1.035); }} .category {{ position:absolute; left:12px; bottom:12px; padding:5px 9px; border-radius:6px; background:var(--accent); color:white; font-size:.69rem; font-weight:800; text-transform:uppercase; }} .story-body {{ padding:16px 17px 18px; }} .story-meta {{ display:flex; align-items:center; gap:10px; color:#ff796f; font-size:.67rem; letter-spacing:.08em; font-weight:800; }} .story-meta time {{ margin-left:auto; color:var(--muted); letter-spacing:0; font-weight:500; }} .save-button {{ border:0; padding:0 2px; color:var(--muted); background:transparent; font-size:1.4rem; line-height:1; cursor:pointer; }} .save-button.saved,.save-button:hover {{ color:var(--accent); }} .story-body h2 {{ margin:12px 0 8px; font-size:1.13rem; line-height:1.4; }} .story-body h2 a {{ text-decoration:none; }} .story-body h2 a:hover {{ color:#ff796f; }} .story-body p {{ margin:0; color:var(--muted); font-size:.89rem; line-height:1.65; }} .read-more {{ display:inline-block; margin-top:13px; color:#ff796f; font-size:.83rem; font-weight:750; text-decoration:none; }} .read-more:hover {{ text-decoration:underline; }} .empty-state {{ grid-column:1/-1; padding:35px; text-align:center; color:var(--muted); border:1px dashed var(--line); border-radius:14px; }} [hidden] {{ display:none!important; }}
    footer {{ border-top:1px solid var(--line); padding:22px 0 32px; color:var(--muted); font-size:.82rem; text-align:center; }}
    @media(max-width:900px) {{ .news-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }}
    @media(max-width:600px) {{ .wrap {{ width:min(100% - 28px,1160px); }} .nav {{ min-height:66px; }} .live {{ display:none; }} .hero {{ padding:43px 0 48px; }} .section-head {{ align-items:stretch; }} .search {{ width:100%; }} .news-grid {{ grid-template-columns:1fr; gap:14px; }} .story-card {{ display:grid; grid-template-columns:112px minmax(0,1fr); }} .story-image {{ height:100%; min-height:165px; aspect-ratio:auto; }} .story-body {{ padding:12px; }} .story-body h2 {{ font-size:.98rem; margin:9px 0 6px; }} .story-body p {{ font-size:.8rem; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }} .read-more {{ margin-top:8px; }} .story-meta {{ font-size:.59rem; gap:6px; }} }}
    @media(prefers-reduced-motion:reduce) {{ *,*::before,*::after {{ scroll-behavior:auto!important; transition:none!important; }} }}
  </style>
</head>
<body>
  <header class="masthead"><div class="wrap"><nav class="nav" aria-label="Main navigation"><a class="brand" href="#top"><span class="brand-mark" aria-hidden="true">S</span><span class="brand-name">Skysport</span></a><div class="nav-right"><span class="live">Sports desk</span><button class="theme-button" id="theme-toggle" type="button" aria-label="Switch to light theme" title="Switch theme">☼</button></div></nav>
    <section class="hero" id="top"><span class="eyebrow">The global sports desk</span><h1>Every moment.<br>Every sport.</h1><p>Match-day drama, big stories and the latest headlines from across the sporting world.</p></section></div></header>
  <div class="ticker"><div class="wrap"><span class="ticker-label">SPORTS NEWS</span><span>Fresh headlines from BBC Sport · Football · Tennis · Formula 1 · Rugby · Cricket</span></div></div>
  <main class="wrap"><section class="section-head"><div><h2>Latest headlines</h2><p>Updated {html.escape(updated)} · News source: BBC Sport</p></div><input class="search" id="search" type="search" placeholder="Search headlines…" aria-label="Search headlines"></section>
    <nav class="filters" aria-label="Filter by sport"><button class="filter active" type="button" data-filter="All">All sports</button><button class="filter" type="button" data-filter="Football">Football</button><button class="filter" type="button" data-filter="Tennis">Tennis</button><button class="filter" type="button" data-filter="Formula 1">Formula 1</button><button class="filter" type="button" data-filter="Rugby">Rugby</button><button class="filter" type="button" data-filter="Cricket">Cricket</button><button class="filter" type="button" data-filter="Other">Other</button><button class="filter" type="button" data-filter="Saved">♡ Saved</button></nav>
    <div class="news-grid" id="news-grid">{stories}<p class="empty-state" id="empty-state" hidden>No stories found. Try a different search or filter.</p></div>
  </main>
  <footer><div class="wrap">Skysport · Headlines and story links provided by BBC Sport RSS</div></footer>
  <script>
    (() => {{
      const filters = [...document.querySelectorAll('.filter')];
      const cards = [...document.querySelectorAll('.story-card')];
      const search = document.getElementById('search');
      const empty = document.getElementById('empty-state');
      const themeButton = document.getElementById('theme-toggle');
      let selected = 'All';
      let saved = new Set();
      try {{ saved = new Set(JSON.parse(localStorage.getItem('skysport-saved') || '[]')); }} catch {{ saved = new Set(); }}
      const storyKey = card => card.querySelector('h2')?.textContent.trim() || '';
      function updateSavedButton(card) {{
        const button = card.querySelector('.save-button');
        if (!button) return;
        const isSaved = saved.has(storyKey(card));
        button.classList.toggle('saved', isSaved);
        button.textContent = isSaved ? '♥' : '♡';
        button.setAttribute('aria-label', isSaved ? 'Remove saved story' : 'Save story');
      }}
      cards.forEach(card => {{
        updateSavedButton(card);
        card.querySelector('.save-button')?.addEventListener('click', () => {{
          const key = storyKey(card);
          saved.has(key) ? saved.delete(key) : saved.add(key);
          try {{ localStorage.setItem('skysport-saved', JSON.stringify([...saved])); }} catch {{}}
          updateSavedButton(card);
          updateCards();
        }});
      }});
      function updateCards() {{
        const query = search.value.trim().toLocaleLowerCase();
        let count = 0;
        cards.forEach(card => {{
          const categoryMatch = selected === 'All' || (selected === 'Saved' ? saved.has(storyKey(card)) : card.dataset.category === selected);
          card.hidden = !(categoryMatch && card.textContent.toLocaleLowerCase().includes(query));
          if (!card.hidden) count++;
        }});
        empty.hidden = count > 0;
      }}
      filters.forEach(button => button.addEventListener('click', () => {{
        filters.forEach(item => item.classList.toggle('active', item === button));
        selected = button.dataset.filter;
        updateCards();
      }}));
      search.addEventListener('input', updateCards);
      try {{ if (localStorage.getItem('skysport-theme') === 'light') document.documentElement.classList.add('light'); }} catch {{}}
      themeButton.addEventListener('click', () => {{
        const light = document.documentElement.classList.toggle('light');
        themeButton.setAttribute('aria-label', light ? 'Switch to dark theme' : 'Switch to light theme');
        try {{ localStorage.setItem('skysport-theme', light ? 'light' : 'dark'); }} catch {{}}
      }});
    }})();
  </script>
</body>
</html>'''


def main():
    try:
        stories = fetch_stories()
        print("Fetched the latest BBC Sport RSS headlines.")
    except (OSError, ET.ParseError, ValueError) as error:
        print(f"RSS update failed; keeping existing page if available: {error}")
        try:
            with open("index.html", encoding="utf-8") as existing:
                current = existing.read()
            if "<article class=\"story-card\"" in current:
                return
        except OSError:
            pass
        stories = '''<article class="story-card"><div class="story-body"><span class="story-meta">BBC SPORT</span><h2>Headlines are temporarily unavailable</h2><p>Please try again later. The automatic updater will retry on its next run.</p></div></article>'''
    updated = datetime.now(timezone.utc).strftime("%d %b %Y · %H:%M UTC")
    with open("index.html", "w", encoding="utf-8") as page:
        page.write(build_page(stories, updated))
    print("Generated Skysport page successfully.")


if __name__ == "__main__":
    main()
