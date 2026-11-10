import json
import os
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

import sports_site


class SportsSiteTests(unittest.TestCase):
    def test_parse_feed_normalizes_story_and_detects_video(self):
        feed = sports_site.NEWS_FEEDS[0]
        payload = b"""<?xml version="1.0"?>
        <rss xmlns:media="http://search.yahoo.com/mrss/"><channel><item>
          <title>Football: &amp;lt;Final&amp;gt; preview</title>
          <description>A big match</description>
          <link>https://www.bbc.co.uk/sport/football/videos/story</link>
          <pubDate>Mon, 02 Nov 2026 10:00:00 GMT</pubDate>
          <media:content url="https://ichef.bbci.co.uk/ace/standard/240/cpsprodpb/photo.jpg" medium="image" />
        </item></channel></rss>"""

        story = sports_site.parse_feed(payload, feed)[0]

        self.assertEqual(story["title"], "Football: <Final> preview")
        self.assertEqual(story["category"], "Football")
        self.assertEqual(story["source"], "BBC Sport")
        self.assertEqual(story["image"], "https://ichef.bbci.co.uk/ace/standard/1024/cpsprodpb/photo.jpg")
        self.assertTrue(story["video"])
        self.assertEqual(story["url"], "https://www.bbc.co.uk/sport/football/videos/story")

    def test_parse_feed_uses_thumbnail_without_media_type_and_largest_image(self):
        feed = sports_site.NEWS_FEEDS[0]
        payload = b"""<rss xmlns:media="http://search.yahoo.com/mrss/"><channel><item>
          <title>Match report</title><link>https://www.bbc.co.uk/sport/football/story</link>
          <media:thumbnail width="240" height="135" url="https://ichef.bbci.co.uk/240/small.jpg"/>
          <media:content width="700" url="https://ichef.bbci.co.uk/700/large.jpg">Photo credit</media:content>
          <media:content width="460" url="https://ichef.bbci.co.uk/460/medium.jpg">Photo credit</media:content>
        </item></channel></rss>"""

        story = sports_site.parse_feed(payload, feed)[0]

        self.assertEqual(story["image"], "https://ichef.bbci.co.uk/700/large.jpg")

    def test_render_story_shows_a_styled_category_fallback(self):
        feed = sports_site.NEWS_FEEDS[0]
        payload = b"""<rss><channel><item><title>Match report</title>
          <link>https://www.bbc.co.uk/sport/football/story</link></item></channel></rss>"""
        story = sports_site.parse_feed(payload, feed)[0]

        markup = sports_site.render_story(story)

        self.assertIn('class="image-placeholder" data-category="Football"', markup)
        self.assertNotIn("<img", markup)

    def test_parse_feed_rejects_non_publisher_links(self):
        feed = sports_site.NEWS_FEEDS[0]
        payload = b"""<rss><channel><item><title>Unsafe story</title>
          <link>https://attacker.example/story</link></item></channel></rss>"""

        story = sports_site.parse_feed(payload, feed)[0]

        self.assertEqual(story["url"], feed.homepage)

    def test_category_uses_publisher_path_for_more_sports(self):
        self.assertEqual(
            sports_site.category_for("NFL best plays", "", "https://www.bbc.co.uk/sport/american-football/videos/clip"),
            "American Football",
        )
        self.assertEqual(sports_site.category_for("NHL playoff race", "", "https://www.espn.com/nhl/story"), "Ice Hockey")
        self.assertEqual(sports_site.category_for("Open Championship", "", "https://www.bbc.co.uk/sport/golf/story"), "Golf")
        self.assertEqual(sports_site.category_for("World title fight", "", "https://www.skysports.com/boxing/news/story"), "Boxing & MMA")

    def test_collect_stories_merges_cross_source_near_duplicates(self):
        bbc, sky = sports_site.NEWS_FEEDS[0], sports_site.NEWS_FEEDS[3]
        payloads = {
            bbc.url: b"""<rss><channel><item><title>Alisson wants to sign new Liverpool contract</title>
              <description>Liverpool goalkeeper Alisson wants to stay at the club.</description>
              <link>https://www.bbc.co.uk/sport/football/articles/alisson-contract</link>
              <pubDate>Mon, 09 Nov 2026 10:00:00 GMT</pubDate></item></channel></rss>""",
            sky.url: b"""<rss><channel><item><title>My will is to stay - Alisson wants new Liverpool contract</title>
              <description>The Liverpool goalkeeper wants a new deal.</description>
              <link>https://www.skysports.com/football/news/alisson-contract</link>
              <pubDate>Mon, 09 Nov 2026 11:00:00 GMT</pubDate></item></channel></rss>""",
        }

        stories, _, _ = sports_site.collect_stories(lambda url: payloads[url], (bbc, sky))

        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]["source"], "Sky Sports")
        self.assertEqual(stories[0]["coverage"], [{
            "name": "BBC Sport",
            "url": "https://www.bbc.co.uk/sport/football/articles/alisson-contract",
        }])
        self.assertIn("BBC Sport", sports_site.render_story(stories[0]))

    def test_parse_feed_embeds_only_publisher_hosted_mp4(self):
        feed = sports_site.NEWS_FEEDS[0]
        trusted = b"""<rss><channel><item><title>Official highlight video</title>
          <link>https://www.bbc.co.uk/sport/football/videos/clip</link>
          <enclosure url="https://cdn.bbci.co.uk/sport/clip.mp4" type="video/mp4"/>
        </item></channel></rss>"""
        untrusted = trusted.replace(b"https://cdn.bbci.co.uk/sport/clip.mp4", b"https://media.example/clip.mp4")

        story = sports_site.parse_feed(trusted, feed)[0]
        unsafe_story = sports_site.parse_feed(untrusted, feed)[0]

        self.assertEqual(story["video_url"], "https://cdn.bbci.co.uk/sport/clip.mp4")
        self.assertIn("<video controls", sports_site.render_video(story))
        self.assertEqual(unsafe_story["video_url"], "")

    def test_collect_stories_keeps_successful_sources_when_one_fails(self):
        good_feed = sports_site.NEWS_FEEDS[0]
        bad_feed = sports_site.NEWS_FEEDS[1]
        xml = b"<rss><channel><item><title>Rugby latest</title><link>https://www.bbc.co.uk/sport/rugby/story</link></item></channel></rss>"

        def fetcher(url):
            if url == bad_feed.url:
                raise OSError("offline")
            return xml

        stories, available, failures = sports_site.collect_stories(fetcher, (good_feed, bad_feed))

        self.assertEqual(len(stories), 1)
        self.assertEqual(available, ["BBC Sport"])
        self.assertEqual(len(failures), 1)
        self.assertIn("The Guardian", failures[0])

    def test_collect_stories_keeps_a_story_from_each_available_source(self):
        primary = sports_site.NEWS_FEEDS[0]
        secondary = sports_site.NEWS_FEEDS[1]
        payloads = {
            primary.url: b"""<rss><channel>
              <item><title>Newest primary story</title><link>https://www.bbc.co.uk/sport/football/newest</link><pubDate>Mon, 09 Nov 2026 15:00:00 GMT</pubDate></item>
              <item><title>Second primary story</title><link>https://www.bbc.co.uk/sport/football/second</link><pubDate>Mon, 09 Nov 2026 14:00:00 GMT</pubDate></item>
              <item><title>Third primary story</title><link>https://www.bbc.co.uk/sport/football/third</link><pubDate>Mon, 09 Nov 2026 13:00:00 GMT</pubDate></item>
            </channel></rss>""",
            secondary.url: b"""<rss><channel><item><title>Older secondary story</title>
              <link>https://www.theguardian.com/sport/football/older</link>
              <pubDate>Sun, 08 Nov 2026 12:00:00 GMT</pubDate></item></channel></rss>""",
        }
        max_stories = sports_site.MAX_STORIES
        sports_site.MAX_STORIES = 2
        try:
            stories, available, failures = sports_site.collect_stories(
                lambda url: payloads[url], (primary, secondary)
            )
        finally:
            sports_site.MAX_STORIES = max_stories

        self.assertEqual(available, ["BBC Sport", "The Guardian"])
        self.assertEqual(failures, [])
        self.assertEqual(len(stories), 2)
        self.assertEqual({story["source"] for story in stories}, {"BBC Sport", "The Guardian"})

    def test_parse_beinsports_news_extracts_official_story_and_largest_image(self):
        feed = sports_site.NEWS_FEEDS[-1]
        page = b"""<html><a href="/en-mena/football/premier-league/articles-video/match-report-2026-11-09">
          <img src="https://prod-media.beinsports.com/image/small.jpg"
            srcset="https://prod-media.beinsports.com/image/medium.jpg 640w, https://prod-media.beinsports.com/image/large.jpg 1080w"/>
          <div title="2026-11-09T14:00:00.000Z"></div>
          <div title="Premier League match report"></div>
          <div title="The full match report summary."></div>
        </a></html>"""

        stories = sports_site.parse_beinsports_news(page, feed)

        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]["source"], "beIN SPORTS")
        self.assertEqual(stories[0]["title"], "Premier League match report")
        self.assertEqual(stories[0]["description"], "The full match report summary.")
        self.assertEqual(stories[0]["category"], "Football")
        self.assertEqual(stories[0]["image"], "https://prod-media.beinsports.com/image/large.jpg")
        self.assertEqual(stories[0]["published"], datetime(2026, 11, 9, 14, tzinfo=timezone.utc))
        self.assertEqual(stories[0]["url"], "https://www.beinsports.com/en-mena/football/premier-league/articles-video/match-report-2026-11-09")

    def test_parse_beinsports_news_rejects_nonpublisher_stories_and_images(self):
        feed = sports_site.NEWS_FEEDS[-1]
        page = b"""<a href="https://attacker.example/story">
          <img src="https://attacker.example/photo.jpg"/>
          <div title="Unsafe headline"></div></a>"""

        self.assertEqual(sports_site.parse_beinsports_news(page, feed), [])

    def test_collect_espn_images_matches_story_ids_and_uses_largest_image(self):
        stories = [
            {"source": "ESPN", "category": "Basketball", "url": "https://www.espn.com/nba/story/_/id/12345/story", "image": ""},
            {"source": "ESPN", "category": "Basketball", "url": "https://www.espn.com/nba/story/_/id/67890/other", "image": ""},
        ]
        payload = {
            "articles": [{
                "links": {"web": {"href": "https://www.espn.com/nba/story/_/id/12345/story"}},
                "images": [
                    {"url": "https://a.espncdn.com/photo-small.jpg", "width": 320},
                    {"url": "https://a.espncdn.com/photo-large.jpg", "width": 1200},
                    {"url": "http://a.espncdn.com/insecure.jpg", "width": 2400},
                ],
            }],
        }

        failures = sports_site.collect_espn_images(stories, lambda _: json.dumps(payload).encode())

        self.assertEqual(failures, [])
        self.assertEqual(stories[0]["image"], "https://a.espncdn.com/photo-large.jpg")
        self.assertEqual(stories[1]["image"], "")

    def test_collect_espn_images_ignores_unmatched_articles(self):
        story = {"source": "ESPN", "category": "American Football", "url": "https://www.espn.com/nfl/story/_/id/12345/story", "image": ""}
        payload = {
            "articles": [{
                "links": {"web": {"href": "https://www.espn.com/nfl/story/_/id/99999/unrelated"}},
                "images": [{"url": "https://a.espncdn.com/unrelated.jpg", "width": 1200}],
            }],
        }

        sports_site.collect_espn_images([story], lambda _: json.dumps(payload).encode())

        self.assertEqual(story["image"], "")

    def test_normalize_event_keeps_upcoming_sourced_match_only(self):
        now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
        feed = sports_site.FixtureFeed("Football", "Premier League", "soccer/eng.1")
        event = {
            "id": "fixture-1",
            "date": (now + timedelta(days=1)).isoformat(),
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"displayName": "North FC"}},
                    {"homeAway": "away", "team": {"displayName": "South FC"}},
                ],
            }],
            "links": [{"href": "https://www.espn.com/soccer/match/_/gameId/1"}],
        }

        match = sports_site.normalize_event(event, feed, now)

        self.assertEqual(match["home"], "North FC")
        self.assertEqual(match["away"], "South FC")
        self.assertEqual(match["competition"], "Premier League")
        self.assertEqual(match["url"], "https://www.espn.com/soccer/match/_/gameId/1")
        event["date"] = (now - timedelta(days=1)).isoformat()
        self.assertIsNone(sports_site.normalize_event(event, feed, now))

    def test_normalize_event_supports_scheduled_events_without_teams(self):
        now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
        feed = sports_site.FixtureFeed("Formula 1", "Formula 1", "racing/f1")
        event = {
            "id": "race-1",
            "name": "Grand Prix race",
            "date": (now + timedelta(days=2)).isoformat(),
        }

        match = sports_site.normalize_event(event, feed, now)
        markup = sports_site.render_fixture(match)

        self.assertEqual(match["home"], "Grand Prix race")
        self.assertEqual(match["away"], "")
        self.assertIn("Grand Prix race", markup)
        self.assertNotIn(">VS<", markup)

    def test_normalize_event_includes_live_score_and_excludes_completed_matches(self):
        now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
        feed = sports_site.FixtureFeed("Football", "Premier League", "soccer/eng.1")
        event = {
            "id": "live-1",
            "date": (now - timedelta(minutes=35)).isoformat(),
            "status": {"type": {"state": "in", "shortDetail": "2nd Half"}},
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"displayName": "North FC"}, "score": "2"},
                    {"homeAway": "away", "team": {"displayName": "South FC"}, "score": "1"},
                ],
            }],
            "links": [{"href": "https://www.espn.com/soccer/match/_/gameId/1"}],
        }

        match = sports_site.normalize_event(event, feed, now)
        markup = sports_site.render_live([match])

        self.assertTrue(match["is_live"])
        self.assertEqual((match["home_score"], match["away_score"]), ("2", "1"))
        self.assertIn("2 : 1", markup)
        self.assertIn("2nd Half", markup)
        self.assertIn('data-i18n="liveNow"', markup)
        event["status"]["type"]["state"] = "post"
        self.assertIsNone(sports_site.normalize_event(event, feed, now))

    def test_collect_fixtures_reports_partial_coverage(self):
        now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
        feed = sports_site.FixtureFeed("Football", "Premier League", "soccer/eng.1")
        event = {
            "id": "fixture-1",
            "date": (now + timedelta(days=1)).isoformat(),
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"displayName": "North FC"}},
                    {"homeAway": "away", "team": {"displayName": "South FC"}},
                ],
            }],
        }

        fixtures, available, failures = sports_site.collect_fixtures(
            lambda _url: json.dumps({"events": [event]}).encode(),
            (feed,),
            now,
        )

        self.assertEqual(len(fixtures), 1)
        self.assertEqual(available, {"Football"})
        self.assertEqual(failures, [])
        markup = sports_site.render_schedule(fixtures, available)
        self.assertIn("North FC", markup)
        self.assertIn("Public fixture feed unavailable right now.", markup)

    def test_collect_fixtures_queries_month_and_filters_to_window(self):
        now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
        feed = sports_site.FixtureFeed("Football", "Premier League", "soccer/eng.1")
        requested = []
        upcoming = {
            "id": "future",
            "date": (now + timedelta(days=2)).isoformat(),
            "name": "North FC vs South FC",
        }
        outside_window = {
            "id": "later",
            "date": (now + timedelta(days=20)).isoformat(),
            "name": "Later match",
        }

        def fetcher(url):
            requested.append(url)
            return json.dumps({"events": [upcoming, outside_window]}).encode()

        fixtures, available, failures = sports_site.collect_fixtures(fetcher, (feed,), now)

        self.assertIn("dates=202611", requested[0])
        self.assertEqual([fixture["id"] for fixture in fixtures], ["future"])
        self.assertEqual(available, {"Football"})
        self.assertEqual(failures, [])

    def test_collect_fixtures_queries_both_months_for_cross_month_window(self):
        now = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)
        feed = sports_site.FixtureFeed("Football", "Premier League", "soccer/eng.1")
        requested = []

        def fetcher(url):
            requested.append(url)
            return b'{"events":[]}'

        sports_site.collect_fixtures(fetcher, (feed,), now)

        self.assertEqual(len(requested), 2)
        self.assertIn("dates=202611", requested[0])
        self.assertIn("dates=202612", requested[1])

    def test_build_page_escapes_dynamic_labels_and_includes_sections(self):
        stories = "".join(
            f'<article class="story-card" data-category="Football">'
            + ('<img src="https://www.bbc.co.uk/feature.jpg" loading="lazy" decoding="async">' if index == 2 else "")
            + f'<div class="story-body"><h3><a href="https://www.bbc.co.uk/{index}">Story {index}</a></h3></div></article>'
            for index in range(1, 7)
        )
        page = sports_site.build_page(
            stories,
            "",
            sports_site.render_schedule([], set()),
            "Today",
            "<publisher>, BBC Sport, beIN SPORTS, ESPN, The Guardian",
            "Status",
            stories=[{"title": "Verified football story", "url": "https://publisher.example/football-story"}],
        )

        self.assertIn("&lt;publisher&gt;", page)
        self.assertIn('href="news.html"', page)
        self.assertIn('href="videos.html"', page)
        self.assertIn('href="live.html"', page)
        self.assertIn('href="fixtures.html"', page)
        self.assertIn('data-section-card="news"', page)
        self.assertIn('data-section-card="videos"', page)
        self.assertNotIn('id="news-grid"', page)
        self.assertNotIn('id="live"', page)
        self.assertNotIn('id="fixtures"', page)
        self.assertIn('class="mobile-nav"', page)
        self.assertIn("position:fixed;z-index:30", page)
        self.assertIn('id="language-toggle"', page)
        self.assertIn('value="fr">Français', page)
        self.assertIn('value="ar">العربية', page)
        self.assertIn("<strong>05</strong> news desks", page)
        self.assertIn('localStorage.setItem(\'skysport-language\'', page)
        self.assertIn('document.documentElement.dir = rtl ? \'rtl\' : \'ltr\'', page)
        self.assertIn('<meta name="robots" content="index, follow, max-image-preview:large">', page)
        self.assertIn(f'<link rel="canonical" href="{sports_site.SITE_URL}">', page)
        self.assertIn('property="og:title"', page)
        self.assertIn('type="application/ld+json"', page)
        self.assertIn('type="application/rss+xml"', page)
        self.assertIn('href="https://aslaykii.github.io/skysport/feed.xml"', page)
        self.assertNotIn("@@TRANSLATIONS@@", page)
        self.assertNotIn("@@SITE_URL@@", page)
        structured_data = re.search(
            r'<script type="application/ld\+json">(.*?)</script>', page
        )
        graph = json.loads(structured_data.group(1))["@graph"]
        self.assertIn("WebSite", [item["@type"] for item in graph])
        self.assertIn("WebPage", [item["@type"] for item in graph])
        self.assertIn("BreadcrumbList", [item["@type"] for item in graph])
        self.assertEqual(len(re.findall(r'<script type="application/ld\+json">', page)), 1)
        self.assertIn('name="twitter:image:alt"', page)
        self.assertIn("Story 1", page)
        self.assertIn("Story 2", page)
        self.assertIn("Story 3", page)
        self.assertNotIn("Story 4", page)
        self.assertIn('data-i18n="topStory">Top story</span><a class="ticker-headline"', page)
        self.assertIn("Verified football story</a>", page)
        self.assertIn('fetchpriority="high"', page)
        self.assertIn(".mobile-nav a{min-height:44px", page)
        self.assertIn(".theme-button,.language-select{min-width:44px;min-height:44px}", page)
        self.assertIn("structuredDataElement.textContent = JSON.stringify(structuredData)", page)
        self.assertIn("navigator.share(shareData)", page)
        self.assertIn("font-family:Georgia,serif", page)
        self.assertIn(":root.dark", page)
        self.assertNotIn("@@STYLE@@", page)

    def test_build_page_creates_separate_news_video_live_and_fixture_pages(self):
        story = {
            "title": "Latest football report",
            "description": "A verified sports update.",
            "url": "https://www.bbc.co.uk/sport/football/report",
            "image": "",
            "category": "Football",
            "source": "BBC Sport",
            "published": datetime(2026, 11, 9, tzinfo=timezone.utc),
            "coverage": [],
            "video": True,
            "video_url": "",
        }
        stories_html = sports_site.render_story(story)
        videos_html = sports_site.render_video(story)

        pages = {
            kind: sports_site.build_page(
                stories_html,
                videos_html,
                '<article class="fixture-card">Upcoming match</article>',
                "09 Nov 2026",
                "BBC Sport",
                "Schedule status",
                '<article class="fixture-card live-card">Live match</article>',
                [story],
                kind,
            )
            for kind in ("home", "news", "videos", "live", "fixtures")
        }
        expected_urls = {
            "home": sports_site.SITE_URL,
            "news": sports_site.SITE_URL + "news.html",
            "videos": sports_site.SITE_URL + "videos.html",
            "live": sports_site.SITE_URL + "live.html",
            "fixtures": sports_site.SITE_URL + "fixtures.html",
        }

        self.assertIn('href="news.html"', pages["home"])
        self.assertNotIn('id="news-grid"', pages["home"])
        self.assertNotIn('<article class="fixture-card live-card">Live match</article>', pages["home"])
        self.assertIn('id="news-grid"', pages["news"])
        self.assertIn("Latest football report", pages["news"])
        news_schema = json.loads(re.search(
            r'<script type="application/ld\+json">(.*?)</script>', pages["news"]
        ).group(1))
        self.assertIn("ItemList", [item["@type"] for item in news_schema["@graph"]])
        self.assertIn("CollectionPage", [item["@type"] for item in news_schema["@graph"]])
        self.assertIn('href="news.html" data-i18n="news" data-page-link="news" aria-current="page"', pages["news"])
        self.assertNotIn('<article class="fixture-card">Upcoming match</article>', pages["news"])
        self.assertIn("video-card", pages["videos"])
        self.assertNotIn("Latest football report</h3>", pages["videos"])
        self.assertNotIn('<article class="fixture-card live-card">Live match</article>', pages["videos"])
        self.assertIn('<article class="fixture-card live-card">Live match</article>', pages["live"])
        self.assertNotIn('<article class="fixture-card">Upcoming match</article>', pages["live"])
        self.assertIn("Upcoming match", pages["fixtures"])
        self.assertNotIn('<article class="fixture-card live-card">Live match</article>', pages["fixtures"])
        for kind, page in pages.items():
            self.assertIn(f'<link rel="canonical" href="{expected_urls[kind]}">', page)
            self.assertNotRegex(page, r"@@[A-Z_]+@@")

    def test_read_cached_news_preserves_refresh_time(self):
        page = '<p>Updated 09 Nov 2026 · 08:16 UTC · Sources: BBC Sport</p><article class="story-card">cached</article>'
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as existing:
            existing.write(page)
            path = existing.name

        try:
            cards, updated = sports_site.read_cached_news(path)
        finally:
            os.unlink(path)

        self.assertIn("cached", cards)
        self.assertEqual(updated, "09 Nov 2026 · 08:16 UTC")

    def test_build_rss_feed_links_to_sky_sport_story_anchors(self):
        story = {
            "title": "Football & more",
            "description": "A verified <report> & update.",
            "url": "https://www.bbc.co.uk/sport/football/report",
            "source": "BBC Sport",
            "category": "Football",
            "published": datetime(2026, 11, 9, tzinfo=timezone.utc),
            "image": "",
            "category": "Football",
            "coverage": [],
            "video": False,
        }

        feed = ET.fromstring(sports_site.build_rss_feed(
            [story], datetime(2026, 11, 10, tzinfo=timezone.utc)
        ))
        channel = feed.find("channel")
        item = channel.find("item")
        expected_link = f"{sports_site.SITE_URL}news.html#story-{sports_site.story_anchor(story)}"

        self.assertEqual(feed.tag, "rss")
        self.assertEqual(channel.findtext("title"), "SkySport | Latest Sports News")
        self.assertEqual(item.findtext("title"), "Football & more")
        self.assertEqual(item.findtext("link"), expected_link)
        self.assertEqual(item.findtext("guid"), expected_link)
        self.assertEqual(item.findtext("description"), "A verified <report> & update. Source: BBC Sport.")
        self.assertEqual(item.findtext("category"), "Football")
        self.assertIsNotNone(item.findtext("pubDate"))
        rendered_story = sports_site.render_story(story)
        self.assertIn(f'id="story-{sports_site.story_anchor(story)}"', rendered_story)
        self.assertIn(f'data-share-url="{expected_link}"', rendered_story)
        self.assertIn('data-i18n="shareStory">Share</span>', rendered_story)

    def test_sitemap_includes_last_modified_dates(self):
        sitemap = ET.fromstring(sports_site.build_sitemap(
            datetime(2026, 11, 10, 8, 30, tzinfo=timezone.utc)
        ))
        namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        self.assertEqual(
            [node.text for node in sitemap.findall("s:url/s:lastmod", namespace)],
            ["2026-11-10"] * len(sports_site.PAGE_FILES),
        )

    def test_sitemap_points_to_the_canonical_pages_site(self):
        root = Path(__file__).resolve().parents[1]
        sitemap = ET.parse(root / "sitemap.xml").getroot()
        namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        self.assertEqual(
            [node.text for node in sitemap.findall("s:url/s:loc", namespace)],
            [
                sports_site.SITE_URL if filename == "index.html"
                else f"{sports_site.SITE_URL}{filename}"
                for filename in sports_site.PAGE_FILES.values()
            ],
        )
        self.assertEqual(
            len(sitemap.findall("s:url/s:lastmod", namespace)),
            len(sports_site.PAGE_FILES),
        )
        robots = (root / "robots.txt").read_text(encoding="utf-8")
        self.assertIn("Allow: /", robots)
        self.assertIn(f"Sitemap: {sports_site.SITE_URL}sitemap.xml", robots)


if __name__ == "__main__":
    unittest.main()
