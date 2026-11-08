import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlparse

RSS_URL = "https://feeds.bbci.co.uk/sport/rss.xml"
MAX_ITEMS = 12
IMAGE_FALLBACKS = [
    "https://images.unsplash.com/photo-1522778119026-d647f0596c20?auto=format&fit=crop&w=1200&q=85",
    "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1200&q=85",
    "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?auto=format&fit=crop&w=1200&q=85",
]
NS = {"media": "http://search.yahoo.com/mrss/"}


def clean_text(value):
    """Convert RSS markup to safe, readable plain text."""
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]*>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def safe_image_url(url):
    """Accept only secure image URLs from BBC or Unsplash."""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    allowed = host == "bbc.co.uk" or host.endswith(".bbc.co.uk") or host == "bbci.co.uk" or host.endswith(".bbci.co.uk") or host == "bbc.com" or host.endswith(".bbc.com") or host == "images.unsplash.com"
    return url.strip() if parsed.scheme == "https" and allowed else ""


def image_for(item, index):
    candidates = []
    for tag in ("thumbnail", "content"):
        for media in item.findall(f"media:{tag}", NS):
            candidates.append(media.attrib.get("url", ""))
    enclosure = item.find("enclosure")
    if enclosure is not None and "image" in enclosure.attrib.get("type", ""):
        candidates.append(enclosure.attrib.get("url", ""))

    # BBC sometimes embeds its image directly in the description HTML.
    description = item.findtext("description", default="")
    candidates.extend(re.findall(r'<img[^>]+src=[\"\']([^\"\']+)', description, flags=re.IGNORECASE))
    for candidate in candidates:
        safe_url = safe_image_url(candidate)
        if safe_url:
            return safe_url
    return IMAGE_FALLBACKS[index % len(IMAGE_FALLBACKS)]


def category_for(title, description):
    text = f"{title} {description}".lower()
    categories = {
        "Football": ("football", "premier league", "champions league", "fa cup", "goal", "arsenal", "chelsea", "liverpool", "man city", "united", "spurs"),
        "Tennis": ("tennis", "wimbledon", "atp", "wta", "grand slam"),
        "Formula 1": ("formula 1", "formula one", "f1", "grand prix"),
        "Rugby": ("rugby", "six nations", "premiership rugby"),
        "Cricket": ("cricket", "test match", "ashes", "odi", "t20"),
    }
    for category, terms in categories.items():
        if any(term in text for term in terms):
            return category
    return "More Sports"


def news_card(item, index):
    title = clean_text(item.findtext("title"))
    description = clean_text(item.findtext("description"))
    link = (item.findtext("link") or "").strip()
    pub_date = item.findtext("pubDate") or ""
    if not title:
        return ""

    parsed_link = urlparse(link)
    if parsed_link.scheme != "https" or not (parsed_link.hostname or "").lower().endswith(("bbc.com", "bbc.co.uk")):
        link = "https://www.bbc.com/sport"

    try:
        date = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %z")
        date_text = date.astimezone(timezone.utc).strftime("%d %b %Y")
    except ValueError:
        date_text = "Latest"

    category = category_for(title, description)
    image = image_for(item, index)
    return f'''<article class="news-card" data-category="{html.escape(category, quote=True)}">
      <a class="image-link" href="{html.escape(link, quote=True)}" target="_blank" rel="noopener noreferrer" tabindex="-1" aria-hidden="true">
        <img class="story-image" src="{html.escape(image, quote=True)}" alt="" loading="lazy" onerror="this.src='{IMAGE_FALLBACKS[index % len(IMAGE_FALLBACKS)]}'">
        <span class="image-badge">{html.escape(category)}</span>
      </a>
      <div class="story-content">
        <p class="meta">BBC SPORT <span>{html.escape(date_text)}</span></p>
        <h2><a href="{html.escape(link, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(title)}</a></h2>
        <p class="description">{html.escape(description or "Read the full story on BBC Sport.")}</p>
        <a class="read-more" href="{html.escape(link, quote=True)}" target="_blank" rel="noopener noreferrer">Read story <span aria-hidden="true">↗</span></a>
      </div>
    </article>'''


try:
    request = urllib.request.Request(RSS_URL, headers={"User-Agent": "SkysportNews/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        root = ET.fromstring(response.read())
    cards = [news_card(item, index) for index, item in enumerate(root.findall("./channel/item"))]
    cards = [card for card in cards if card][:MAX_ITEMS]
    if not cards:
        raise ValueError("RSS feed contained no usable stories")
    news_items_html = "\n".join(cards)
except (OSError, ET.ParseError, ValueError) as error:
    print(f"Could not update RSS news: {error}")
    news_items_html = '''<article class="news-card notice" data-category="More Sports"><div class="story-content"><h2>News temporarily unavailable</h2><p class="description">We couldn't load the latest headlines. Please check back soon.</p></div></article>'''

updated = datetime.now(timezone.utc).strftime("%d %b %Y at %H:%M UTC")
html_content = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="The latest global sports headlines, with photos and stories updated automatically.">
  <meta name="theme-color" content="#07101d">
  <title>Skysport | Global Sports News</title>
  <style>
    :root {{ color-scheme:dark; --bg:#07101d; --panel:#101d30; --text:#f4f7fc; --muted:#a9b5c9; --red:#ff3b30; --line:#ffffff16; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--text); font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif; }}
    a {{ color:inherit; }}
    .wrap {{ width:min(1160px,calc(100% - 40px)); margin:auto; }}
    header {{ position:relative; overflow:hidden; background:linear-gradient(90deg,rgba(5,12,23,.95),rgba(7,16,29,.68)),url("https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=2000&q=85") center 48%/cover; border-bottom:1px solid var(--line); }}
    .masthead {{ padding:22px 0; display:flex; align-items:center; justify-content:space-between; gap:20px; }}
    .brand {{ display:flex; align-items:center; gap:12px; text-decoration:none; }}
    .mark {{ display:grid; place-items:center; width:42px; height:42px; border-radius:12px; background:var(--red); font-size:23px; font-weight:900; box-shadow:0 8px 25px #ff3b3040; }}
    h1 {{ margin:0; font-size:1.55rem; letter-spacing:.11em; text-transform:uppercase; }}
    .live {{ color:#ffe2df; font-size:.8rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }}
    .live:before {{ content:""; display:inline-block; width:8px; height:8px; margin-right:8px; border-radius:50%; background:#4ade80; box-shadow:0 0 12px #4ade80; }}
    .hero {{ min-height:310px; display:flex; align-items:end; padding:45px 0 42px; }}
    .hero-copy {{ max-width:750px; text-shadow:0 2px 18px #000; }}
    .eyebrow {{ color:#ffb5af; font-size:.78rem; font-weight:800; letter-spacing:.18em; text-transform:uppercase; }}
    .hero h2 {{ margin:8px 0; font-size:clamp(2rem,6vw,4.1rem); line-height:1.06; letter-spacing:-.04em; }}
    .hero p {{ margin:0; max-width:600px; color:#d5dced; font-size:1.02rem; }}
    .toolbar {{ padding:26px 0 18px; display:flex; align-items:center; justify-content:space-between; gap:18px; flex-wrap:wrap; }}
    .toolbar h2 {{ margin:0; font-size:1.3rem; }}
    .updated {{ margin:3px 0 0; color:var(--muted); font-size:.83rem; }}
    .search {{ width:min(300px,100%); padding:11px 14px; color:var(--text); background:#101d30; border:1px solid var(--line); border-radius:10px; font:inherit; outline:none; }}
    .search:focus {{ border-color:var(--red); box-shadow:0 0 0 3px #ff3b3028; }}
    .filters {{ display:flex; gap:8px; overflow-x:auto; padding:0 0 20px; scrollbar-width:thin; }}
    .filter {{ flex:none; border:1px solid var(--line); border-radius:999px; padding:8px 14px; color:#cad4e5; background:#101d30; font:600 .85rem inherit; cursor:pointer; }}
    .filter.active,.filter:hover {{ color:#fff; border-color:#ff3b3080; background:#ff3b3026; }}
    main {{ padding-bottom:45px; }}
    .news-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:20px; }}
    .news-card {{ overflow:hidden; background:var(--panel); border:1px solid var(--line); border-radius:16px; box-shadow:0 12px 30px #0003; transition:transform .2s ease,border-color .2s ease; }}
    .news-card:hover {{ transform:translateY(-4px); border-color:#ffffff38; }}
    .image-link {{ position:relative; display:block; aspect-ratio:16/9; overflow:hidden; background:#17263d; }}
    .story-image {{ width:100%; height:100%; object-fit:cover; display:block; transition:transform .4s ease; }}
    .news-card:hover .story-image {{ transform:scale(1.04); }}
    .image-badge {{ position:absolute; left:13px; bottom:12px; padding:5px 9px; border-radius:6px; background:var(--red); color:#fff; font-size:.7rem; font-weight:800; letter-spacing:.06em; text-transform:uppercase; }}
    .story-content {{ padding:17px 18px 19px; }}
    .meta {{ display:flex; justify-content:space-between; gap:10px; margin:0 0 10px; color:#ffaaa3; font-size:.68rem; font-weight:800; letter-spacing:.1em; }}
    .meta span {{ color:var(--muted); font-weight:500; letter-spacing:normal; }}
    .news-card h2 {{ margin:0 0 9px; font-size:1.12rem; line-height:1.4; }}
    .news-card h2 a {{ text-decoration:none; }}
    .news-card h2 a:hover {{ color:#ffaaa3; }}
    .description {{ margin:0; color:var(--muted); font-size:.9rem; line-height:1.65; }}
    .read-more {{ display:inline-flex; gap:7px; margin-top:15px; color:#ff9e96; font-size:.83rem; font-weight:750; text-decoration:none; }}
    .notice {{ grid-column:1/-1; }}
    footer {{ border-top:1px solid var(--line); padding:25px 0 35px; color:var(--muted); text-align:center; font-size:.84rem; }}
    @media(max-width:900px) {{ .news-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }}
    @media(max-width:600px) {{ .wrap {{ width:min(100% - 28px,1160px); }} .masthead {{ padding:17px 0; }} .hero {{ min-height:260px; padding:35px 0; }} .news-grid {{ grid-template-columns:1fr; gap:15px; }} .toolbar {{ align-items:stretch; }} .search {{ width:100%; }} .news-card {{ display:grid; grid-template-columns:115px 1fr; }} .image-link {{ aspect-ratio:auto; min-height:100%; }} .story-content {{ padding:13px; }} .news-card h2 {{ font-size:1rem; }} .description {{ font-size:.82rem; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }} .meta {{ font-size:.62rem; }} .read-more {{ margin-top:10px; }} }}
    @media(prefers-reduced-motion:reduce) {{ *,*::before,*::after {{ scroll-behavior:auto!important; transition:none!important; }} }}
  </style>
</head>
<body>
  <header><div class="wrap">
    <nav class="masthead" aria-label="Main navigation"><a class="brand" href="#top"><span class="mark" aria-hidden="true">S</span><h1>Skysport</h1></a><span class="live">World of sport</span></nav>
    <section class="hero" id="top"><div class="hero-copy"><span class="eyebrow">The global sports desk</span><h2>Every moment.<br>Every sport.</h2><p>Big stories, match-day drama and the latest headlines from across the sporting world.</p></div></section>
  </div></header>
  <div class="wrap">
    <section class="toolbar" aria-label="News tools"><div><h2>Latest headlines</h2><p class="updated">Updated {html.escape(updated)} · Photos and stories from BBC Sport</p></div><input class="search" type="search" id="news-search" placeholder="Search headlines…" aria-label="Search headlines"></section>
    <nav class="filters" aria-label="Filter news by sport"><button class="filter active" data-filter="All" type="button">All sports</button><button class="filter" data-filter="Football" type="button">Football</button><button class="filter" data-filter="Tennis" type="button">Tennis</button><button class="filter" data-filter="Formula 1" type="button">Formula 1</button><button class="filter" data-filter="Rugby" type="button">Rugby</button><button class="filter" data-filter="Cricket" type="button">Cricket</button><button class="filter" data-filter="More Sports" type="button">More sports</button></nav>
    <main><div class="news-grid" id="news-grid">{news_items_html}</div></main>
  </div>
  <footer><div class="wrap">Skysport · Global sports news · Headlines provided by BBC Sport RSS</div></footer>
  <script>
    const buttons = document.querySelectorAll('.filter');
    const cards = [...document.querySelectorAll('.news-card')];
    const search = document.getElementById('news-search');
    let selected = 'All';
    function updateCards() {{
      const query = search.value.trim().toLowerCase();
      cards.forEach(card => {{
        const categoryMatch = selected === 'All' || card.dataset.category === selected;
        const textMatch = card.textContent.toLowerCase().includes(query);
        card.hidden = !(categoryMatch && textMatch);
      }});
    }}
    buttons.forEach(button => button.addEventListener('click', () => {{
      buttons.forEach(item => item.classList.remove('active'));
      button.classList.add('active');
      selected = button.dataset.filter;
      updateCards();
    }}));
    search.addEventListener('input', updateCards);
  </script>
</body>
</html>
'''

with open("index.html", "w", encoding="utf-8") as file:
    file.write(html_content)

print("Generated Skysport news page.")
