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


def safe_story_link(value):
    parsed = urlparse((value or "").strip())
    host = (parsed.hostname or "").lower()
    trusted = host in {"bbc.com", "bbc.co.uk"} or host.endswith((".bbc.com", ".bbc.co.uk"))
    if parsed.scheme == "https" and trusted:
        return parsed.geturl()
    return "https://www.bbc.com/sport"


def story_image(item, index):
    candidates = []
    for tag in ("thumbnail", "content"):
        candidates.extend(node.get("url", "") for node in item.findall(f"media:{tag}", MEDIA_NS))
    enclosure = item.find("enclosure")
    if enclosure is not None and enclosure.get("type", "").startswith("image/"):
        candidates.append(enclosure.get("url", ""))
    for candidate in candidates:
        parsed = urlparse(candidate)
        host = (parsed.hostname or "").lower()
        trusted = host.endswith("bbc.co.uk") or host.endswith("bbci.co.uk") or host.endswith("bbc.com")
        if parsed.scheme == "https" and trusted:
            return parsed.geturl()
    return FALLBACK_IMAGES[index % len(FALLBACK_IMAGES)]


def sport_category(title, description):
    text = f"{title} {description}".lower()
    groups = {
        "Football": ("football", "premier league", "champions league", "arsenal", "chelsea", "liverpool", "man city"),
        "Tennis": ("tennis", "wimbledon", "atp", "wta"),
        "Formula 1": ("formula 1", "formula one", "f1", "grand prix"),
        "Cricket": ("cricket", "ashes", "test match", "t20"),
        "Rugby": ("rugby", "six nations"),
    }
    return next((name for name, terms in groups.items() if any(term in text for term in terms)), "Other sports")


def render_story(item, index):
    title = clean_text(item.findtext("title"))
    if not title:
        return ""
    description = clean_text(item.findtext("description")) or "Read the full report on BBC Sport."
    link = html.escape(safe_story_link(item.findtext("link")), quote=True)
    image = html.escape(story_image(item, index), quote=True)
    category = sport_category(title, description)
    try:
        published = datetime.strptime(item.findtext("pubDate", ""), "%a, %d %b %Y %H:%M:%S %z")
        date_label = published.astimezone(timezone.utc).strftime("%d %b %Y")
    except ValueError:
        date_label = "Latest"
    return f'''<article class="story-card" data-category="{html.escape(category, quote=True)}">
      <a class="story-image" href="{link}" target="_blank" rel="noopener noreferrer" tabindex="-1" aria-hidden="true"><img src="{image}" alt="" loading="lazy"><span class="category">{html.escape(category)}</span></a>
      <div class="story-body"><div class="story-meta"><span>BBC SPORT</span><time>{html.escape(date_label)}</time><button class="save-button" type="button" aria-label="Save story">♡</button></div>
      <h2><a href="{link}" target="_blank" rel="noopener noreferrer">{html.escape(title)}</a></h2><p>{html.escape(description)}</p>
      <a class="read-more" href="{link}" target="_blank" rel="noopener noreferrer">Read story ↗</a></div>
    </article>'''


def fetch_stories():
    request = urllib.request.Request(RSS_URL, headers={"User-Agent": "Skysport/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        root = ET.fromstring(response.read())
    stories = [render_story(item, index) for index, item in enumerate(root.findall("./channel/item"))]
    stories = [story for story in stories if story][:MAX_STORIES]
    if not stories:
        raise ValueError("RSS feed returned no usable headlines")
    return "\n".join(stories)


PAGE_TEMPLATE = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Latest global sports headlines, photos and reports from BBC Sport."><meta name="theme-color" content="#091321">
<title>Skysport | Global Sports News</title><style>
:root{color-scheme:dark;--bg:#091321;--panel:#111f32;--text:#f4f7fc;--muted:#a9b7ca;--red:#ff493d;--line:#ffffff18}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}a{color:inherit;text-decoration:none}.wrap{width:min(1160px,calc(100% - 32px));margin:auto}
header{color:#fff;background:linear-gradient(90deg,#081321ed,#091321ad),url("https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1800&q=80") center/cover;border-bottom:1px solid var(--line)}.nav{height:74px;display:flex;align-items:center;justify-content:space-between}.brand{display:flex;align-items:center;gap:12px;font-weight:850;letter-spacing:.12em;text-transform:uppercase}.logo{display:grid;place-items:center;width:42px;height:42px;border-radius:12px;background:linear-gradient(135deg,var(--red),#ff8b42);font-size:22px}.live{font-size:.76rem;color:#c9ffd8;text-transform:uppercase;letter-spacing:.1em}.live:before{content:"";display:inline-block;width:8px;height:8px;background:#4ade80;border-radius:50%;margin-right:8px}.hero{padding:54px 0 62px}.eyebrow{font-size:.74rem;letter-spacing:.17em;text-transform:uppercase;color:#ffbcb6;font-weight:800}.hero h1{font-size:clamp(2.4rem,6vw,4.6rem);line-height:1.04;letter-spacing:-.05em;margin:12px 0;max-width:760px}.hero p{color:#d5deeb;max-width:600px;margin:0;font-size:1.03rem}
.ticker{background:var(--red);color:white;font-size:.8rem;font-weight:700;padding:9px 0}.toolbar{display:flex;justify-content:space-between;align-items:end;gap:16px;flex-wrap:wrap;padding:29px 0 17px}.toolbar h2{margin:0;font-size:1.5rem}.toolbar p{margin:3px 0 0;color:var(--muted);font-size:.83rem}.search{width:min(320px,100%);padding:11px 14px;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--text);font:inherit}.search:focus{outline:2px solid #ff493d77}.filters{display:flex;gap:8px;overflow:auto;padding-bottom:19px}.filter{flex:none;padding:8px 14px;border:1px solid var(--line);border-radius:999px;background:var(--panel);color:var(--muted);font:inherit;font-size:.83rem;cursor:pointer}.filter.active,.filter:hover{color:var(--text);border-color:#ff493d88;background:#ff493d22}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;padding-bottom:42px}.story-card{overflow:hidden;background:var(--panel);border:1px solid var(--line);border-radius:16px;box-shadow:0 12px 30px #0003;transition:transform .2s}.story-card:hover{transform:translateY(-3px)}.story-image{display:block;position:relative;aspect-ratio:16/9;background:#172941;overflow:hidden}.story-image img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .3s}.story-card:hover .story-image img{transform:scale(1.04)}.category{position:absolute;left:12px;bottom:12px;background:var(--red);padding:5px 9px;border-radius:5px;color:white;font-size:.68rem;font-weight:800;text-transform:uppercase}.story-body{padding:16px}.story-meta{display:flex;align-items:center;gap:10px;color:var(--muted);font-size:.7rem}.story-meta b,.story-meta>span{color:#ff857c;letter-spacing:.08em;font-weight:800}.story-meta time{margin-left:auto}.save-button{border:0;background:transparent;color:var(--muted);font-size:1.35rem;cursor:pointer}.save-button.saved,.save-button:hover{color:var(--red)}.story-body h2{font-size:1.1rem;line-height:1.4;margin:10px 0 7px}.story-body h2 a:hover,.read-more:hover{color:#ff938b}.story-body p{margin:0;color:var(--muted);font-size:.9rem;line-height:1.65}.read-more{display:inline-block;margin-top:12px;color:#ff8e86;font-size:.83rem;font-weight:750}.empty{grid-column:1/-1;text-align:center;padding:32px;color:var(--muted);border:1px dashed var(--line);border-radius:14px}footer{border-top:1px solid var(--line);padding:23px 0 32px;text-align:center;color:var(--muted);font-size:.82rem}[hidden]{display:none!important}
@media(max-width:900px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.wrap{width:calc(100% - 26px)}.live{display:none}.hero{padding:42px 0}.toolbar{align-items:stretch}.search{width:100%}.grid{grid-template-columns:1fr;gap:13px}.story-card{display:grid;grid-template-columns:112px minmax(0,1fr)}.story-image{height:100%;min-height:165px;aspect-ratio:auto}.story-body{padding:12px}.story-body h2{font-size:.96rem;margin:8px 0 5px}.story-body p{font-size:.79rem;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.read-more{margin-top:8px}.story-meta{font-size:.59rem;gap:6px}}@media(prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;transition:none!important}}
</style></head><body><header><div class="wrap"><nav class="nav"><a class="brand" href="#"><span class="logo">S</span>Skysport</a><span class="live">Sports desk</span></nav><section class="hero"><span class="eyebrow">The global sports desk</span><h1>Every moment.<br>Every sport.</h1><p>Match-day drama, big stories and the latest headlines from across the sporting world.</p></section></div></header>
<div class="ticker"><div class="wrap">TOP STORIES &nbsp; · &nbsp; Football &nbsp; · &nbsp; Tennis &nbsp; · &nbsp; Formula 1 &nbsp; · &nbsp; Rugby &nbsp; · &nbsp; Cricket</div></div><main class="wrap"><section class="toolbar"><div><h2>Latest headlines</h2><p>Updated {{UPDATED}} · News from BBC Sport</p></div><input class="search" id="search" type="search" placeholder="Search headlines…" aria-label="Search headlines"></section>
<nav class="filters" aria-label="Filter sports"><button class="filter active" data-filter="All" type="button">All sports</button><button class="filter" data-filter="Football" type="button">Football</button><button class="filter" data-filter="Tennis" type="button">Tennis</button><button class="filter" data-filter="Formula 1" type="button">Formula 1</button><button class="filter" data-filter="Rugby" type="button">Rugby</button><button class="filter" data-filter="Cricket" type="button">Cricket</button><button class="filter" data-filter="Other sports" type="button">Other</button><button class="filter" data-filter="Saved" type="button">♡ Saved</button></nav>
<div class="grid" id="grid">{{NEWS}}<p class="empty" id="empty" hidden>No headlines match. Try another search or filter.</p></div></main><footer><div class="wrap">Skysport · Headlines and reporting links provided by BBC Sport RSS</div></footer>
<script>(()=>{{const buttons=[...document.querySelectorAll('.filter')],cards=[...document.querySelectorAll('.story-card')],search=document.getElementById('search'),empty=document.getElementById('empty');let selected='All',saved=new Set();try{{saved=new Set(JSON.parse(localStorage.getItem('skysport-saved')||'[]'))}}catch{{}}const key=c=>c.querySelector('h2')?.textContent.trim()||'';function update(){{let shown=0;const q=search.value.trim().toLowerCase();cards.forEach(c=>{{const b=c.querySelector('.save-button'),isSaved=saved.has(key(c));if(b){{b.textContent=isSaved?'♥':'♡';b.classList.toggle('saved',isSaved);b.setAttribute('aria-label',isSaved?'Remove saved story':'Save story')}}const match=selected==='All'||(selected==='Saved'?isSaved:c.dataset.category===selected);c.hidden=!(match&&c.textContent.toLowerCase().includes(q));if(!c.hidden)shown++}});empty.hidden=shown>0}}cards.forEach(c=>c.querySelector('.save-button')?.addEventListener('click',()=>{{saved.has(key(c))?saved.delete(key(c)):saved.add(key(c));try{{localStorage.setItem('skysport-saved',JSON.stringify([...saved]))}}catch{{}}update()}}));buttons.forEach(b=>b.addEventListener('click',()=>{{buttons.forEach(x=>x.classList.toggle('active',x===b));selected=b.dataset.filter;update()}}));search.addEventListener('input',update)}})();</script></body></html>'''


def main():
    try:
        stories = fetch_stories()
    except (OSError, ET.ParseError, ValueError) as error:
        print(f"RSS update failed; keeping existing page: {error}")
        # Avoid replacing a working page when the external feed is temporarily down.
        try:
            with open("index.html", encoding="utf-8") as current:
                if "<html" in current.read().lower():
                    return
        except OSError:
            pass
        stories = '<article class="story-card"><div class="story-body"><h2>News temporarily unavailable</h2><p>Please check back later.</p></div></article>'
    updated = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    page = PAGE_TEMPLATE.replace("{{NEWS}}", stories).replace("{{UPDATED}}", html.escape(updated))
    with open("index.html", "w", encoding="utf-8") as output:
        output.write(page)
    print("Skysport page updated successfully.")


if __name__ == "__main__":
    main()
