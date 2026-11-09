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

    def test_build_page_escapes_dynamic_labels_and_includes_sections(self):
        page = sports_site.build_page(
            '<article class="story-card"><h3>Story</h3></article>',
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
