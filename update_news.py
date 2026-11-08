import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

RSS_URL = "https://feeds.bbci.co.uk/sport/rss.xml"
MAX_ITEMS = 8


def clean_text(value):
    """Convert RSS markup to safe, readable plain text."""
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]*>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def news_card(item):
    title = clean_text(item.findtext("title"))
    description = clean_text(item.findtext("description"))
    link = (item.findtext("link") or "").strip()
    pub_date = item.findtext("pubDate") or ""
    if not title:
        return ""

    # Only link to HTTPS stories from BBC; don't trust arbitrary feed URLs.
    if not link.startswith("https://www.bbc.com/") and not link.startswith("https://www.bbc.co.uk/"):
        link = "https://www.bbc.com/sport"

    try:
        date = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %z")
        date_text = date.astimezone(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    except ValueError:
        date_text = "Latest news"

    return f'''<article class="news-card">
      <p class="meta">BBC SPORT <span>{html.escape(date_text)}</span></p>
      <h2><a href="{html.escape(link, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(title)}</a></h2>
      <p class="description">{html.escape(description or "Read the full story on BBC Sport.")}</p>
    </article>'''


try:
    request = urllib.request.Request(RSS_URL, headers={"User-Agent": "SkysportNews/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        root = ET.fromstring(response.read())

    cards = [news_card(item) for item in root.findall("./channel/item")]
    cards = [card for card in cards if card][:MAX_ITEMS]
    if not cards:
        raise ValueError("RSS feed contained no usable stories")
    news_items_html = "\n".join(cards)
except (OSError, ET.ParseError, ValueError) as error:
    print(f"Could not update RSS news: {error}")
    news_items_html = '''<article class="news-card notice">
      <h2>News temporarily unavailable</h2>
      <p class="description">We couldn't load the latest headlines. Please check back soon.</p>
    </article>'''

updated = datetime.now(timezone.utc).strftime("%d %b %Y at %H:%M UTC")
html_content = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="The latest global sports headlines, updated automatically.">
  <meta name="theme-color" content="#0b1220">
  <title>Skysport | Global Sports News</title>
  <style>
    :root {{ color-scheme: dark; --bg:#0b1220; --panel:#121e31; --text:#f4f7fc; --muted:#a9b5c9; --red:#ff3b30; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:radial-gradient(ellipse at top,#172743,var(--bg) 55%); color:var(--text); font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif; }}
    header {{ border-bottom:1px solid #ffffff18; background:#0b1220cc; }}
    .wrap {{ width:min(920px,calc(100% - 32px)); margin:auto; }}
    .masthead {{ padding:30px 0 25px; }}
    .brand {{ display:flex; align-items:center; gap:13px; }}
    .mark {{ display:grid; place-items:center; width:45px; height:45px; border-radius:14px; background:var(--red); font-weight:900; font-size:24px; box-shadow:0 8px 25px #ff3b3040; }}
    h1 {{ margin:0; font-size:clamp(1.7rem,5vw,2.4rem); letter-spacing:.12em; text-transform:uppercase; }}
    .intro {{ padding:30px 0 18px; }}
    .intro h2 {{ margin:0 0 5px; font-size:clamp(1.35rem,4vw,2rem); }}
    .intro p,.description {{ color:var(--muted); }}
    .intro p {{ margin:0; }}
    main {{ padding:8px 0 40px; }}
    .news-card {{ margin:0 0 17px; padding:22px; background:linear-gradient(145deg,var(--panel),#101a2b); border:1px solid #ffffff12; border-left:4px solid var(--red); border-radius:15px; box-shadow:0 12px 30px #0003; }}
    .meta {{ display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; margin:0 0 10px; color:#ffb1ab; font-size:.75rem; font-weight:750; letter-spacing:.07em; }}
    .meta span {{ color:var(--muted); font-weight:500; letter-spacing:normal; }}
    .news-card h2 {{ margin:0 0 8px; font-size:clamp(1.15rem,3vw,1.5rem); line-height:1.35; }}
    .news-card a {{ color:var(--text); text-decoration:none; }}
    .news-card a:hover {{ color:#ffaaa4; }}
    .description {{ margin:0; }}
    .notice {{ border-left-color:#ffb020; }}
    footer {{ padding:10px 0 32px; text-align:center; color:var(--muted); font-size:.85rem; }}
    @media (prefers-reduced-motion:no-preference) {{ .news-card {{ transition:transform .18s ease,border-color .18s ease; }} .news-card:hover {{ transform:translateY(-2px); }} }}
  </style>
</head>
<body>
  <header><div class="wrap masthead"><div class="brand"><div class="mark" aria-hidden="true">S</div><h1>Skysport</h1></div></div></header>
  <section class="wrap intro"><h2>Global sports headlines</h2><p>Latest sports news, automatically refreshed. Last generated: {html.escape(updated)}.</p></section>
  <main class="wrap" aria-label="Latest sports news">{news_items_html}</main>
  <footer class="wrap">Headlines provided by BBC Sport RSS • Automatically updated with GitHub Actions</footer>
</body>
</html>
'''

with open("index.html", "w", encoding="utf-8") as file:
    file.write(html_content)

print("Generated Skysport news page.")
