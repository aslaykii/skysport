import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

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
          <media:content url="https://ichef.bbci.co.uk/photo.jpg" medium="image" />
        </item></channel></rss>"""

        story = sports_site.parse_feed(payload, feed)[0]

        self.assertEqual(story["title"], "Football: <Final> preview")
        self.assertEqual(story["category"], "Football")
        self.assertEqual(story["source"], "BBC Sport")
        self.assertTrue(story["video"])
        self.assertEqual(story["url"], "https://www.bbc.co.uk/sport/football/videos/story")

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
            + ('<img src="https://www.bbc.co.uk/feature.jpg">' if index == 2 else "")
            + f'<div class="story-body"><h3><a href="https://www.bbc.co.uk/{index}">Story {index}</a></h3></div></article>'
            for index in range(1, 7)
        )
        page = sports_site.build_page(
            stories,
            "",
            sports_site.render_schedule([], set()),
            "Today",
            "<publisher>",
            "Status",
        )

        self.assertIn("&lt;publisher&gt;", page)
        self.assertIn('id="videos"', page)
        self.assertIn('id="fixtures"', page)
        self.assertIn("No video items were available", page)
        self.assertIn('data-filter="American Football"', page)
        self.assertIn('data-filter="Ice Hockey"', page)
        self.assertIn('href="#fixtures"', page)
        self.assertIn('class="mobile-nav"', page)
        self.assertIn("position:fixed;z-index:30", page)
        self.assertIn('id="language-toggle"', page)
        self.assertIn('value="fr">Français', page)
        self.assertIn('value="ar">العربية', page)
        self.assertIn('id="live"', page)
        self.assertIn('data-i18n="liveScores"', page)
        self.assertIn('localStorage.setItem(\'skysport-language\'', page)
        self.assertIn('document.documentElement.dir = rtl ? \'rtl\' : \'ltr\'', page)
        self.assertNotIn("@@TRANSLATIONS@@", page)
        self.assertIn('class="story-card lead-story"', page)
        self.assertIn('class="story-card latest-story"', page)
        featured = page[page.index('class="story-card lead-story"'):page.index('class="latest-panel"')]
        self.assertIn("Story 2", featured)
        self.assertNotIn("Story 1", featured)
        self.assertIn("Story 6", page)
        self.assertNotIn("Story 1", page[page.index('<div class="news-grid"'):])
        self.assertIn("font-family:Georgia,serif", page)
        self.assertIn(":root.dark", page)
        self.assertNotIn("@@STYLE@@", page)

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


if __name__ == "__main__":
    unittest.main()
