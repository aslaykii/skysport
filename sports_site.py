import html
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlparse


USER_AGENT = "Skysport/2.0 (+https://github.com/aslaykii/skysport)"
SITE_URL = "https://aslaykii.github.io/skysport/"
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
    format: str = "rss"


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
    NewsFeed("beIN SPORTS", "https://www.beinsports.com/en-mena/all-news", ("beinsports.com",), "https://www.beinsports.com/en-mena", "html"),
)

ESPN_API = "https://site.api.espn.com/apis/site/v2/sports"
FIXTURE_FEEDS = (
    FixtureFeed("Football", "Premier League", "soccer/eng.1"),
    FixtureFeed("Football", "UEFA Champions League", "soccer/uefa.champions"),
    FixtureFeed("Football", "La Liga", "soccer/esp.1"),
    FixtureFeed("Tennis", "ATP", "tennis/atp"),
    FixtureFeed("Tennis", "WTA", "tennis/wta"),
    FixtureFeed("Formula 1", "Formula 1", "racing/f1"),
    FixtureFeed("Basketball", "NBA", "basketball/nba"),
    FixtureFeed("American Football", "NFL", "football/nfl"),
    FixtureFeed("Ice Hockey", "NHL", "hockey/nhl"),
    FixtureFeed("Cricket", "International cricket", "cricket/icc"),
    FixtureFeed("Rugby", "Rugby union", "rugby/union"),
)
SPORTS = ("Football", "Tennis", "Formula 1", "Basketball", "American Football", "Ice Hockey", "Cricket", "Rugby")
ESPN_NEWS_PATHS = {
    "Football": "soccer/eng.1",
    "Basketball": "basketball/nba",
    "Formula 1": "racing/f1",
    "American Football": "football/nfl",
    "Ice Hockey": "hockey/nhl",
}
NEWS_CATEGORIES = (
    "Football", "Tennis", "Formula 1", "Cricket", "Rugby",
    "Basketball", "American Football", "Ice Hockey", "Golf", "Boxing & MMA", "Other",
)
PAGE_FILES = {
    "home": "index.html",
    "news": "news.html",
    "videos": "videos.html",
    "live": "live.html",
    "fixtures": "fixtures.html",
}

TRANSLATIONS = {
    "en": {
        "title": "SkySport | Sports News, Live Scores & Fixtures",
        "metaDescription": "Latest football, basketball, tennis and Formula 1 news, with live scores, videos and upcoming fixtures from trusted sports publishers.",
        "pages": {
            "home": {"title": "SkySport | Sports News, Live Scores & Fixtures", "description": "Sports headlines, trusted sources, video highlights, live scores and upcoming fixtures.", "heading": "The sports world, in focus.", "intro": "Follow the latest headlines, watch highlights, check live scores and find upcoming fixtures."},
            "news": {"title": "Sports News | SkySport", "description": "The latest sports headlines from BBC Sport, The Guardian, ESPN, Sky Sports and beIN SPORTS.", "heading": "Latest sports news", "intro": "A dedicated feed of the latest headlines from trusted sports publishers."},
            "videos": {"title": "Sports Videos & Highlights | SkySport", "description": "Watch the latest sports video highlights from trusted publishers.", "heading": "Sports videos", "intro": "Video highlights and reports from across the sporting world."},
            "live": {"title": "Live Sports Scores | SkySport", "description": "Follow current live sports scores and match status from ESPN public scoreboards.", "heading": "Live scores", "intro": "Follow matches in progress with live scores and status updates."},
            "fixtures": {"title": "Upcoming Sports Fixtures | SkySport", "description": "Browse upcoming sports fixtures and event schedules for the next 14 days.", "heading": "Upcoming fixtures", "intro": "Plan ahead with upcoming fixtures and events for the next 14 days."},
        },
        "newsPageIntro": "Updated __UPDATED__ · Sources: __SOURCES__",
        "videosPageIntro": "Official highlights and publisher video reports.",
        "livePageIntro": "Scores and match status from ESPN public scoreboards.",
        "fixturesPageIntro": "Upcoming events · Times shown in UTC.",
        "exploreSection": "Explore SkySport",
        "sectionCards": {
            "news": {"title": "Latest news", "description": "Headlines from five trusted sports news sources.", "action": "Browse all news"},
            "videos": {"title": "Video highlights", "description": "Watch recent sports clips and publisher reports.", "action": "Watch videos"},
            "live": {"title": "Live scores", "description": "See which matches are in progress and follow the scores.", "action": "View live scores"},
            "fixtures": {"title": "Match schedule", "description": "Find upcoming fixtures and events for the next 14 days.", "action": "View schedule"},
        },
        "language": "Select language",
        "news": "News",
        "videos": "Videos",
        "live": "Live",
        "fixtures": "Fixtures",
        "sportsDesk": "Sports desk",
        "eyebrow": "Independent sports coverage",
        "headline": "The sports world, in focus.",
        "intro": "Headlines, highlights and match schedules from across the sporting world.",
        "topStory": "Top story",
        "latest": "Latest",
        "allNews": "All news ↓",
        "moreHeadlines": "More headlines",
        "search": "Search headlines",
        "allSports": "All sports",
        "saved": "♡ Saved",
        "saveStory": "Save story",
        "removeSaved": "Remove saved story",
        "readStory": "Read story",
        "noStories": "No stories found. Try a different search or filter.",
        "videoHighlights": "Video highlights",
        "videoDescription": "Videos open on their publisher's site unless a direct file is available.",
        "noVideos": "No video items were available from the active RSS feeds.",
        "playVideo": "Play video",
        "watchOn": "Watch on",
        "liveScores": "Live scores",
        "liveDescription": "Live matches from ESPN public scoreboards. Updates about every 15 minutes.",
        "noLive": "No matches are live at the latest update.",
        "liveNow": "LIVE",
        "upcomingFixtures": "Upcoming fixtures",
        "fixtureDescription": "Next 14 days · Times shown in UTC",
        "fixtureNote": "Fixture data is supplied by ESPN public scoreboards. Availability varies by sport and competition.",
        "noUpcoming": "No upcoming events in the next 14 days.",
        "feedUnavailable": "Public fixture feed unavailable right now.",
        "footer": "Skysport · News headlines stay in their publisher's original language. Fixture data: ESPN public scoreboards.",
        "themeLight": "Switch to light theme",
        "themeDark": "Switch to dark theme",
        "categories": {
            "All": "All sports", "Football": "Football", "Tennis": "Tennis", "Formula 1": "Formula 1",
            "Cricket": "Cricket", "Rugby": "Rugby", "Basketball": "Basketball",
            "American Football": "American Football", "Ice Hockey": "Ice Hockey", "Golf": "Golf", "Boxing & MMA": "Boxing & MMA",
            "Other": "Other", "Saved": "♡ Saved",
        },
        "sports": {"Football": "Football", "Tennis": "Tennis", "Formula 1": "Formula 1", "Basketball": "Basketball", "American Football": "American Football", "Ice Hockey": "Ice Hockey", "Cricket": "Cricket", "Rugby": "Rugby"},
    },
    "fr": {
        "title": "SkySport — Actualités sportives, scores et calendrier",
        "metaDescription": "Les dernières actualités du football, du basketball, du tennis et de la Formule 1, avec vidéos, scores en direct et calendrier.",
        "pages": {
            "home": {"title": "SkySport — Actualités sportives, scores et calendrier", "description": "Actualités, vidéos, scores en direct et calendrier sportif.", "heading": "Le sport, au cœur de l'actualité.", "intro": "Suivez l'actualité, regardez les vidéos, consultez les scores et les rencontres à venir."},
            "news": {"title": "Actualités sportives | SkySport", "description": "Les dernières actualités sportives de BBC Sport, The Guardian, ESPN, Sky Sports et beIN SPORTS.", "heading": "Dernières actualités sportives", "intro": "Les derniers titres des principaux médias sportifs."},
            "videos": {"title": "Vidéos et résumés sportifs | SkySport", "description": "Regardez les derniers résumés sportifs des médias de référence.", "heading": "Vidéos sportives", "intro": "Résumés vidéo et reportages du monde sportif."},
            "live": {"title": "Scores sportifs en direct | SkySport", "description": "Suivez les scores et l'état des matchs en direct.", "heading": "Scores en direct", "intro": "Suivez les matchs en cours avec leurs scores et leur état."},
            "fixtures": {"title": "Calendrier des rencontres sportives | SkySport", "description": "Consultez les rencontres et événements sportifs des 14 prochains jours.", "heading": "Prochaines rencontres", "intro": "Préparez-vous avec les rencontres prévues dans les 14 prochains jours."},
        },
        "newsPageIntro": "Mis à jour __UPDATED__ · Sources : __SOURCES__",
        "videosPageIntro": "Résumés et reportages vidéo des éditeurs.",
        "livePageIntro": "Scores et état des matchs via les tableaux publics d'ESPN.",
        "fixturesPageIntro": "Prochains événements · Horaires en UTC.",
        "exploreSection": "Explorer SkySport",
        "sectionCards": {
            "news": {"title": "Dernières actualités", "description": "Les titres de cinq sources sportives fiables.", "action": "Toutes les actualités"},
            "videos": {"title": "Résumés vidéo", "description": "Les dernières vidéos et reportages sportifs.", "action": "Voir les vidéos"},
            "live": {"title": "Scores en direct", "description": "Consultez les matchs en cours et leurs scores.", "action": "Voir les scores"},
            "fixtures": {"title": "Calendrier des matchs", "description": "Les rencontres et événements des 14 prochains jours.", "action": "Voir le calendrier"},
        },
        "language": "Choisir la langue",
        "news": "Actualités",
        "videos": "Vidéos",
        "live": "En direct",
        "fixtures": "Calendrier",
        "sportsDesk": "Actualités sportives",
        "eyebrow": "Le sport, en toute indépendance",
        "headline": "Toute l'actualité sportive.",
        "intro": "Actualités, résumés vidéo et calendrier des rencontres du monde entier.",
        "topStory": "À la une",
        "latest": "À suivre",
        "allNews": "Toutes les actualités ↓",
        "moreHeadlines": "Dernières actualités",
        "search": "Rechercher une actualité",
        "allSports": "Tous les sports",
        "saved": "♡ Enregistrés",
        "saveStory": "Enregistrer l'article",
        "removeSaved": "Retirer des articles enregistrés",
        "readStory": "Lire l'article",
        "noStories": "Aucun résultat. Essayez une autre recherche ou un autre filtre.",
        "videoHighlights": "Résumés vidéo",
        "videoDescription": "Les vidéos s'ouvrent sur le site de leur éditeur, sauf fichier directement disponible.",
        "noVideos": "Aucune vidéo n'est disponible dans les flux RSS actifs.",
        "playVideo": "Lire la vidéo",
        "watchOn": "Voir sur",
        "liveScores": "Scores en direct",
        "liveDescription": "Matchs en direct via les tableaux de scores publics d'ESPN. Actualisation environ toutes les 15 minutes.",
        "noLive": "Aucun match en direct lors de la dernière mise à jour.",
        "liveNow": "EN DIRECT",
        "upcomingFixtures": "Prochaines rencontres",
        "fixtureDescription": "14 prochains jours · Horaires en UTC",
        "fixtureNote": "Calendrier fourni par les tableaux de scores publics d'ESPN. La disponibilité varie selon le sport et la compétition.",
        "noUpcoming": "Aucun événement prévu dans les 14 prochains jours.",
        "feedUnavailable": "Flux public du calendrier momentanément indisponible.",
        "footer": "Skysport · Les titres restent dans la langue d'origine de leur éditeur. Calendrier : tableaux de scores publics d'ESPN.",
        "themeLight": "Passer au thème clair",
        "themeDark": "Passer au thème sombre",
        "categories": {
            "All": "Tous les sports", "Football": "Football", "Tennis": "Tennis", "Formula 1": "Formule 1",
            "Cricket": "Cricket", "Rugby": "Rugby", "Basketball": "Basket-ball",
            "American Football": "Football américain", "Ice Hockey": "Hockey sur glace", "Golf": "Golf", "Boxing & MMA": "Boxe et MMA",
            "Other": "Autres", "Saved": "♡ Enregistrés",
        },
        "sports": {"Football": "Football", "Tennis": "Tennis", "Formula 1": "Formule 1", "Basketball": "Basket-ball", "American Football": "Football américain", "Ice Hockey": "Hockey sur glace", "Cricket": "Cricket", "Rugby": "Rugby"},
    },
    "ar": {
        "title": "سكاي سبورت | أخبار الرياضة والنتائج والمباريات",
        "metaDescription": "آخر أخبار كرة القدم والسلة والتنس والفورمولا 1، مع فيديوهات ونتائج مباشرة ومواعيد المباريات من مصادر رياضية موثوقة.",
        "pages": {
            "home": {"title": "سكاي سبورت | أخبار الرياضة والنتائج والمباريات", "description": "أخبار رياضية وفيديوهات ونتائج مباشرة ومواعيد المباريات.", "heading": "عالم الرياضة في صدارة المشهد.", "intro": "تابع آخر الأخبار وشاهد الملخصات وتعرّف على النتائج والمباريات القادمة."},
            "news": {"title": "آخر الأخبار الرياضية | سكاي سبورت", "description": "آخر الأخبار الرياضية من BBC Sport وThe Guardian وESPN وSky Sports وbeIN SPORTS.", "heading": "آخر الأخبار الرياضية", "intro": "أحدث العناوين من مصادر رياضية موثوقة."},
            "videos": {"title": "فيديوهات وملخصات رياضية | سكاي سبورت", "description": "شاهد أحدث الفيديوهات والملخصات الرياضية من الناشرين.", "heading": "فيديوهات رياضية", "intro": "ملخصات ومقاطع رياضية من مختلف الرياضات."},
            "live": {"title": "النتائج الرياضية المباشرة | سكاي سبورت", "description": "تابع النتائج وحالة المباريات الرياضية المباشرة.", "heading": "النتائج المباشرة", "intro": "تابع المباريات الجارية ونتائجها وحالتها."},
            "fixtures": {"title": "مواعيد المباريات القادمة | سكاي سبورت", "description": "تعرّف على مواعيد المباريات والفعاليات الرياضية خلال الأيام الـ14 القادمة.", "heading": "المباريات القادمة", "intro": "خطط لمتابعة المباريات والفعاليات خلال الأيام الـ14 القادمة."},
        },
        "newsPageIntro": "آخر تحديث __UPDATED__ · المصادر: __SOURCES__",
        "videosPageIntro": "ملخصات وتقارير فيديو من الناشرين.",
        "livePageIntro": "النتائج وحالة المباريات من لوحات ESPN العامة.",
        "fixturesPageIntro": "المباريات القادمة · الأوقات بتوقيت UTC.",
        "exploreSection": "استكشف سكاي سبورت",
        "sectionCards": {
            "news": {"title": "آخر الأخبار", "description": "أخبار رياضية من خمسة مصادر موثوقة.", "action": "تصفح الأخبار"},
            "videos": {"title": "ملخصات الفيديو", "description": "شاهد أحدث المقاطع والتقارير الرياضية.", "action": "شاهد الفيديوهات"},
            "live": {"title": "النتائج المباشرة", "description": "تابع المباريات الجارية ونتائجها.", "action": "عرض النتائج"},
            "fixtures": {"title": "جدول المباريات", "description": "مواعيد المباريات والفعاليات خلال الأيام الـ14 القادمة.", "action": "عرض الجدول"},
        },
        "language": "اختيار اللغة",
        "news": "الأخبار",
        "videos": "الفيديوهات",
        "live": "مباشر",
        "fixtures": "المباريات",
        "sportsDesk": "أخبار الرياضة",
        "eyebrow": "تغطية رياضية مستقلة",
        "headline": "عالم الرياضة في صدارة المشهد.",
        "intro": "أخبار وملخصات ومواعيد مباريات من مختلف الرياضات حول العالم.",
        "topStory": "الخبر الأبرز",
        "latest": "أحدث الأخبار",
        "allNews": "كل الأخبار ↓",
        "moreHeadlines": "المزيد من الأخبار",
        "search": "ابحث في الأخبار",
        "allSports": "كل الرياضات",
        "saved": "♡ المحفوظات",
        "saveStory": "حفظ الخبر",
        "removeSaved": "إزالة الخبر من المحفوظات",
        "readStory": "اقرأ الخبر",
        "noStories": "لا توجد نتائج. جرّب بحثاً أو تصنيفاً آخر.",
        "videoHighlights": "ملخصات الفيديو",
        "videoDescription": "تُعرض الفيديوهات على موقع الناشر ما لم يتوفر ملف مباشر.",
        "noVideos": "لا تتوفر فيديوهات في مصادر الأخبار الحالية.",
        "playVideo": "تشغيل الفيديو",
        "watchOn": "شاهد على",
        "liveScores": "النتائج المباشرة",
        "liveDescription": "المباريات المباشرة من لوحات ESPN العامة. تُحدّث البيانات كل 15 دقيقة تقريباً.",
        "noLive": "لا توجد مباريات مباشرة وقت آخر تحديث.",
        "liveNow": "مباشر",
        "upcomingFixtures": "المباريات القادمة",
        "fixtureDescription": "الأيام الـ14 القادمة · الأوقات بتوقيت UTC",
        "fixtureNote": "بيانات المباريات من لوحات ESPN العامة، وقد يختلف توفرها حسب الرياضة والبطولة.",
        "noUpcoming": "لا توجد مباريات خلال الأيام الـ14 القادمة.",
        "feedUnavailable": "جدول المباريات العام غير متاح حالياً.",
        "footer": "سكاي سبورت · عناوين الأخبار تبقى بلغة الناشر الأصلية. بيانات المباريات من لوحات ESPN العامة.",
        "themeLight": "التبديل إلى الوضع الفاتح",
        "themeDark": "التبديل إلى الوضع الداكن",
        "categories": {
            "All": "كل الرياضات", "Football": "كرة القدم", "Tennis": "التنس", "Formula 1": "فورمولا 1",
            "Cricket": "الكريكيت", "Rugby": "الرغبي", "Basketball": "كرة السلة",
            "American Football": "كرة القدم الأمريكية", "Ice Hockey": "هوكي الجليد", "Golf": "الغولف", "Boxing & MMA": "الملاكمة والفنون القتالية",
            "Other": "أخرى", "Saved": "♡ المحفوظات",
        },
        "sports": {"Football": "كرة القدم", "Tennis": "التنس", "Formula 1": "فورمولا 1", "Basketball": "كرة السلة", "American Football": "كرة القدم الأمريكية", "Ice Hockey": "هوكي الجليد", "Cricket": "الكريكيت", "Rugby": "الرغبي"},
    },
}

TITLE_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "has", "have", "in", "is", "it", "of", "on", "or", "the", "to", "was",
    "were", "will", "with",
}


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


def image_source_url(value):
    parsed = urlparse(value)
    if parsed.hostname == "ichef.bbci.co.uk":
        return re.sub(r"(/standard/)\d+/", r"\g<1>1024/", value, count=1)
    return value


def category_for(title, description, url=""):
    text = f"{title} {description} {url}".lower()
    keywords = {
        "American Football": ("american football", "college football", "nfl", "super bowl", "touchdown", "quarterback"),
        "Basketball": ("basketball", "nba", "wnba"),
        "Ice Hockey": ("ice hockey", "nhl", "stanley cup"),
        "Golf": ("golf", "pga tour", "the open"),
        "Boxing & MMA": ("boxing", "boxer", "ufc", "mma", "knockout", "undisputed"),
        "Football": ("football", "soccer", "premier league", "champions league", "arsenal", "chelsea", "liverpool", "man city", "spurs"),
        "Tennis": ("tennis", "wimbledon", "atp", "wta"),
        "Formula 1": ("formula 1", "formula one", "f1", "grand prix"),
        "Cricket": ("cricket", "ashes", "test match", "t20"),
        "Rugby": ("rugby", "six nations"),
    }
    path = urlparse(url).path.lower()
    path_categories = (
        ("American Football", ("/american-football/", "/college-football/", "/nfl/")),
        ("Basketball", ("/basketball/", "/college-basketball/", "/nba/")),
        ("Ice Hockey", ("/hockey/", "/nhl/")),
        ("Golf", ("/golf/",)),
        ("Boxing & MMA", ("/boxing/", "/mma/", "/ufc/")),
        ("Football", ("/football/", "/soccer/")),
        ("Tennis", ("/tennis/",)),
        ("Formula 1", ("/f1/", "/formula-one/", "/motorsports-formula-1/")),
        ("Cricket", ("/cricket/",)),
        ("Rugby", ("/rugby-", "/rugby/")),
    )
    for category, paths in path_categories:
        if any(part in path for part in paths):
            return category
    for category, terms in keywords.items():
        if any(re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text) for term in terms):
            return category
    return "Other"


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
    image_candidates = []
    video_url = ""
    is_video = "/video" in urlparse(link).path.lower()
    for element in item.iter():
        element_name = local_name(element)
        if element_name in ("thumbnail", "content"):
            media_url = element.get("url", "")
            media_type = element.get("type", "").lower()
            medium = element.get("medium", "").lower()
            image_path = urlparse(media_url).path.lower()
            is_image = (
                element_name == "thumbnail"
                or medium == "image"
                or media_type.startswith("image/")
                or (
                    element_name == "content"
                    and image_path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))
                )
            )
            if medium == "video" or media_type.startswith("video/"):
                is_video = True
                if media_type == "video/mp4":
                    safe_url = safe_feed_link(media_url, feed)
                    if safe_url != feed.homepage:
                        video_url = safe_url
            if is_image and urlparse(media_url).scheme == "https":
                try:
                    width = int(element.get("width", "0"))
                except ValueError:
                    width = 0
                image_candidates.append((width, image_source_url(media_url)))
    enclosure = next((child for child in list(item) if local_name(child) == "enclosure"), None)
    if enclosure is not None:
        media_type = enclosure.get("type", "").lower()
        media_url = enclosure.get("url", "")
        is_video = is_video or media_type.startswith("video/")
        if media_type == "video/mp4":
            safe_url = safe_feed_link(media_url, feed)
            if safe_url != feed.homepage:
                video_url = safe_url
        if media_type.startswith("image/") and urlparse(media_url).scheme == "https":
            image_candidates.append((0, image_source_url(media_url)))
    if image_candidates:
        image = max(image_candidates, key=lambda candidate: candidate[0])[1]

    published = parse_published(child_text(item, {"pubdate", "published", "updated"}))
    return {
        "title": title,
        "description": description or f"Read the full report from {feed.name}.",
        "url": safe_feed_link(link, feed),
        "image": image,
        "category": category_for(title, description, link),
        "published": published,
        "source": feed.name,
        "coverage": [],
        "video": is_video,
        "video_url": video_url,
    }


def parse_feed(xml_data, feed):
    root = ET.fromstring(xml_data)
    items = [element for element in root.iter() if local_name(element) in ("item", "entry")]
    stories = [parse_story(item, feed) for item in items]
    return [story for story in stories if story]


class BeinsportsNewsParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stories = []
        self.current = None
        self.anchor_depth = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "a" and "/articles-video/" in attributes.get("href", ""):
            if self.current is not None:
                return
            self.current = {
                "url": attributes["href"],
                "titles": [],
                "images": [],
                "text": [],
            }
            self.anchor_depth = 1
            return
        if self.current is None:
            return
        if tag == "a":
            self.anchor_depth += 1
        title = clean_text(attributes.get("title", ""))
        if title:
            self.current["titles"].append(title)
        if tag == "img":
            self.current["images"].append((attributes.get("src", ""), attributes.get("srcset", "")))

    def handle_endtag(self, tag):
        if self.current is None or tag != "a":
            return
        self.anchor_depth -= 1
        if self.anchor_depth <= 0:
            self.stories.append(self.current)
            self.current = None
            self.anchor_depth = 0

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"].append(data)


def parse_beinsports_news(page_data, feed):
    parser = BeinsportsNewsParser()
    parser.feed(page_data.decode("utf-8", "replace") if isinstance(page_data, bytes) else page_data)
    stories = []
    for item in parser.stories:
        title_values = [
            value for value in item["titles"]
            if parse_event_date(value) is None
        ]
        title = title_values[0] if title_values else ""
        if not title:
            text = clean_text(" ".join(item["text"]))
            text = re.sub(r"\b\d{4}-\d{2}-\d{2}T[^\s]+\s*", "", text, count=1)
            title = text
        if not title:
            continue
        description = title_values[1] if len(title_values) > 1 else f"Read the full report from {feed.name}."
        link = safe_feed_link(urljoin(feed.homepage, item["url"]), feed)
        if link == feed.homepage:
            continue
        published_text = next((value for value in item["titles"] if parse_event_date(value)), "")
        published = parse_event_date(published_text)

        image_candidates = []
        for src, srcset in item["images"]:
            if src:
                image_candidates.append((0, src))
            for candidate in srcset.split(","):
                parts = candidate.strip().rsplit(" ", 1)
                if len(parts) != 2:
                    continue
                width = re.fullmatch(r"(\d+)w", parts[1])
                if width:
                    image_candidates.append((int(width.group(1)), parts[0]))
        image = ""
        if image_candidates:
            _, image_url = max(image_candidates, key=lambda candidate: candidate[0])
            if safe_feed_link(image_url, feed) != feed.homepage:
                image = image_url

        stories.append({
            "title": title,
            "description": description,
            "url": link,
            "image": image,
            "category": category_for(title, description, link),
            "published": published,
            "source": feed.name,
            "coverage": [],
            "video": "/video" in urlparse(link).path.lower(),
            "video_url": "",
        })
    return stories


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
            payload = fetcher(feed.url)
            items = parse_beinsports_news(payload, feed) if feed.format == "html" else parse_feed(payload, feed)
            if not items:
                raise ValueError("feed contained no usable stories")
            stories.extend(items)
            available.append(feed.name)
        except (OSError, urllib.error.URLError, ET.ParseError, ValueError) as error:
            failures.append(f"{feed.name}: {error}")
    stories.sort(key=lambda story: story["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    deduplicated = []
    for story in stories:
        match = next(
            (item for item in deduplicated if same_story(item, story)),
            None,
        )
        if match:
            if story["source"] != match["source"] and all(
                source["name"] != story["source"] for source in match["coverage"]
            ):
                match["coverage"].append({"name": story["source"], "url": story["url"]})
            continue
        deduplicated.append(story)
    representatives = []
    for source in available:
        representative = next(
            (
                story for story in deduplicated
                if story["source"] == source
                or any(coverage["name"] == source for coverage in story["coverage"])
            ),
            None,
        )
        if representative is not None and representative not in representatives:
            representatives.append(representative)
    selected = representatives[:MAX_STORIES]
    selected.extend(
        story for story in deduplicated
        if story not in representatives and len(selected) < MAX_STORIES
    )
    selected.sort(
        key=lambda story: story["published"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return selected[:MAX_STORIES], available, failures


def collect_espn_images(stories, fetcher=request_bytes):
    story_by_id = {}
    paths = set()
    for story in stories:
        if story["source"] != "ESPN" or story.get("image"):
            continue
        match = re.search(r"/id/(\d+)", story["url"])
        path = ESPN_NEWS_PATHS.get(story["category"])
        if match and path:
            story_by_id[match.group(1)] = story
            paths.add(path)

    failures = []
    for path in sorted(paths):
        url = f"{ESPN_API}/{path}/news"
        try:
            payload = json.loads(fetcher(url))
            if not isinstance(payload, dict) or not isinstance(payload.get("articles", []), list):
                raise ValueError("unexpected ESPN news response")
            for article in payload.get("articles", []):
                if not isinstance(article, dict):
                    continue
                links = article.get("links") or {}
                hrefs = [
                    link.get("href", "")
                    for link in links.values()
                    if isinstance(link, dict)
                ] if isinstance(links, dict) else []
                identifiers = {
                    match.group(1)
                    for href in hrefs
                    if (match := re.search(r"(?:/id/|[?&]storyId=)(\d+)", href))
                }
                images = article.get("images") or []
                if not isinstance(images, list):
                    continue
                candidates = []
                for image in images:
                    if not isinstance(image, dict):
                        continue
                    image_url = image.get("url", "")
                    host = (urlparse(image_url).hostname or "").lower()
                    if (
                        urlparse(image_url).scheme == "https"
                        and (host.endswith(".espncdn.com") or host == "espnmedia-cdn.akamaized.net")
                    ):
                        candidates.append((int(image.get("width", 0) or 0), image_url))
                if not candidates:
                    continue
                for identifier in identifiers:
                    story = story_by_id.get(identifier)
                    if story:
                        story["image"] = max(candidates, key=lambda candidate: candidate[0])[1]
        except (OSError, urllib.error.URLError, json.JSONDecodeError, TypeError, ValueError) as error:
            failures.append(f"ESPN images / {path}: {error}")
    return failures


def title_tokens(title):
    return {
        word for word in re.findall(r"[a-z0-9]+", title.casefold())
        if word not in TITLE_STOP_WORDS
    }


def same_story(first, second):
    if first["url"] == second["url"] and first["source"] != second["source"]:
        return True
    if first["source"] == second["source"] or first["category"] != second["category"]:
        return False
    first_tokens = title_tokens(first["title"])
    second_tokens = title_tokens(second["title"])
    shared = first_tokens & second_tokens
    combined = first_tokens | second_tokens
    return len(shared) >= 4 and len(combined) > 0 and len(shared) / len(combined) >= 0.6


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
    if start is None:
        return None
    competitions = event.get("competitions") or []
    competition_data = competitions[0] if isinstance(competitions, list) and competitions and isinstance(competitions[0], dict) else {}
    status = event.get("status") or competition_data.get("status") or {}
    status_type = status.get("type", {}) if isinstance(status, dict) else {}
    if not isinstance(status_type, dict):
        status_type = {}
    state = str(status_type.get("state", "")).lower()
    status_name = str(status_type.get("name", "")).upper()
    is_live = state in {"in", "live"} or status_name in {"STATUS_IN_PROGRESS", "STATUS_HALFTIME"}
    if (start < now and not is_live) or start > now + timedelta(days=SCHEDULE_DAYS):
        return None
    competitors = competition_data.get("competitors", [])
    if not isinstance(competitors, list) or any(not isinstance(item, dict) for item in competitors):
        competitors = []
    home_competitor = next((item for item in competitors if item.get("homeAway") == "home"), None)
    away_competitor = next((item for item in competitors if item.get("homeAway") == "away"), None)
    if not home_competitor and competitors:
        home_competitor = competitors[0]
    if not away_competitor and len(competitors) > 1:
        away_competitor = competitors[1]
    home = event_team(home_competitor or {})
    away = event_team(away_competitor or {})
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
        "is_live": is_live,
        "home_score": clean_text(str((home_competitor or {}).get("score", ""))) if is_live else "",
        "away_score": clean_text(str((away_competitor or {}).get("score", ""))) if is_live else "",
        "status_detail": clean_text(
            status_type.get("shortDetail") or status_type.get("detail") or status_type.get("description", "")
        ) if is_live else "",
    }


def collect_fixtures(fetcher=request_bytes, feeds=FIXTURE_FEEDS, now=None):
    now = now or datetime.now(timezone.utc)
    end = now + timedelta(days=SCHEDULE_DAYS)
    months = []
    year, month = now.year, now.month
    while (year, month) <= (end.year, end.month):
        months.append(f"{year}{month:02d}")
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    fixtures = []
    available_sports = set()
    failures = []
    for feed in feeds:
        for month in months:
            url = f"{ESPN_API}/{feed.path}/scoreboard?{urlencode({'dates': month, 'limit': MAX_FIXTURES_PER_FEED})}"
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
    coverage = "".join(
        f' · <a href="{html.escape(item["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(item["name"])}</a>'
        for item in story.get("coverage", [])
    )
    published = story["published"]
    date_label = published.strftime("%d %b %Y") if published else "Latest"
    iso_date = published.isoformat() if published else ""
    image_markup = (
        f'<span class="image-placeholder" data-category="{category}" aria-hidden="true">{category}</span>'
        f'<img src="{image}" alt="" loading="lazy" decoding="async">'
        if image else
        f'<span class="image-placeholder" data-category="{category}" aria-hidden="true">{category}</span>'
    )
    video_badge = '<span class="video-badge">VIDEO</span>' if story["video"] else ""
    return f'''<article class="story-card" data-category="{category}">
      <a class="story-image" href="{link}" target="_blank" rel="noopener noreferrer" tabindex="-1" aria-hidden="true">{image_markup}<span class="category" data-category="{category}">{category}</span>{video_badge}</a>
      <div class="story-body"><div class="story-meta"><span>{source}{coverage}</span><time datetime="{html.escape(iso_date, quote=True)}">{date_label}</time><button class="save-button" type="button" aria-label="Save story" title="Save story">♡</button></div>
        <h3><a href="{link}" target="_blank" rel="noopener noreferrer">{title}</a></h3><p>{description}</p>
        <a class="read-more" href="{link}" target="_blank" rel="noopener noreferrer"><span data-i18n="readStory">Read story</span> <span aria-hidden="true">↗</span></a>
      </div>
    </article>'''


def render_video(story):
    title = html.escape(story["title"])
    link = html.escape(story["url"], quote=True)
    image = html.escape(story["image"], quote=True)
    source = html.escape(story["source"])
    video_url = html.escape(story.get("video_url", ""), quote=True)
    if video_url:
        poster = f' poster="{image}"' if image else ""
        player = f'<video controls preload="none"{poster}><source src="{video_url}" type="video/mp4">Your browser does not support video playback.</video>'
        action = '<span data-i18n="playVideo">Play video</span>'
    else:
        cover = f'<img src="{image}" alt="" loading="lazy">' if image else '<span class="video-placeholder" aria-hidden="true">▶</span>'
        player = f'<a class="video-cover" href="{link}" target="_blank" rel="noopener noreferrer">{cover}<span class="play-button" aria-hidden="true">▶</span></a>'
        action = f'<span data-i18n="watchOn">Watch on</span> {source} ↗'
    return f'''<article class="video-card">{player}
      <div class="video-info"><span>{source} · VIDEO</span><h3><a href="{link}" target="_blank" rel="noopener noreferrer">{title}</a></h3><a class="read-more" href="{link}" target="_blank" rel="noopener noreferrer">{action}</a></div>
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
      <div class="fixture-meta"><span class="sport-label" data-sport="{sport}">{sport}</span><span>{competition}</span></div>
      <div class="fixture-match">{matchup}</div>
      <div class="fixture-footer"><time datetime="{start.isoformat()}">{start.strftime("%a, %d %b · %H:%M")} UTC</time><a href="{link}" target="_blank" rel="noopener noreferrer">ESPN ↗</a></div>
    </article>'''


def render_live_fixture(fixture):
    home = html.escape(fixture["home"])
    away = html.escape(fixture["away"])
    sport = html.escape(fixture["sport"])
    competition = html.escape(fixture["competition"])
    link = html.escape(fixture["url"], quote=True)
    home_score = html.escape(fixture.get("home_score", ""))
    away_score = html.escape(fixture.get("away_score", ""))
    status = html.escape(fixture.get("status_detail", ""))
    if away:
        score = (
            f'<strong>{home}</strong><span class="live-score">{home_score or "–"} : {away_score or "–"}</span>'
            f'<strong>{away}</strong>'
        )
    else:
        score = f'<strong class="event-name">{home}</strong>'
    status_markup = f'<span class="live-detail">{status}</span>' if status else ""
    return f'''<article class="fixture-card live-card" data-sport="{sport}">
      <div class="fixture-meta"><span class="sport-label" data-sport="{sport}">{sport}</span><span>{competition}</span><span class="live-badge" data-i18n="liveNow">LIVE</span></div>
      <div class="fixture-match live-match">{score}</div>
      <div class="fixture-footer">{status_markup}<a href="{link}" target="_blank" rel="noopener noreferrer">ESPN ↗</a></div>
    </article>'''


def render_live(fixtures):
    live_fixtures = [fixture for fixture in fixtures if fixture.get("is_live")]
    if not live_fixtures:
        return '<p class="section-empty" data-i18n="noLive">No matches are live at the latest update.</p>'
    return "\n".join(render_live_fixture(fixture) for fixture in live_fixtures)


def render_schedule(fixtures, available_sports):
    fixtures = [fixture for fixture in fixtures if not fixture.get("is_live")]
    sports_with_events = {fixture["sport"] for fixture in fixtures}
    cards = [render_fixture(match) for match in fixtures]
    for sport in SPORTS:
        if sport in sports_with_events:
            continue
        status = "No upcoming events in the next 14 days." if sport in available_sports else "Public fixture feed unavailable right now."
        status_key = "noUpcoming" if sport in available_sports else "feedUnavailable"
        cards.append(f'<article class="schedule-empty"><strong class="sport-label" data-sport="{html.escape(sport, quote=True)}">{html.escape(sport)}</strong><span data-i18n="{status_key}">{html.escape(status)}</span></article>')
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
.nav{min-height:74px;display:flex;align-items:center;justify-content:space-between;gap:20px}.brand{display:flex;align-items:center;gap:11px;text-decoration:none}.brand-mark{display:grid;place-items:center;width:42px;height:42px;border-radius:13px;background:linear-gradient(135deg,var(--accent),#ff8b42);font-size:22px;font-weight:900}.brand-name{color:#fff;font-size:1.13rem;font-weight:850;letter-spacing:.13em;text-transform:uppercase}.nav-links{display:flex;gap:24px;color:#e3eaf5;font-size:.88rem;font-weight:650}.nav-links a{text-decoration:none}.nav-links a:hover{color:#ffbcb6}.nav-right{display:flex;align-items:center;gap:14px}.desk-label{color:#e4ffec;font-size:.73rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase}.desk-label:before{content:"";display:inline-block;width:8px;height:8px;margin-right:8px;border-radius:50%;background:var(--green)}.theme-button{width:39px;height:39px;border:1px solid #ffffff50;border-radius:50%;color:#fff;background:#07101d75;cursor:pointer}.language-select{min-height:36px;padding:5px 9px;border:1px solid #ffffff50;border-radius:4px;color:#fff;background:#07101d75;font-size:.78rem}
.hero{padding:55px 0 62px;color:#fff}.eyebrow{color:#ffbcb6;text-transform:uppercase;letter-spacing:.17em;font-weight:850;font-size:.73rem}.hero h1{max-width:780px;margin:12px 0;font-size:clamp(2.5rem,6.1vw,4.7rem);line-height:1.01;letter-spacing:-.055em}.hero p{max-width:620px;margin:0;color:#d5deeb;font-size:1.04rem}.hero-stats{display:flex;gap:22px;margin-top:27px;color:#e3eaf5;font-size:.78rem}.hero-stats strong{color:#fff;font-size:1rem}
.ticker{background:var(--accent);color:#fff}.ticker .wrap{min-height:40px;display:flex;align-items:center;gap:12px;font-size:.8rem;font-weight:750}.ticker-label{border:1px solid #ffffff75;padding:2px 8px;border-radius:4px;font-size:.68rem;letter-spacing:.08em}
.section-head{display:flex;align-items:end;justify-content:space-between;gap:18px;flex-wrap:wrap;padding:33px 0 16px}.section-head h2{margin:0;font-size:1.6rem;letter-spacing:-.025em}.section-head p{margin:3px 0 0;color:var(--muted);font-size:.82rem}.search{width:min(330px,100%);padding:11px 14px;color:var(--text);background:var(--surface);border:1px solid var(--line);border-radius:11px;outline:none}.search:focus{border-color:var(--accent);box-shadow:0 0 0 3px #ff493d25}
.filters{display:flex;gap:8px;overflow-x:auto;padding:0 0 19px}.filter{flex:none;border:1px solid var(--line);border-radius:999px;padding:8px 14px;color:var(--muted);background:var(--surface);font-size:.82rem;font-weight:650;cursor:pointer}.filter:hover,.filter.active{color:var(--text);border-color:#ff493d88;background:#ff493d1c}
.news-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;padding-bottom:24px}.story-card{overflow:hidden;background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:0 12px 32px #00000018;transition:transform .2s,border-color .2s}.story-card:hover{transform:translateY(-3px);border-color:#ff493d70}.story-image{display:block;position:relative;aspect-ratio:16/9;overflow:hidden;background:var(--surface2)}.story-image img{position:absolute;inset:0;width:100%;height:100%;display:block;object-fit:cover;object-position:center;transition:transform .35s}.story-card:hover .story-image img{transform:scale(1.035)}.image-placeholder{position:absolute;inset:0;display:grid;place-items:center;width:100%;height:100%;padding:20px;color:#71829a;font-size:.72rem;font-weight:900;letter-spacing:.18em;text-align:center;text-transform:uppercase;background:radial-gradient(ellipse at 75% 15%,#c9152b22,transparent 45%),linear-gradient(135deg,var(--surface2),var(--surface))}.category{position:absolute;left:12px;bottom:12px;padding:4px 9px;border-radius:6px;background:var(--accent);color:#fff;font-size:.66rem;font-weight:800;text-transform:uppercase}.video-badge{position:absolute;top:11px;right:11px;padding:4px 7px;border-radius:4px;background:#07101dcc;color:#fff;font-size:.62rem;font-weight:850;letter-spacing:.08em}.story-body{padding:15px 16px 17px}.story-meta{display:flex;align-items:center;gap:9px;color:#ff796f;font-size:.64rem;letter-spacing:.055em;font-weight:850}.story-meta a{color:inherit;text-decoration:underline;text-underline-offset:2px}.story-meta time{margin-left:auto;color:var(--muted);letter-spacing:0;font-weight:500;white-space:nowrap}.save-button{border:0;padding:0 2px;color:var(--muted);background:transparent;font-size:1.35rem;line-height:1;cursor:pointer}.save-button.saved,.save-button:hover{color:var(--accent)}.story-body h2,.story-body h3{margin:11px 0 7px;font-size:1.08rem;line-height:1.4}.story-body h2 a,.story-body h3 a,.video-info h3 a{text-decoration:none}.story-body h2 a:hover,.story-body h3 a:hover,.video-info h3 a:hover{color:#ff796f}.story-body p{margin:0;color:var(--muted);font-size:.86rem;line-height:1.6}.read-more{display:inline-block;margin-top:11px;color:#ff796f;font-size:.8rem;font-weight:750;text-decoration:none}.read-more:hover{text-decoration:underline}.empty-state{grid-column:1/-1;padding:30px;text-align:center;color:var(--muted);border:1px dashed var(--line);border-radius:14px}
.content-section{padding:12px 0 29px}.section-title{display:flex;align-items:end;justify-content:space-between;gap:12px;margin-bottom:15px}.section-title h2{margin:0;font-size:1.55rem}.section-title p{margin:0;color:var(--muted);font-size:.8rem}.video-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.video-card{overflow:hidden;background:var(--surface);border:1px solid var(--line);border-radius:15px}.video-cover,.video-card>video{display:block;position:relative;width:100%;aspect-ratio:16/9;overflow:hidden;background:var(--surface2)}.video-cover img{width:100%;height:100%;object-fit:cover}.video-card>video{object-fit:contain}.video-placeholder{display:grid;place-items:center;width:100%;height:100%;color:#ff796f;font-size:2rem}.play-button{position:absolute;left:50%;top:50%;display:grid;place-items:center;width:46px;height:46px;border-radius:50%;color:#fff;background:var(--accent);box-shadow:0 5px 20px #0008;transform:translate(-50%,-50%);font-size:.92rem}.video-info{padding:12px 15px 15px}.video-info>span{color:#ff796f;font-size:.65rem;font-weight:850;letter-spacing:.07em}.video-info h3{margin:5px 0 0;font-size:.98rem;line-height:1.4}.section-empty{padding:25px;color:var(--muted);background:var(--surface);border:1px dashed var(--line);border-radius:13px;text-align:center}
.schedule-wrap{margin:4px 0 38px;padding:20px;border:1px solid var(--line);border-radius:18px;background:linear-gradient(135deg,var(--surface),var(--bg))}.schedule-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.fixture-card,.schedule-empty{padding:15px;background:var(--surface);border:1px solid var(--line);border-radius:12px}.fixture-meta{display:flex;justify-content:space-between;gap:8px;color:#ff796f;font-size:.64rem;font-weight:850;letter-spacing:.045em;text-transform:uppercase}.fixture-match{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:17px 0;font-size:.9rem}.fixture-match strong{flex:1}.fixture-match strong:last-child{text-align:right}.versus{color:var(--muted);font-size:.65rem;font-weight:800}.fixture-footer{display:flex;justify-content:space-between;gap:8px;padding-top:10px;border-top:1px solid var(--line);color:var(--muted);font-size:.7rem}.fixture-footer a{color:var(--muted);text-decoration:none}.fixture-footer a:hover{color:var(--text)}.schedule-empty{display:flex;flex-direction:column;gap:4px;color:var(--muted);font-size:.77rem}.schedule-empty strong{color:var(--text);font-size:.9rem}.schedule-note{margin:10px 0 0;color:var(--muted);font-size:.74rem}.live-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.live-card{border-color:#c9152b55}.live-badge{padding:2px 6px;border-radius:3px;background:var(--accent);color:#fff;letter-spacing:.04em}.live-match{align-items:center}.live-match strong{font-size:.84rem}.live-score{white-space:nowrap;color:var(--accent);font-size:1.02rem;font-weight:900;font-variant-numeric:tabular-nums}.live-detail{font-weight:750}.live-card .fixture-footer{align-items:center}
.fixture-match .event-name{flex:none;text-align:left!important}.mobile-nav{display:none}.visually-hidden{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
footer{border-top:1px solid var(--line);padding:22px 0 32px;color:var(--muted);font-size:.8rem;text-align:center}[hidden]{display:none!important}
@media(max-width:900px){.news-grid,.video-grid,.schedule-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.nav-links{gap:14px}}
@media(max-width:650px){body{padding-bottom:68px}.wrap{width:min(100% - 28px,1200px)}.nav{min-height:65px;padding:9px 0}.nav-links{display:none}.mobile-nav{position:fixed;z-index:30;right:0;bottom:0;left:0;display:flex;justify-content:space-around;gap:8px;padding:9px 14px calc(9px + env(safe-area-inset-bottom));border-top:1px solid var(--line);background:var(--surface);box-shadow:0 -8px 24px #0003}.mobile-nav a{flex:1;padding:5px;color:var(--text);font-size:.82rem;font-weight:750;text-align:center;text-decoration:none}.mobile-nav a:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:5px}.desk-label{display:none}.hero{padding:42px 0 48px}.hero-stats{gap:14px;flex-wrap:wrap}.section-head{align-items:stretch}.search{width:100%}.news-grid,.video-grid,.schedule-grid{grid-template-columns:1fr;gap:13px}.story-card{display:grid;grid-template-columns:112px minmax(0,1fr)}.story-image{height:100%;min-height:164px;aspect-ratio:auto}.story-body{padding:11px}.story-body h3{font-size:.96rem;margin:8px 0 5px}.story-body p{font-size:.78rem;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.story-meta{font-size:.56rem;gap:5px}.read-more{margin-top:7px}.schedule-wrap{padding:14px}.fixture-match{font-size:.86rem}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;transition:none!important}}

/* Editorial magazine treatment inspired by sports and industry news layouts. */
:root{color-scheme:light;--bg:#fff;--surface:#fff;--surface2:#f2f4f6;--text:#111820;--muted:#66717d;--accent:#c9152b;--line:#dfe3e7;--green:#177b50}
:root.dark{color-scheme:dark;--bg:#101820;--surface:#17222d;--surface2:#22313e;--text:#f4f7fc;--muted:#b0bdc9;--accent:#f05260;--line:#ffffff22}
body{font-family:Arial,Helvetica,sans-serif}
.wrap{width:min(1180px,calc(100% - 40px))}
.masthead{background:var(--surface);border-bottom:1px solid var(--line)}
.nav{min-height:66px}
.brand-mark{width:35px;height:35px;border-radius:3px;background:var(--accent);font-size:19px}
.brand-name{color:var(--text);font-size:1.35rem;letter-spacing:-.06em}
.nav-links{color:var(--text);font-size:.82rem;text-transform:uppercase;letter-spacing:.04em}
.nav-links a:hover{color:var(--accent)}
.theme-button{border-color:var(--line);color:var(--text);background:var(--surface2)}
.desk-label{color:var(--muted)}
.hero{padding:18px 0 22px;color:var(--text)}
.eyebrow{color:var(--accent);font-size:.67rem}
.hero h1{max-width:none;margin:4px 0;font-size:clamp(1.35rem,3vw,2rem);line-height:1.2;letter-spacing:-.035em}
.hero p{color:var(--muted);font-size:.9rem}
.hero-stats{display:none}
.ticker{background:var(--surface);color:var(--muted);border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.ticker .wrap{min-height:36px;overflow:hidden;font-size:.7rem;letter-spacing:.06em;text-transform:uppercase}
.ticker-label{border:0;border-radius:0;padding:0;color:var(--accent);font-weight:850}
.ticker-label,.ticker .wrap>span:last-child{flex:none;white-space:nowrap}
.top-stories{display:grid;grid-template-columns:minmax(0,1.8fr) minmax(260px,1fr);gap:28px;padding:30px 0 24px;border-bottom:1px solid var(--line)}
.section-kicker{margin:0 0 10px;color:var(--accent);font-size:.7rem;font-weight:850;letter-spacing:.09em;text-transform:uppercase}
.lead-story{display:grid;grid-template-columns:1.1fr 1fr;align-items:stretch;overflow:hidden;border:1px solid var(--line);border-radius:3px;background:var(--surface)}
.lead-story .story-image{height:100%;min-height:300px;aspect-ratio:auto}
.lead-story .story-body{align-self:center;padding:clamp(18px,3vw,34px)}
.lead-story .story-body h3{margin:12px 0;font-family:Georgia,serif;font-size:clamp(1.45rem,3vw,2.25rem);line-height:1.14;letter-spacing:-.025em}
.lead-story .story-body p{font-size:.94rem}
.latest-panel{border:1px solid var(--line);border-radius:3px;background:var(--surface)}
.latest-heading{display:flex;align-items:center;justify-content:space-between;padding:14px 16px;border-bottom:1px solid var(--line)}
.latest-heading h2{margin:0;font-family:Georgia,serif;font-size:1.28rem}
.latest-heading a{color:var(--accent);font-size:.76rem;font-weight:750;text-decoration:none}
.latest-list{padding:0 16px}
.latest-story{display:block;overflow:visible;border:0;border-bottom:1px solid var(--line);border-radius:0;box-shadow:none;background:transparent}
.latest-story:last-child{border-bottom:0}
.latest-story .story-image,.latest-story .story-body p,.latest-story .read-more,.latest-story .save-button{display:none}
.latest-story .story-body{padding:11px 0}
.latest-story .story-meta{justify-content:space-between;color:var(--muted);font-size:.62rem}
.latest-story .story-meta time{margin-left:auto}
.latest-story .story-body h3{margin:4px 0 0;font-family:Georgia,serif;font-size:.97rem;line-height:1.3}
.latest-story .story-body h3 a:hover{color:var(--accent)}
.latest-story:before{content:attr(data-category);display:block;padding-top:10px;color:var(--accent);font-size:.58rem;font-weight:850;letter-spacing:.07em;text-transform:uppercase}
.section-head{padding:30px 0 13px;border-bottom:1px solid var(--line)}
.section-head h2,.section-title h2{font-family:Georgia,serif}
.section-head p{font-size:.75rem}
.search{border-radius:3px;background:var(--surface);border-color:var(--line)}
.filter{border-radius:3px;background:var(--surface);border-color:var(--line)}
.filter:hover,.filter.active{color:var(--accent);border-color:var(--accent);background:transparent}
.news-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:0 22px;padding-bottom:32px}
.news-grid>.story-card{display:block;overflow:visible;border:0;border-bottom:1px solid var(--line);border-radius:0;box-shadow:none;background:transparent}
.news-grid>.story-card:hover{transform:none;border-color:var(--line)}
.news-grid>.story-card .story-image{aspect-ratio:16/9}
.news-grid>.story-card .story-body{padding:12px 0 18px}
.news-grid>.story-card .story-body h3{font-family:Georgia,serif;font-size:1.2rem;line-height:1.25}
.news-grid>.story-card .story-body p{font-size:.84rem}
.story-meta{font-size:.62rem}
.story-body h3 a:hover,.read-more{color:var(--accent)}
.video-card,.fixture-card,.schedule-empty{border-radius:3px;box-shadow:none}
.schedule-wrap{border-radius:3px;background:var(--surface2)}
.language-select{border-color:var(--line);color:var(--text);background:var(--surface);cursor:pointer}
.language-select option{color:var(--text);background:var(--surface)}
html[dir=rtl] body{text-align:right}
html[dir=rtl] .nav-links,html[dir=rtl] .nav-right{direction:rtl}
html[dir=rtl] .desk-label:before{margin-right:0;margin-left:8px}
html[dir=rtl] .latest-story .story-meta{flex-direction:row-reverse}
html[dir=rtl] .latest-story .story-meta time{margin-right:auto;margin-left:0}
html[dir=rtl] .category{right:12px;left:auto}
html[dir=rtl] .story-meta time{margin-right:auto;margin-left:0}
html[dir=rtl] .fixture-match strong:last-child{text-align:left}
html[dir=rtl] .fixture-match .event-name{text-align:right!important}
html[dir=rtl] .fixture-footer{direction:rtl}
footer{background:var(--surface);border-color:var(--line)}
@media(max-width:900px){.top-stories{grid-template-columns:minmax(0,1.35fr) minmax(230px,1fr);gap:18px}.lead-story{grid-template-columns:1fr}.lead-story .story-image{min-height:220px}.news-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.live-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:650px){.wrap{width:min(100% - 28px,1180px)}.nav{min-height:58px;gap:8px}.brand-name{font-size:1.2rem}.nav-right{gap:7px}.language-select{max-width:76px;padding:4px}.hero{padding:13px 0 17px}.hero p{font-size:.82rem}.top-stories{grid-template-columns:1fr;gap:14px;padding:18px 0}.lead-story{grid-template-columns:1fr}.lead-story .story-image{height:auto;min-height:0;aspect-ratio:16/9}.lead-story .story-body{padding:17px}.lead-story .story-body h3{font-size:1.55rem}.latest-list{padding:0 14px}.section-head{padding:24px 0 12px}.news-grid{grid-template-columns:1fr;gap:0}.news-grid>.story-card{display:block}.news-grid>.story-card .story-image{height:auto;min-height:0;aspect-ratio:16/9}.news-grid>.story-card .story-body{padding:11px 0 16px}.news-grid>.story-card .story-body h3{font-size:1.08rem}.news-grid>.story-card .story-body p{display:block;overflow:visible}.filters{padding-bottom:14px}.mobile-nav{background:var(--surface);border-color:var(--line)}.mobile-nav a{font-size:.74rem}.live-grid{grid-template-columns:1fr}}
.nav-links a[aria-current="page"]{color:#ffbcb6;text-decoration:underline;text-decoration-color:var(--accent);text-underline-offset:8px}
.hero-stats[hidden]{display:none}
.page-section-title{padding:32px 0 8px}
.page-section-title h2,.home-sections>h2{font-family:Georgia,serif;font-size:1.8rem;letter-spacing:-.03em}
.home-sections,.home-latest{padding:28px 0}
.section-card-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
.section-card{position:relative;display:flex;min-height:196px;flex-direction:column;align-items:flex-start;justify-content:flex-end;gap:9px;padding:20px;border:1px solid var(--line);border-radius:16px;background:linear-gradient(145deg,var(--surface),var(--bg));color:var(--text);text-decoration:none;box-shadow:0 10px 28px #00000012;transition:transform .2s,border-color .2s}
.section-card:hover{transform:translateY(-3px);border-color:#ff493d88}
.section-card-icon{position:absolute;top:17px;left:19px;color:var(--accent);font-size:1.7rem;font-weight:900}
.section-card h3{margin:0;font-family:Georgia,serif;font-size:1.24rem}
.section-card p{margin:0;color:var(--muted);font-size:.84rem;line-height:1.5}
.section-card-action{color:#ff796f;font-size:.8rem;font-weight:800}
.home-story-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.home-story .story-image{aspect-ratio:16/9}
.home-latest .section-title{align-items:center}
.home-latest .section-title>a{white-space:nowrap}
@media(max-width:900px){.section-card-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.home-story-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:650px){.section-card-grid,.home-story-grid{grid-template-columns:1fr}.section-card{min-height:150px}.section-card-icon{font-size:1.4rem}.home-story .story-image{height:auto;min-height:0;aspect-ratio:16/9}.home-latest .section-title{align-items:flex-start}}
.ticker .wrap{min-width:0}
.ticker-headline{min-width:0;overflow:hidden;color:var(--text);text-overflow:ellipsis;text-decoration:none;white-space:nowrap}
.ticker-headline:hover{text-decoration:underline;text-underline-offset:3px}
.section-card:focus-visible,.ticker-headline:focus-visible,.mobile-nav a:focus-visible{outline:3px solid var(--accent);outline-offset:3px}
@media(max-width:650px){
  body{padding-bottom:78px}
  .theme-button,.language-select{min-width:44px;min-height:44px}
  .language-select{max-width:84px}
  .mobile-nav{min-height:70px;align-items:center;padding-top:8px}
  .mobile-nav a{min-height:44px;display:grid;place-items:center;padding:6px 3px}
  .filter{min-height:44px}
  .section-card{min-height:144px}
  .story-card,.fixture-card,.video-card{min-width:0}
  .story-body,.video-info{min-width:0}
  .story-meta{flex-wrap:wrap}
}
@media(max-width:360px){
  .wrap{width:calc(100% - 24px)}
  .brand-name{font-size:1.08rem}
  .nav-right{gap:4px}
  .section-card-grid{grid-template-columns:1fr}
}
</style>
"""


def build_page(
    stories_html,
    videos_html,
    fixtures_html,
    updated,
    news_sources,
    fixture_status,
    live_html="",
    stories=None,
    page_kind="home",
):
    if page_kind not in PAGE_FILES:
        raise ValueError(f"Unknown page kind: {page_kind}")
    source_count = 0 if news_sources == "No RSS source available" else len(news_sources.split(", "))
    page_url = SITE_URL if page_kind == "home" else urljoin(SITE_URL, PAGE_FILES[page_kind])
    english_page = TRANSLATIONS["en"]["pages"][page_kind]
    story_list_schema = {
        "@id": f"{page_url}#news-list",
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": english_page["heading"],
        "numberOfItems": sum(
            1 for story in stories or [] if story.get("url", "").startswith("https://")
        ),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": position,
                "name": story["title"],
                "url": story["url"],
            }
            for position, story in enumerate(stories or [], start=1)
            if story.get("url", "").startswith("https://")
        ],
    }
    if page_kind != "news":
        story_list_schema = {}
    website_schema = {
        "@type": "WebSite",
        "@id": f"{SITE_URL}#website",
        "name": "SkySport",
        "url": SITE_URL,
        "description": "Sports news, videos, live scores and fixtures from trusted publishers.",
        "inLanguage": ["en", "fr", "ar"],
        "publisher": {"@type": "Organization", "name": "SkySport", "url": SITE_URL},
    }
    breadcrumb_items = [{
        "@type": "ListItem",
        "position": 1,
        "name": "Home",
        "item": SITE_URL,
    }]
    if page_kind != "home":
        breadcrumb_items.append({
            "@type": "ListItem",
            "position": 2,
            "name": english_page["heading"],
            "item": page_url,
        })
    page_schema = {
        "@type": "CollectionPage" if page_kind in {"news", "videos", "fixtures"} else "WebPage",
        "@id": f"{page_url}#webpage",
        "url": page_url,
        "name": english_page["title"],
        "description": english_page["description"],
        "inLanguage": "en",
        "isPartOf": {"@id": f"{SITE_URL}#website"},
        "breadcrumb": {"@id": f"{page_url}#breadcrumb"},
    }
    if page_kind == "news":
        page_schema["mainEntity"] = {"@id": story_list_schema["@id"]}
    structured_data = {"@context": "https://schema.org", "@graph": [
        website_schema,
        page_schema,
        {
            "@type": "BreadcrumbList",
            "@id": f"{page_url}#breadcrumb",
            "itemListElement": breadcrumb_items,
        },
    ]}
    if story_list_schema:
        structured_data["@graph"].append(story_list_schema)
    structured_data_json = json.dumps(structured_data, ensure_ascii=False).replace("<", "\\u003c")
    story_cards = re.findall(r'<article\b[^>]*class="story-card"[^>]*>.*?</article>', stories_html, re.DOTALL)
    page_intro = {
        "news": "newsPageIntro",
        "videos": "videosPageIntro",
        "live": "livePageIntro",
        "fixtures": "fixturesPageIntro",
    }.get(page_kind, "intro")
    if page_kind == "news":
        page_content = f'''<section class="section-head"><div><h2 data-i18n="moreHeadlines">{english_page["heading"]}</h2><p data-i18n="{page_intro}">{TRANSLATIONS["en"]["newsPageIntro"].replace("__UPDATED__", html.escape(updated)).replace("__SOURCES__", html.escape(news_sources))}</p></div><input class="search" id="search" type="search" placeholder="Search headlines…" aria-label="Search headlines" data-i18n-placeholder="search"></section>
          <nav class="filters" aria-label="Filter headlines by sport">@@FILTERS@@</nav>
          <div class="news-grid" id="news-grid">{stories_html or '<p class="empty-state">Headlines are temporarily unavailable.</p>'}<p class="empty-state" id="empty-state" hidden data-i18n="noStories">No stories found. Try a different search or filter.</p></div>'''
    elif page_kind == "videos":
        page_content = f'''<section class="section-title page-section-title"><div><h2 data-i18n="videoHighlights">{english_page["heading"]}</h2><p data-i18n="{page_intro}">{TRANSLATIONS["en"][page_intro]}</p></div></section><div class="video-grid">@@VIDEOS@@</div>'''
    elif page_kind == "live":
        page_content = f'''<section class="section-title page-section-title"><div><h2 data-i18n="liveScores">{english_page["heading"]}</h2><p data-i18n="{page_intro}">{TRANSLATIONS["en"][page_intro]}</p></div></section><div class="schedule-wrap"><div class="live-grid">@@LIVE@@</div></div>'''
    elif page_kind == "fixtures":
        page_content = f'''<section class="section-title page-section-title"><div><h2 data-i18n="upcomingFixtures">{english_page["heading"]}</h2><p data-i18n="{page_intro}">{TRANSLATIONS["en"][page_intro]}</p></div></section><div class="schedule-wrap"><div class="schedule-grid">@@FIXTURES@@</div><p class="schedule-note">@@FIXTURE_STATUS@@ <span data-i18n="fixtureNote">{TRANSLATIONS["en"]["fixtureNote"]}</span></p></div>'''
    else:
        story_preview = "".join(
            story.replace('class="story-card"', 'class="story-card home-story"', 1)
            for story in story_cards[:3]
        ) or '<p class="section-empty">Latest headlines will appear after the next update.</p>'
        story_preview = re.sub(
            r'loading="lazy" decoding="async"',
            'loading="eager" fetchpriority="high" decoding="async"',
            story_preview,
            count=1,
        )
        page_content = f'''<section class="home-sections" aria-labelledby="explore-heading"><h2 id="explore-heading" data-i18n="exploreSection">Explore SkySport</h2><div class="section-card-grid">@@SECTION_CARDS@@</div></section>
          <section class="home-latest"><div class="section-title"><div><h2 data-i18n="latest">{TRANSLATIONS["en"]["latest"]}</h2><p>{html.escape(updated)} · {html.escape(news_sources)}</p></div><a class="read-more" href="news.html" data-i18n="allNews">Browse all news</a></div><div class="home-story-grid">{story_preview}</div></section>'''
    top_story = (stories or [None])[0]
    if top_story:
        ticker_markup = (
            f'<a class="ticker-headline" href="{html.escape(top_story["url"], quote=True)}" '
            f'target="_blank" rel="noopener noreferrer">{html.escape(top_story["title"])}</a>'
        )
        ticker_label = '<span class="ticker-label" data-i18n="topStory">Top story</span>'
    else:
        ticker_markup = '<span>Football · Tennis · Formula 1 · Cricket · Rugby · Basketball · American football · Ice hockey · Golf · Boxing &amp; MMA</span>'
        ticker_label = '<span class="ticker-label" data-i18n="sportsDesk">SPORTS DESK</span>'
    section_cards = "".join(
        f'<a class="section-card" href="{PAGE_FILES[key]}" data-section-card="{key}"><span class="section-card-icon" aria-hidden="true">{icon}</span><h3 data-section-copy="{key}.title">{copy["title"]}</h3><p data-section-copy="{key}.description">{copy["description"]}</p><span class="section-card-action" data-section-copy="{key}.action">{copy["action"]} ↗</span></a>'
        for key, icon in (("news", "N"), ("videos", "▶"), ("live", "●"), ("fixtures", "▦"))
        for copy in (TRANSLATIONS["en"]["sectionCards"][key],)
    )
    page = """<!doctype html>
<html lang="en" dir="ltr">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="@@PAGE_DESCRIPTION@@">
  <meta name="robots" content="index, follow, max-image-preview:large">
  <link rel="canonical" href="@@PAGE_URL@@">
  <meta property="og:type" content="website"><meta property="og:site_name" content="SkySport">
  <meta property="og:url" content="@@PAGE_URL@@">
  <meta property="og:title" content="@@PAGE_TITLE@@">
  <meta property="og:description" content="@@PAGE_DESCRIPTION@@">
  <meta property="og:image" content="https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&amp;fit=crop&amp;w=1200&amp;q=80">
  <meta property="og:image:alt" content="Football match under stadium lights">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="@@PAGE_TITLE@@">
  <meta name="twitter:description" content="@@PAGE_DESCRIPTION@@">
  <meta name="twitter:image" content="https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&amp;fit=crop&amp;w=1200&amp;q=80">
  <meta name="twitter:image:alt" content="Football match under stadium lights">
  <meta name="theme-color" content="#081321"><title>@@PAGE_TITLE@@</title>
  <script type="application/ld+json">@@STRUCTURED_DATA@@</script>
@@STYLE@@
  </head>
<body>
  <header class="masthead"><div class="wrap">
    <nav class="nav" aria-label="Main navigation"><a class="brand" href="index.html"><span class="brand-mark" aria-hidden="true">S</span><span class="brand-name">Skysport</span></a>
      <div class="nav-links"><a href="news.html" data-i18n="news" data-page-link="news" @@NAV_NEWS@@>News</a><a href="videos.html" data-i18n="videos" data-page-link="videos" @@NAV_VIDEOS@@>Videos</a><a href="live.html" data-i18n="live" data-page-link="live" @@NAV_LIVE@@>Live</a><a href="fixtures.html" data-i18n="fixtures" data-page-link="fixtures" @@NAV_FIXTURES@@>Fixtures</a></div>
      <div class="nav-right"><span class="desk-label" data-i18n="sportsDesk">Sports desk</span><label class="visually-hidden" for="language-toggle" data-i18n="language">Select language</label><select class="language-select" id="language-toggle" aria-label="Select language"><option value="en">English</option><option value="fr">Français</option><option value="ar">العربية</option></select><button class="theme-button" id="theme-toggle" type="button" aria-label="Switch to dark theme" title="Switch theme">☼</button></div>
    </nav>
    <section class="hero"><span class="eyebrow" data-i18n="eyebrow">Independent sports coverage</span><h1 data-page-heading>@@PAGE_HEADING@@</h1><p data-page-intro>@@PAGE_INTRO@@</p>
      <div class="hero-stats" @@HOME_STATS_HIDDEN@@><span><strong>10</strong> sports</span><span><strong>@@SOURCE_COUNT@@</strong> news desks</span><span><strong>14 days</strong> fixture window</span></div>
    </section>
  </div></header>
  <nav class="mobile-nav" aria-label="Quick section navigation"><a href="news.html" data-i18n="news" data-page-link="news" @@NAV_NEWS@@>News</a><a href="videos.html" data-i18n="videos" data-page-link="videos" @@NAV_VIDEOS@@>Videos</a><a href="live.html" data-i18n="live" data-page-link="live" @@NAV_LIVE@@>Live</a><a href="fixtures.html" data-i18n="fixtures" data-page-link="fixtures" @@NAV_FIXTURES@@>Fixtures</a></nav>
  <div class="ticker"><div class="wrap">@@TICKER_LABEL@@@@TICKER_CONTENT@@</div></div>
  <main class="wrap">
    @@MAIN_CONTENT@@
  </main>
  <footer><div class="wrap" data-i18n="footer">Skysport · News headlines stay in their publisher's original language. Fixture data: ESPN public scoreboards.</div></footer>
  <script>
    (() => {
      const translations = @@TRANSLATIONS@@;
      const languageSelect = document.getElementById('language-toggle');
      let language = 'en';
      try {
        const storedLanguage = localStorage.getItem('skysport-language');
        if (storedLanguage && translations[storedLanguage]) language = storedLanguage;
      } catch {}
      const copy = () => translations[language];
      const filters = [...document.querySelectorAll('.filter')];
      const cards = [...document.querySelectorAll('.story-card')];
      const search = document.getElementById('search');
      const empty = document.getElementById('empty-state');
      const themeButton = document.getElementById('theme-toggle');
      const pageKind = '@@PAGE_KIND@@';
      const pageUrl = @@PAGE_URL_JSON@@;
      const pageUpdated = @@UPDATED_JSON@@;
      const pageSources = @@SOURCES_JSON@@;
      const structuredDataElement = document.querySelector('script[type="application/ld+json"]');
      const structuredData = JSON.parse(structuredDataElement.textContent);
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
        button.setAttribute('aria-label', isSaved ? copy().removeSaved : copy().saveStory);
      }
      cards.forEach(card => {
        updateSavedButton(card);
        card.querySelectorAll('.story-image img').forEach(image => {
          image.addEventListener('error', () => { image.hidden = true; }, {once: true});
          if (image.complete && image.naturalWidth === 0) image.hidden = true;
        });
        card.querySelector('.save-button')?.addEventListener('click', () => {
          const key = storyKey(card);
          saved.has(key) ? saved.delete(key) : saved.add(key);
          try { localStorage.setItem('skysport-saved', JSON.stringify([...saved])); } catch {}
          updateSavedButton(card);
          updateCards();
        });
      });
      function updateCards() {
        if (!search || !empty) return;
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
      search?.addEventListener('input', updateCards);
      function applyLanguage() {
        const rtl = language === 'ar';
        const page = copy().pages[pageKind];
        document.documentElement.lang = language;
        document.documentElement.dir = rtl ? 'rtl' : 'ltr';
        document.title = page.title;
        document.querySelector('meta[name="description"]').content = page.description;
        document.querySelector('meta[property="og:title"]').content = page.title;
        document.querySelector('meta[property="og:description"]').content = page.description;
        document.querySelector('meta[name="twitter:title"]').content = page.title;
        document.querySelector('meta[name="twitter:description"]').content = page.description;
        const pageData = structuredData['@graph'].find(item => item['@id'] === `${pageUrl}#webpage`);
        pageData.name = page.title;
        pageData.description = page.description;
        pageData.inLanguage = language;
        structuredDataElement.textContent = JSON.stringify(structuredData);
        document.querySelector('[data-page-heading]').textContent = page.heading;
        document.querySelector('[data-page-intro]').textContent = page.intro;
        if (languageSelect) {
          languageSelect.value = language;
          languageSelect.setAttribute('aria-label', copy().language);
        }
        document.querySelector('label[for="language-toggle"]').textContent = copy().language;
        document.querySelectorAll('[data-i18n]').forEach(element => {
          const value = copy()[element.dataset.i18n];
          if (typeof value === 'string') element.textContent = value;
        });
        if (pageKind === 'news') {
          const newsIntro = document.querySelector('[data-i18n="newsPageIntro"]');
          if (newsIntro) newsIntro.textContent = copy().newsPageIntro.replace('__UPDATED__', pageUpdated).replace('__SOURCES__', pageSources);
        }
        document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
          element.placeholder = copy()[element.dataset.i18nPlaceholder];
        });
        document.querySelectorAll('[data-section-copy]').forEach(element => {
          const [section, key] = element.dataset.sectionCopy.split('.');
          element.textContent = copy().sectionCards[section][key] + (key === 'action' ? ' ↗' : '');
        });
        filters.forEach(button => {
          button.textContent = copy().categories[button.dataset.filter] || button.dataset.filter;
        });
        document.querySelectorAll('.category, .sport-label, .image-placeholder').forEach(element => {
          const sport = element.dataset.category || element.dataset.sport;
          if (sport) element.textContent = copy().categories[sport] || copy().sports[sport] || sport;
        });
        cards.forEach(updateSavedButton);
        const dark = document.documentElement.classList.contains('dark');
        themeButton.setAttribute('aria-label', dark ? copy().themeLight : copy().themeDark);
      }
      languageSelect?.addEventListener('change', () => {
        language = translations[languageSelect.value] ? languageSelect.value : 'en';
        try { localStorage.setItem('skysport-language', language); } catch {}
        applyLanguage();
      });
      try {
        if (localStorage.getItem('skysport-theme') === 'dark') document.documentElement.classList.add('dark');
      } catch {}
      themeButton?.addEventListener('click', () => {
        const dark = document.documentElement.classList.toggle('dark');
        try { localStorage.setItem('skysport-theme', dark ? 'dark' : 'light'); } catch {}
        applyLanguage();
      });
      applyLanguage();
    })();
  </script>
</body>
</html>"""
    replacements = {
        "@@SITE_URL@@": html.escape(SITE_URL, quote=True),
        "@@PAGE_URL@@": html.escape(page_url, quote=True),
        "@@PAGE_TITLE@@": html.escape(english_page["title"]),
        "@@PAGE_DESCRIPTION@@": html.escape(english_page["description"], quote=True),
        "@@PAGE_HEADING@@": html.escape(english_page["heading"]),
        "@@PAGE_INTRO@@": html.escape(english_page["intro"]),
        "@@PAGE_INTRO_KEY@@": "intro",
        "@@PAGE_KIND@@": page_kind,
        "@@UPDATED_JSON@@": json.dumps(updated, ensure_ascii=False),
        "@@SOURCES_JSON@@": json.dumps(news_sources, ensure_ascii=False),
        "@@HOME_STATS_HIDDEN@@": "" if page_kind == "home" else "hidden",
        "@@MAIN_CONTENT@@": page_content,
        "@@SECTION_CARDS@@": section_cards,
        "@@NAV_NEWS@@": 'aria-current="page"' if page_kind == "news" else "",
        "@@NAV_VIDEOS@@": 'aria-current="page"' if page_kind == "videos" else "",
        "@@NAV_LIVE@@": 'aria-current="page"' if page_kind == "live" else "",
        "@@NAV_FIXTURES@@": 'aria-current="page"' if page_kind == "fixtures" else "",
        "@@STYLE@@": STYLE,
        "@@STRUCTURED_DATA@@": structured_data_json,
        "@@PAGE_URL_JSON@@": json.dumps(page_url, ensure_ascii=False),
        "@@TICKER_LABEL@@": ticker_label,
        "@@TICKER_CONTENT@@": ticker_markup,
        "@@SOURCE_COUNT@@": f"{source_count:02d}",
        "@@FILTERS@@": "".join(
            f'<button class="filter{" active" if category == "All" else ""}" type="button" data-filter="{html.escape(category, quote=True)}">{html.escape({"All": "All sports", "Saved": "♡ Saved"}.get(category, category))}</button>'
            for category in ("All", *NEWS_CATEGORIES, "Saved")
        ),
        "@@VIDEOS@@": videos_html or '<p class="section-empty" data-i18n="noVideos">No video items were available from the active RSS feeds.</p>',
        "@@LIVE@@": live_html or render_live([]),
        "@@FIXTURES@@": fixtures_html,
        "@@FIXTURE_STATUS@@": html.escape(fixture_status),
        "@@TRANSLATIONS@@": json.dumps(TRANSLATIONS, ensure_ascii=False),
    }
    for marker, value in replacements.items():
        page = page.replace(marker, value)
    return page


def read_cached_news(path="news.html"):
    current = ""
    for candidate in (path, "index.html") if path != "index.html" else (path,):
        try:
            with open(candidate, encoding="utf-8") as existing:
                current = existing.read()
                break
        except OSError:
            continue
    if not current:
        return "", ""
    cards = re.findall(r'<article\b[^>]*class="story-card"[^>]*>.*?</article>', current, re.DOTALL)
    updated = re.search(r"(?:Updated|Last cached update:?)\s+([^<]+?)\s*·\s*(?:News source|Sources|Source):", current)
    updated_label = updated.group(1).strip() if updated else ""
    if updated_label == "No successful feed refresh yet":
        updated_label = ""
    return "\n".join(cards), updated_label


def main():
    stories, news_sources, news_failures = collect_stories()
    image_failures = collect_espn_images(stories)
    stories_html = "\n".join(render_story(story) for story in stories)
    failures = news_failures + image_failures
    if failures:
        print("Some news feeds or images could not be updated: " + "; ".join(failures))
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
    live_fixtures = [fixture for fixture in fixtures if fixture.get("is_live")]
    upcoming_fixtures = [fixture for fixture in fixtures if not fixture.get("is_live")]
    fixtures_html = render_schedule(upcoming_fixtures, available_sports)
    if not upcoming_fixtures and fixture_failures and not available_sports:
        fixture_status = "All public schedule requests failed this refresh."
    elif not upcoming_fixtures:
        fixture_status = "No fixtures were returned by public feeds this refresh."
    elif len(available_sports) < len(SPORTS):
        fixture_status = "Some sports do not have a currently available public schedule feed."
    else:
        fixture_status = ""
    source_label = ", ".join(news_sources) if news_sources else "No RSS source available"
    for page_kind, page_file in PAGE_FILES.items():
        page = build_page(
            stories_html,
            videos_html,
            fixtures_html,
            updated,
            source_label,
            fixture_status,
            render_live(live_fixtures),
            stories,
            page_kind,
        )
        with open(page_file, "w", encoding="utf-8") as output:
            output.write(page)

    sitemap = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for page_file in PAGE_FILES.values():
        location = SITE_URL if page_file == "index.html" else urljoin(SITE_URL, page_file)
        url_node = ET.SubElement(sitemap, "url")
        ET.SubElement(url_node, "loc").text = location
    ET.indent(sitemap, space="  ")
    ET.ElementTree(sitemap).write("sitemap.xml", encoding="UTF-8", xml_declaration=True)
    print(f"Generated {len(PAGE_FILES)} Skysport pages and sitemap successfully.")


if __name__ == "__main__":
    main()
