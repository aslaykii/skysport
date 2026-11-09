import html
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode, urlparse


USER_AGENT = "Skysport/2.0 (+https://github.com/aslaykii/skysport)"
MAX_STORIES = 36
MAX_FIXTURES_PER_FEED = 100
SCHEDULE_DAYS = 14
ATOM_NS = "{http://www.w3.org/2005/Atom}"


@dataclass(frozen=True)
class NewsFeed:
    name: str
    url: str
    domains: tuple
    homepage: str


@dataclass(frozen=True)
class FixtureFeed:
    sport: str
    competition: str
    path: str


NEWS_FEEDS = (
    NewsFeed("BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml", ("bbc.com", "bbc.co.uk", "bbci.co.uk"), "https://www.bbc.com/sport"),
    NewsFeed("The Guardian", "https://www.theguardian.com/sport/rss", ("theguardian.com",), "https://www.theguardian.com/sport"),
    NewsFeed("ESPN", "https://www.espn.com/espn/rss/news", ("espn.com", "espn.co.uk"), "https://www.espn.com/"),
    NewsFeed("Sky Sports", "https://www.skysports.com/rss/12040", ("skysports.com",), "https://www.skysports.com/"),
)

ESPN_API = "https://site.api.espn.com/apis/site/v2/sports"
FIXTURE_FEEDS = (
    FixtureFeed("Football", "Premier League", "soccer/eng.1"),
    FixtureFeed("Football", "UEFA Champions League", "soccer/uefa.champions"),
    FixtureFeed("Football", "La Liga", "soccer/esp.1"),
    FixtureFeed("Tennis", "ATP", "tennis/atp"),
    FixtureFeed("Tennis", "WTA", "tennis/wta"),
    FixtureFeed("Formula 1", "Formula 1", "racing/f1"),
    FixtureFeed("Cricket", "International cricket", "cricket/icc"),
    FixtureFeed("Rugby", "Rugby union", "rugby/union"),
)
SPORTS = ("Football", "Tennis", "Formula 1", "Cricket", "Rugby")


def clean_text(value):
    value = re.sub(r"<[^>]*>", " ", value or "")
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def local_name(element):
    return element.tag.rsplit("}", 1)[-1].lower()


def child_text(element, names):
    for child in list(element):
        if local_name(child) in names:
            text = " ".join(child.itertext()).strip()
            if text:
                return text
    return ""


def safe_feed_link(value, feed):
    parsed = urlparse((value or "").strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "https" and any(host == domain or host.endswith("." + domain) for domain in feed.domains):
        return parsed.geturl()
    return feed.homepage


def category_for(title, description):
    text = f"{title} {description}".lower()
    keywords = {
        "Football": ("football", "soccer", "premier league", "champions league", "arsenal", "chelsea", "liverpool", "man city", "spurs"),
        "Tennis": ("tennis", "wimbledon", "atp", "wta"),
        "Formula 1": ("formula 1", "formula one", "f1", "grand prix"),
        "Cricket": ("cricket", "ashes", "test match", "t20"),
        "Rugby": ("rugby", "six nations"),
    }
    return next((name for name, terms in keywords.items() if any(term in text for term in terms)), "Other")


def parse_published(value):
    try:
        published = parsedate_to_datetime(value)
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        return published.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def parse_story(item, feed):
    title = clean_text(child_text(item, {"title"}))
    if not title:
        return None
    description = clean_text(child_text(item, {"description", "summary", "encoded", "content"}))
    link = child_text(item, {"link"})
    if not link:
        atom_link = next((child for child in list(item) if child.tag == ATOM_NS + "link"), None)
        link = atom_link.get("href", "") if atom_link is not None else ""

    image = ""
    is_video = "/video" in urlparse(link).path.lower()
    for element in item.iter():
        if local_name(element) in ("thumbnail", "content"):
            media_url = element.get("url", "")
            if element.get("medium", "").lower() == "video" or element.get("type", "").lower().startswith("video/"):
                is_video = True
            if not image and urlparse(media_url).scheme == "https":
                image = media_url
    enclosure = next((child for child in list(item) if local_name(child) == "enclosure"), None)
    if enclosure is not None:
        media_type = enclosure.get("type", "").lower()
        media_url = enclosure.get("url", "")
        is_video = is_video or media_type.startswith("video/")
        if not image and media_type.startswith("image/") and urlparse(media_url).scheme == "https":
            image = media_url

    published = parse_published(child_text(item, {"pubdate", "published", "updated"}))
    return {
        "title": title,
        "description": description or f"Read the full report from {feed.name}.",
        "url": safe_feed_link(link, feed),
        "image": image,
        "category": category_for(title, description),
        "published": published,
        "source": feed.name,
        "video": is_video,
    }


def parse_feed(xml_data, feed):
    root = ET.fromstring(xml_data)
    items = [element for element in root.iter() if local_name(element) in ("item", "entry")]
    stories = [parse_story(item, feed) for item in items]
    return [story for story in stories if story]


def request_bytes(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.read()


def collect_stories(fetcher=request_bytes, feeds=NEWS_FEEDS):
    stories = []
    available = []
    failures = []
    for feed in feeds:
        try:
            items = parse_feed(fetcher(feed.url), feed)
            if not items:
                raise ValueError("feed contained no usable stories")
            stories.extend(items)
            available.append(feed.name)
        except (OSError, urllib.error.URLError, ET.ParseError, ValueError) as error:
            failures.append(f"{feed.name}: {error}")
    deduplicated = []
    seen = set()
    for story in stories:
        key = story["url"] if story["url"] != story["source"] else story["title"].casefold()
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(story)
    deduplicated.sort(key=lambda story: story["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return deduplicated[:MAX_STORIES], available, failures


def parse_event_date(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError):
        return None


def event_team(competitor):
    team = competitor.get("team") or {}
    return team.get("displayName") or team.get("name") or team.get("abbreviation") or competitor.get("name") or ""


def normalize_event(event, feed, now=None):
    now = now or datetime.now(timezone.utc)
    start = parse_event_date(event.get("date", ""))
    if start is None or start < now or start > now + timedelta(days=SCHEDULE_DAYS):
        return None
    competitions = event.get("competitions") or []
    competition_data = competitions[0] if isinstance(competitions, list) and competitions and isinstance(competitions[0], dict) else {}
    competitors = competition_data.get("competitors", [])
    if not isinstance(competitors, list) or any(not isinstance(item, dict) for item in competitors):
        competitors = []
    home = next((event_team(item) for item in competitors if item.get("homeAway") == "home"), "")
    away = next((event_team(item) for item in competitors if item.get("homeAway") == "away"), "")
    if not home and competitors:
        home = event_team(competitors[0])
    if not away and len(competitors) > 1:
        away = event_team(competitors[1])
    if not home and not away:
        home = clean_text(event.get("name", ""))
        if not home:
            return None

    links = event.get("links") or []
    event_url = next((link.get("href", "") for link in links if isinstance(link, dict) and link.get("href")), "") if isinstance(links, list) else ""
    host = (urlparse(event_url).hostname or "").lower()
    if urlparse(event_url).scheme != "https" or not (host == "espn.com" or host.endswith(".espn.com")):
        event_url = "https://www.espn.com/"
    return {
        "id": str(event.get("id") or f"{feed.path}:{start.isoformat()}:{home}:{away}"),
        "sport": feed.sport,
        "competition": feed.competition,
        "home": home or clean_text(event.get("name", "")),
        "away": away,
        "start": start,
        "url": event_url,
    }


def collect_fixtures(fetcher=request_bytes, feeds=FIXTURE_FEEDS, now=None):
    now = now or datetime.now(timezone.utc)
    start_day = now.strftime("%Y%m%d")
    end_day = (now + timedelta(days=SCHEDULE_DAYS)).strftime("%Y%m%d")
    fixtures = []
    available_sports = set()
    failures = []
    for feed in feeds:
        url = f"{ESPN_API}/{feed.path}/scoreboard?{urlencode({'dates': start_day + '-' + end_day, 'limit': MAX_FIXTURES_PER_FEED})}"
        try:
            payload = json.loads(fetcher(url))
            if not isinstance(payload, dict) or not isinstance(payload.get("events", []), list):
                raise ValueError("unexpected scoreboard response")
            available_sports.add(feed.sport)
            fixtures.extend(
                match for event in payload.get("events", [])
                if isinstance(event, dict) and (match := normalize_event(event, feed, now)) is not None
            )
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError) as error:
            failures.append(f"{feed.sport} / {feed.competition}: {error}")
    unique = {}
    for fixture in fixtures:
        unique.setdefault(fixture["id"], fixture)
    return sorted(unique.values(), key=lambda fixture: fixture["start"]), available_sports, failures


def render_story(story):
    title = html.escape(story["title"])
    description = html.escape(story["description"])
    link = html.escape(story["url"], quote=True)
    image = html.escape(story["image"], quote=True)
    category = html.escape(story["category"])
    source = html.escape(story["source"])
    published = story["published"]
    date_label = published.strftime("%d %b %Y") if published else "Latest"
    iso_date = published.isoformat() if published else ""
    image_markup = f'<img src="{image}" alt="" loading="lazy">' if image else '<span class="image-placeholder" aria-hidden="true">SPORT</span>'
    video_badge = '<span class="video-badge">VIDEO</span>' if story["video"] else ""
    return f'''<article class="story-card" data-category="{category}">
      <a class="story-image" href="{link}" target="_blank" rel="noopener noreferrer" tabindex="-1" aria-hidden="true">{image_markup}<span class="category">{category}</span>{video_badge}</a>
      <div class="story-body"><div class="story-meta"><span>{source}</span><time datetime="{html.escape(iso_date, quote=True)}">{date_label}</time><button class="save-button" type="button" aria-label="Save story" title="Save story">♡</button></div>
        <h3><a href="{link}" target="_blank" rel="noopener noreferrer">{title}</a></h3><p>{description}</p>
        <a class="read-more" href="{link}" target="_blank" rel="noopener noreferrer">Read story <span aria-hidden="true">↗</span></a>
      </div>
    </article>'''


def render_video(story):
    title = html.escape(story["title"])
    link = html.escape(story["url"], quote=True)
    image = html.escape(story["image"], quote=True)
    source = html.escape(story["source"])
    cover = f'<img src="{image}" alt="" loading="lazy">' if image else '<span class="video-placeholder" aria-hidden="true">▶</span>'
    return f'''<article class="video-card"><a class="video-cover" href="{link}" target="_blank" rel="noopener noreferrer">{cover}<span class="play-button" aria-hidden="true">▶</span></a>
      <div class="video-info"><span>{source} · VIDEO</span><h3><a href="{link}" target="_blank" rel="noopener noreferrer">{title}</a></h3><a class="read-more" href="{link}" target="_blank" rel="noopener noreferrer">Watch on {source} ↗</a></div>
    </article>'''


def render_fixture(fixture):
    home = html.escape(fixture["home"])
    away = html.escape(fixture["away"])
    competition = html.escape(fixture["competition"])
    sport = html.escape(fixture["sport"])
    link = html.escape(fixture["url"], quote=True)
    start = fixture["start"]
    matchup = f'<strong>{home}</strong><span class="versus">VS</span><strong>{away}</strong>' if away else f'<strong class="event-name">{home}</strong>'
    return f'''<article class="fixture-card" data-sport="{sport}">
      <div class="fixture-meta"><span>{sport}</span><span>{competition}</span></div>
      <div class="fixture-match">{matchup}</div>
      <div class="fixture-footer"><time datetime="{start.isoformat()}">{start.strftime("%a, %d %b · %H:%M")} UTC</time><a href="{link}" target="_blank" rel="noopener noreferrer">ESPN ↗</a></div>
    </article>'''


def render_schedule(fixtures, available_sports):
    sports_with_events = {fixture["sport"] for fixture in fixtures}
    cards = [render_fixture(match) for match in fixtures]
    for sport in SPORTS:
        if sport in sports_with_events:
            continue
        status = "No upcoming events in the next 14 days." if sport in available_sports else "Public fixture feed unavailable right now."
        cards.append(f'<article class="schedule-empty"><strong>{html.escape(sport)}</strong><span>{html.escape(status)}</span></article>')
    return "\n".join(cards)


def cached_video_cards(stories_html):
    cards = []
    articles = re.findall(r'<article\b[^>]*class="story-card"[^>]*>.*?</article>', stories_html, re.DOTALL)
    for article in articles:
        link_match = re.search(r'href="(https://[^"]*/videos?/[^"]*)"', article, re.IGNORECASE)
        if not link_match:
            continue
        title_match = re.search(r"<h[23]\b[^>]*>\s*<a\b[^>]*>(.*?)</a>\s*</h[23]>", article, re.DOTALL | re.IGNORECASE)
        if not title_match:
            continue
        image_match = re.search(r'<img\b[^>]*src="([^"]+)"', article, re.IGNORECASE)
        title = clean_text(html.unescape(title_match.group(1)))
        link = safe_feed_link(html.unescape(link_match.group(1)), NEWS_FEEDS[0])
        image = html.unescape(image_match.group(1)) if image_match else ""
        if urlparse(image).scheme != "https":
            image = ""
        cards.append(render_video({
            "title": title,
            "url": link,
            "image": image,
            "source": "BBC Sport",
        }))
    return "\n".join(cards)


STYLE = """
<style>
:root{color-scheme:dark;--bg:#081321;--surface:#101e31;--surface2:#182a42;--text:#f4f7fc;--muted:#a9b7ca;--accent:#ff493d;--line:#ffffff18;--green:#57e39a}
:root.light{color-scheme:light;--bg:#f3f6fb;--surface:#fff;--surface2:#e8eef7;--text:#162238;--muted:#5e6d82;--line:#1327471a}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:18px}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}a{color:inherit}button,input{font:inherit}.wrap{width:min(1200px,calc(100% - 40px));margin:auto}
.masthead{background:linear-gradient(90deg,#06101deb,#081321a8),url("https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=2000&q=80") center 48%/cover;border-bottom:1px solid var(--line)}
.nav{min-height:74px;display:flex;align-items:center;justify-content:space-between;gap:20px}.brand{display:flex;align-items:center;gap:11px;text-decoration:none}.brand-mark{display:grid;place-items:center;width:42px;height:42px;border-radius:13px;background:linear-gradient(135deg,var(--accent),#ff8b42);font-size:22px;font-weight:900}.brand-name{color:#fff;font-size:1.13rem;font-weight:850;letter-spacing:.13em;text-transform:uppercase}.nav-links{display:flex;gap:24px;color:#e3eaf5;font-size:.88rem;font-weight:650}.nav-links a{text-decoration:none}.nav-links a:hover{color:#ffbcb6}.nav-right{display:flex;align-items:center;gap:14px}.desk-label{color:#e4ffec;font-size:.73rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase}.desk-label:before{content:"";display:inline-block;width:8px;height:8px;margin-right:8px;border-radius:50%;background:var(--green)}.theme-button{width:39px;height:39px;border:1px solid #ffffff50;border-radius:50%;color:#fff;background:#07101d75;cursor:pointer}
.hero{padding:55px 0 62px;color:#fff}.eyebrow{color:#ffbcb6;text-transform:uppercase;letter-spacing:.17em;font-weight:850;font-size:.73rem}.hero h1{max-width:780px;margin:12px 0;font-size:clamp(2.5rem,6.1vw,4.7rem);line-height:1.01;letter-spacing:-.055em}.hero p{max-width:620px;margin:0;color:#d5deeb;font-size:1.04rem}.hero-stats{display:flex;gap:22px;margin-top:27px;color:#e3eaf5;font-size:.78rem}.hero-stats strong{color:#fff;font-size:1rem}
.ticker{background:var(--accent);color:#fff}.ticker .wrap{min-height:40px;display:flex;align-items:center;gap:12px;font-size:.8rem;font-weight:750}.ticker-label{border:1px solid #ffffff75;padding:2px 8px;border-radius:4px;font-size:.68rem;letter-spacing:.08em}
.section-head{display:flex;align-items:end;justify-content:space-between;gap:18px;flex-wrap:wrap;padding:33px 0 16px}.section-head h2{margin:0;font-size:1.6rem;letter-spacing:-.025em}.section-head p{margin:3px 0 0;color:var(--muted);font-size:.82rem}.search{width:min(330px,100%);padding:11px 14px;color:var(--text);background:var(--surface);border:1px solid var(--line);border-radius:11px;outline:none}.search:focus{border-color:var(--accent);box-shadow:0 0 0 3px #ff493d25}
.filters{display:flex;gap:8px;overflow-x:auto;padding:0 0 19px}.filter{flex:none;border:1px solid var(--line);border-radius:999px;padding:8px 14px;color:var(--muted);background:var(--surface);font-size:.82rem;font-weight:650;cursor:pointer}.filter:hover,.filter.active{color:var(--text);border-color:#ff493d88;background:#ff493d1c}
.news-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;padding-bottom:24px}.story-card{overflow:hidden;background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:0 12px 32px #00000018;transition:transform .2s,border-color .2s}.story-card:hover{transform:translateY(-3px);border-color:#ff493d70}.story-image{display:block;position:relative;aspect-ratio:16/9;overflow:hidden;background:var(--surface2)}.story-image img{width:100%;height:100%;display:block;object-fit:cover;transition:transform .35s}.story-card:hover .story-image img{transform:scale(1.035)}.image-placeholder{display:grid;place-items:center;width:100%;height:100%;color:#71829a;font-weight:900;letter-spacing:.18em;background:linear-gradient(135deg,var(--surface2),var(--surface))}.category{position:absolute;left:12px;bottom:12px;padding:4px 9px;border-radius:6px;background:var(--accent);color:#fff;font-size:.66rem;font-weight:800;text-transform:uppercase}.video-badge{position:absolute;top:11px;right:11px;padding:4px 7px;border-radius:4px;background:#07101dcc;color:#fff;font-size:.62rem;font-weight:850;letter-spacing:.08em}.story-body{padding:15px 16px 17px}.story-meta{display:flex;align-items:center;gap:9px;color:#ff796f;font-size:.64rem;letter-spacing:.055em;font-weight:850}.story-meta time{margin-left:auto;color:var(--muted);letter-spacing:0;font-weight:500;white-space:nowrap}.save-button{border:0;padding:0 2px;color:var(--muted);background:transparent;font-size:1.35rem;line-height:1;cursor:pointer}.save-button.saved,.save-button:hover{color:var(--accent)}.story-body h2,.story-body h3{margin:11px 0 7px;font-size:1.08rem;line-height:1.4}.story-body h2 a,.story-body h3 a,.video-info h3 a{text-decoration:none}.story-body h2 a:hover,.story-body h3 a:hover,.video-info h3 a:hover{color:#ff796f}.story-body p{margin:0;color:var(--muted);font-size:.86rem;line-height:1.6}.read-more{display:inline-block;margin-top:11px;color:#ff796f;font-size:.8rem;font-weight:750;text-decoration:none}.read-more:hover{text-decoration:underline}.empty-state{grid-column:1/-1;padding:30px;text-align:center;color:var(--muted);border:1px dashed var(--line);border-radius:14px}
.content-section{padding:12px 0 29px}.section-title{display:flex;align-items:end;justify-content:space-between;gap:12px;margin-bottom:15px}.section-title h2{margin:0;font-size:1.55rem}.section-title p{margin:0;color:var(--muted);font-size:.8rem}.video-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.video-card{overflow:hidden;background:var(--surface);border:1px solid var(--line);border-radius:15px}.video-cover{display:block;position:relative;aspect-ratio:16/9;overflow:hidden;background:var(--surface2)}.video-cover img{width:100%;height:100%;object-fit:cover}.video-placeholder{display:grid;place-items:center;width:100%;height:100%;color:#ff796f;font-size:2rem}.play-button{position:absolute;left:50%;top:50%;display:grid;place-items:center;width:46px;height:46px;border-radius:50%;color:#fff;background:var(--accent);box-shadow:0 5px 20px #0008;transform:translate(-50%,-50%);font-size:.92rem}.video-info{padding:12px 15px 15px}.video-info>span{color:#ff796f;font-size:.65rem;font-weight:850;letter-spacing:.07em}.video-info h3{margin:5px 0 0;font-size:.98rem;line-height:1.4}.section-empty{padding:25px;color:var(--muted);background:var(--surface);border:1px dashed var(--line);border-radius:13px;text-align:center}
.schedule-wrap{margin:4px 0 38px;padding:20px;border:1px solid var(--line);border-radius:18px;background:linear-gradient(135deg,var(--surface),var(--bg))}.schedule-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.fixture-card,.schedule-empty{padding:15px;background:var(--surface);border:1px solid var(--line);border-radius:12px}.fixture-meta{display:flex;justify-content:space-between;gap:8px;color:#ff796f;font-size:.64rem;font-weight:850;letter-spacing:.045em;text-transform:uppercase}.fixture-match{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:17px 0;font-size:.9rem}.fixture-match strong{flex:1}.fixture-match strong:last-child{text-align:right}.versus{color:var(--muted);font-size:.65rem;font-weight:800}.fixture-footer{display:flex;justify-content:space-between;gap:8px;padding-top:10px;border-top:1px solid var(--line);color:var(--muted);font-size:.7rem}.fixture-footer a{color:var(--muted);text-decoration:none}.fixture-footer a:hover{color:var(--text)}.schedule-empty{display:flex;flex-direction:column;gap:4px;color:var(--muted);font-size:.77rem}.schedule-empty strong{color:var(--text);font-size:.9rem}.schedule-note{margin:10px 0 0;color:var(--muted);font-size:.74rem}
.fixture-match .event-name{flex:none;text-align:left!important}
footer{border-top:1px solid var(--line);padding:22px 0 32px;color:var(--muted);font-size:.8rem;text-align:center}[hidden]{display:none!important}
@media(max-width:900px){.news-grid,.video-grid,.schedule-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.nav-links{gap:14px}}
@media(max-width:650px){.wrap{width:min(100% - 28px,1200px)}.nav{min-height:65px}.nav-links{display:none}.desk-label{display:none}.hero{padding:42px 0 48px}.hero-stats{gap:14px;flex-wrap:wrap}.section-head{align-items:stretch}.search{width:100%}.news-grid,.video-grid,.schedule-grid{grid-template-columns:1fr;gap:13px}.story-card{display:grid;grid-template-columns:112px minmax(0,1fr)}.story-image{height:100%;min-height:164px;aspect-ratio:auto}.story-body{padding:11px}.story-body h3{font-size:.96rem;margin:8px 0 5px}.story-body p{font-size:.78rem;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.story-meta{font-size:.56rem;gap:5px}.read-more{margin-top:7px}.schedule-wrap{padding:14px}.fixture-match{font-size:.86rem}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;transition:none!important}}
</style>
"""


def build_page(stories_html, videos_html, fixtures_html, updated, news_sources, fixture_status):
    page = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Sports headlines, video highlights and upcoming fixtures from trusted public sources.">
  <meta name="theme-color" content="#081321"><title>Skysport — Sports news, video & fixtures</title>
@@STYLE@@
</head>
<body>
  <header class="masthead"><div class="wrap">
    <nav class="nav" aria-label="Main navigation"><a class="brand" href="#top"><span class="brand-mark" aria-hidden="true">S</span><span class="brand-name">Skysport</span></a>
      <div class="nav-links"><a href="#news">News</a><a href="#videos">Videos</a><a href="#fixtures">Fixtures</a></div>
      <div class="nav-right"><span class="desk-label">Sports desk</span><button class="theme-button" id="theme-toggle" type="button" aria-label="Switch to light theme" title="Switch theme">☼</button></div>
    </nav>
    <section class="hero" id="top"><span class="eyebrow">The global sports desk</span><h1>Every moment.<br>Every sport.</h1><p>Big stories, video highlights and the upcoming fixtures that matter — gathered from sports publishers around the world.</p>
      <div class="hero-stats"><span><strong>05</strong> sports</span><span><strong>04</strong> news desks</span><span><strong>14 days</strong> fixture window</span></div>
    </section>
  </div></header>
  <div class="ticker"><div class="wrap"><span class="ticker-label">SPORTS DESK</span><span>Football · Tennis · Formula 1 · Cricket · Rugby</span></div></div>
  <main class="wrap">
    <section class="section-head" id="news"><div><h2>Latest headlines</h2><p>@@UPDATED@@ · Sources: @@NEWS_SOURCES@@</p></div><input class="search" id="search" type="search" placeholder="Search headlines…" aria-label="Search headlines"></section>
    <nav class="filters" aria-label="Filter headlines by sport"><button class="filter active" type="button" data-filter="All">All sports</button><button class="filter" type="button" data-filter="Football">Football</button><button class="filter" type="button" data-filter="Tennis">Tennis</button><button class="filter" type="button" data-filter="Formula 1">Formula 1</button><button class="filter" type="button" data-filter="Cricket">Cricket</button><button class="filter" type="button" data-filter="Rugby">Rugby</button><button class="filter" type="button" data-filter="Other">Other</button><button class="filter" type="button" data-filter="Saved">♡ Saved</button></nav>
    <div class="news-grid" id="news-grid">@@STORIES@@<p class="empty-state" id="empty-state" hidden>No headlines are available. Please check back after the next source update.</p></div>
    <section class="content-section" id="videos"><div class="section-title"><div><h2>Video highlights</h2><p>Watch on the publisher’s site</p></div></div><div class="video-grid">@@VIDEOS@@</div></section>
    <section class="content-section" id="fixtures"><div class="section-title"><div><h2>Upcoming fixtures</h2><p>Public scoreboard data · Next 14 days · Times shown in UTC</p></div></div>
      <div class="schedule-wrap"><div class="schedule-grid">@@FIXTURES@@</div><p class="schedule-note">@@FIXTURE_STATUS@@ Fixtures are supplied by ESPN’s public scoreboard feeds. Availability can vary by sport and competition.</p></div>
    </section>
  </main>
  <footer><div class="wrap">Skysport · Headlines and videos link to their publishers. Fixture data: ESPN public scoreboards.</div></footer>
  <script>
    (() => {
      const filters = [...document.querySelectorAll('.filter')];
      const cards = [...document.querySelectorAll('.story-card')];
      const search = document.getElementById('search');
      const empty = document.getElementById('empty-state');
      const themeButton = document.getElementById('theme-toggle');
      let selected = 'All';
      let saved = new Set();
      try { saved = new Set(JSON.parse(localStorage.getItem('skysport-saved') || '[]')); } catch {}
      const storyKey = card => card.querySelector('h3, h2')?.textContent.trim() || '';
      function updateSavedButton(card) {
        const button = card.querySelector('.save-button');
        if (!button) return;
        const isSaved = saved.has(storyKey(card));
        button.classList.toggle('saved', isSaved);
        button.textContent = isSaved ? '♥' : '♡';
        button.setAttribute('aria-label', isSaved ? 'Remove saved story' : 'Save story');
      }
      cards.forEach(card => {
        updateSavedButton(card);
        card.querySelector('.save-button')?.addEventListener('click', () => {
          const key = storyKey(card);
          saved.has(key) ? saved.delete(key) : saved.add(key);
          try { localStorage.setItem('skysport-saved', JSON.stringify([...saved])); } catch {}
          updateSavedButton(card);
          updateCards();
        });
      });
      function updateCards() {
        const query = search.value.trim().toLocaleLowerCase();
        let count = 0;
        cards.forEach(card => {
          const categoryMatch = selected === 'All' || (selected === 'Saved' ? saved.has(storyKey(card)) : card.dataset.category === selected);
          card.hidden = !(categoryMatch && card.textContent.toLocaleLowerCase().includes(query));
          if (!card.hidden) count++;
        });
        empty.hidden = count > 0;
      }
      filters.forEach(button => button.addEventListener('click', () => {
        filters.forEach(item => item.classList.toggle('active', item === button));
        selected = button.dataset.filter;
        updateCards();
      }));
      search.addEventListener('input', updateCards);
      try {
        if (localStorage.getItem('skysport-theme') === 'light') document.documentElement.classList.add('light');
      } catch {}
      themeButton.addEventListener('click', () => {
        const light = document.documentElement.classList.toggle('light');
        themeButton.setAttribute('aria-label', light ? 'Switch to dark theme' : 'Switch to light theme');
        try { localStorage.setItem('skysport-theme', light ? 'light' : 'dark'); } catch {}
      });
    })();
  </script>
</body>
</html>"""
    replacements = {
        "@@STYLE@@": STYLE,
        "@@UPDATED@@": html.escape(updated),
        "@@NEWS_SOURCES@@": html.escape(news_sources),
        "@@STORIES@@": stories_html,
        "@@VIDEOS@@": videos_html or '<p class="section-empty">No video items were available from the active RSS feeds.</p>',
        "@@FIXTURES@@": fixtures_html,
        "@@FIXTURE_STATUS@@": html.escape(fixture_status),
    }
    for marker, value in replacements.items():
        page = page.replace(marker, value)
    return page


def read_cached_news(path="index.html"):
    try:
        with open(path, encoding="utf-8") as existing:
            current = existing.read()
    except OSError:
        return "", ""
    cards = re.findall(r'<article\b[^>]*class="story-card"[^>]*>.*?</article>', current, re.DOTALL)
    updated = re.search(r"(?:Updated|Last cached update:?)\s+([^<]+?)\s*·\s*(?:News source|Sources|Source):", current)
    updated_label = updated.group(1).strip() if updated else ""
    if updated_label == "No successful feed refresh yet":
        updated_label = ""
    return "\n".join(cards), updated_label


def main():
    stories, news_sources, news_failures = collect_stories()
    stories_html = "\n".join(render_story(story) for story in stories)
    if news_failures:
        print("Some news feeds could not be updated: " + "; ".join(news_failures))
    if not stories:
        print("No news feed returned usable stories; retaining previously generated headlines if available.")
        stories_html, cached_updated = read_cached_news()
        news_sources = ["BBC Sport (saved headlines)"] if stories_html else []
        updated = cached_updated or ("Cached headlines - refresh time unavailable" if stories_html else "No successful feed refresh yet")
    else:
        updated = datetime.now(timezone.utc).strftime("%d %b %Y · %H:%M UTC")
    if not stories_html:
        stories_html = '<p class="empty-state">Headlines are temporarily unavailable. The scheduled update will try again.</p>'
    videos_html = "\n".join(render_video(story) for story in stories if story["video"])
    if not stories and videos_html == "":
        videos_html = cached_video_cards(stories_html)

    fixtures, available_sports, fixture_failures = collect_fixtures()
    if fixture_failures:
        print("Some fixture feeds could not be updated: " + "; ".join(fixture_failures))
    fixtures_html = render_schedule(fixtures, available_sports)
    if not fixtures and fixture_failures and not available_sports:
        fixture_status = "All public schedule requests failed this refresh."
    elif not fixtures:
        fixture_status = "No fixtures were returned by public feeds this refresh."
    elif len(available_sports) < len(SPORTS):
        fixture_status = "Some sports do not have a currently available public schedule feed."
    else:
        fixture_status = ""
    source_label = ", ".join(news_sources) if news_sources else "No RSS source available"
    page = build_page(stories_html, videos_html, fixtures_html, updated, source_label, fixture_status)
    with open("index.html", "w", encoding="utf-8") as output:
        output.write(page)
    print("Generated Skysport page successfully.")


if __name__ == "__main__":
    main()
