import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import world_news


class WorldNewsTests(unittest.TestCase):
    def setUp(self):
        self.bbc = world_news.NEWS_FEEDS[0]

    def test_parser_keeps_only_https_links_from_the_feed_publisher(self):
        payload = b"""<rss><channel>
          <item><title>World &amp; leaders</title><description>Summary &amp; context.</description>
            <link>https://www.bbc.co.uk/news/world-1?utm_source=feed</link>
            <pubDate>Mon, 09 Nov 2026 10:00:00 GMT</pubDate></item>
          <item><title>Unsafe item</title><link>https://attacker.example/story</link></item>
          <item><title>Insecure item</title><link>http://www.bbc.co.uk/story</link></item>
        </channel></rss>"""

        stories = world_news.parse_feed(payload, self.bbc)

        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]["title"], "World & leaders")
        self.assertEqual(stories[0]["description"], "Summary & context.")
        self.assertEqual(stories[0]["url"], "https://www.bbc.co.uk/news/world-1")
        self.assertEqual(stories[0]["source"], "BBC News")
        self.assertEqual(stories[0]["published"], datetime(2026, 11, 9, 10, tzinfo=timezone.utc))

    def test_parser_supports_atom_link_attributes(self):
        payload = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
          <title>Climate update</title><summary>New research was published.</summary>
          <link href="https://www.bbc.co.uk/news/climate-1"/>
          <updated>2026-11-09T12:30:00Z</updated>
        </entry></feed>"""

        story = world_news.parse_feed(payload, self.bbc)[0]

        self.assertEqual(story["category"], "Climate")
        self.assertEqual(story["published"], datetime(2026, 11, 9, 12, 30, tzinfo=timezone.utc))

    def test_collect_stories_deduplicates_across_publishers_and_keeps_citations(self):
        guardian = world_news.NEWS_FEEDS[1]
        payloads = {
            self.bbc.url: b"""<rss><channel><item><title>Global leaders announce new climate deal</title>
              <description>Officials reached a new agreement.</description>
              <link>https://www.bbc.co.uk/news/climate-deal</link></item></channel></rss>""",
            guardian.url: b"""<rss><channel><item><title>Global leaders announce a new climate deal</title>
              <description>Leaders confirmed the agreement.</description>
              <link>https://www.theguardian.com/world/climate-deal</link></item></channel></rss>""",
        }

        stories, sources, failures = world_news.collect_stories(
            lambda url: payloads[url], (self.bbc, guardian)
        )

        self.assertEqual(len(stories), 1)
        self.assertEqual(sources, ["BBC News", "The Guardian"])
        self.assertEqual(failures, [])
        self.assertEqual(stories[0]["coverage"], [{
            "name": "The Guardian",
            "url": "https://www.theguardian.com/world/climate-deal",
        }])

    def test_ai_request_uses_grounded_input_and_ignores_unknown_ids(self):
        story = {
            "id": "known",
            "title": "Leaders sign a climate agreement",
            "description": "The agreement was signed at a summit.",
            "source": "BBC News",
        }
        requests = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return json.dumps({
                    "choices": [{
                        "message": {
                            "content": json.dumps({"summaries": [
                                {"id": "known", "summary": "Leaders signed an agreement at a summit."},
                                {"id": "unknown", "summary": "Not a supplied story."},
                            ]}),
                        },
                    }],
                }).encode()

        def opener(request, timeout):
            requests.append((request, timeout))
            return Response()

        result = world_news.request_ai_summaries(
            [story], "test-secret", "https://api.example.test/v1/chat/completions", "test-model", opener
        )

        self.assertEqual(result, {"known": "Leaders signed an agreement at a summit."})
        self.assertEqual(requests[0][1], 45)
        self.assertIn(b"using only facts explicitly present", requests[0][0].data)
        self.assertEqual(requests[0][0].get_header("Authorization"), "Bearer test-secret")

    def test_summaries_are_cached_and_missing_ai_is_not_passed_off_as_a_summary(self):
        story = {
            "id": "story-id",
            "title": "Leaders meet",
            "description": "Officials met on Monday.",
            "source": "BBC News",
            "url": "https://www.bbc.co.uk/news/story",
            "published": None,
            "category": "World",
            "coverage": [],
        }
        stories = [story]
        cache = {}

        result = world_news.attach_summaries(stories, cache, "", "https://api.example.test", "model")

        self.assertEqual(result[0]["summary"], "AI summary unavailable. Open the source report for context.")
        self.assertEqual(result[0]["summary_kind"], "AI summary unavailable")
        self.assertEqual(cache["story-id"]["summary_kind"], "AI summary unavailable")

    def test_cached_ai_summary_is_reused_without_an_api_key(self):
        story = {
            "id": "story-id",
            "title": "Leaders meet",
            "description": "Officials met on Monday.",
            "source": "BBC News",
        }
        cache = {"story-id": {"summary": "Leaders met on Monday.", "summary_kind": "ai"}}

        result = world_news.attach_summaries(
            [story], cache, "", "https://api.example.test", "model"
        )

        self.assertEqual(result[0]["summary"], "Leaders met on Monday.")
        self.assertEqual(result[0]["summary_kind"], "ai")

    def test_html_escapes_dynamic_content_and_keeps_source_links_and_times(self):
        story = {
            "id": "story-id",
            "title": "<script>alert(1)</script>",
            "description": "Source summary",
            "summary": "A <safe> summary.",
            "summary_kind": "ai",
            "source": "BBC News",
            "url": "https://www.bbc.co.uk/news/story",
            "published": datetime(2026, 11, 9, 10, tzinfo=timezone.utc),
            "category": "World",
            "coverage": [],
        }

        page = world_news.build_page(
            [story], datetime(2026, 11, 9, 11, tzinfo=timezone.utc), ["BBC News"]
        )

        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)
        self.assertIn("A &lt;safe&gt; summary.", page)
        self.assertIn('href="https://www.bbc.co.uk/news/story"', page)
        self.assertIn('datetime="2026-11-09T10:00:00+00:00"', page)
        self.assertIn('href="world-news-feed.xml"', page)

    def test_rss_feed_contains_original_source_link_and_summary(self):
        story = {
            "id": "story-id",
            "title": "World & leaders",
            "summary": "A concise summary.",
            "category": "Politics",
            "source": "BBC News",
            "url": "https://www.bbc.co.uk/news/story",
            "published": datetime(2026, 11, 9, 10, tzinfo=timezone.utc),
        }

        feed = ET.fromstring(world_news.build_rss_feed(
            [story], datetime(2026, 11, 9, 11, tzinfo=timezone.utc)
        ))
        item = feed.find("./channel/item")

        self.assertEqual(item.findtext("title"), "World & leaders")
        self.assertEqual(item.findtext("link"), story["url"])
        self.assertEqual(item.findtext("description"), story["summary"])
        self.assertEqual(item.findtext("source"), "BBC News")
        self.assertEqual(item.findtext("guid"), story["id"])

    def test_cache_reader_rejects_non_object_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValueError):
                world_news.read_cache(path)


if __name__ == "__main__":
    unittest.main()
