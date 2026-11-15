# Automated world news

The world-news desk is an additive side project alongside the existing sports site. It reads RSS/Atom headlines and publisher-provided descriptions from BBC News, The Guardian, and NPR, validates every article URL against that feed's publisher domain, and merges likely cross-source duplicates while preserving the other source links.

The existing GitHub Actions workflow runs every 15 minutes and now refreshes the world-news page and RSS feed alongside the sports site. It commits `world-news.html`, `world-news-feed.xml`, and `world-news-cache.json` so the latest output is available to the repository's existing site hosting. You can also run `python world_news.py` locally to generate those files once. Run `python -m unittest discover -s tests -v` to test the parser, source validation, deduplication, AI request handling, and output rendering without network access.

For local ongoing updates, run `python world_news.py --watch`. The default interval is 60 minutes; set `WORLD_NEWS_INTERVAL_MINUTES` to a positive integer to change it. The process updates only the files in its current directory.

AI summaries use an OpenAI-compatible Chat Completions endpoint. For scheduled GitHub Actions runs, add a repository Actions secret named `AI_API_KEY` containing your provider API key (Repository Settings → Secrets and variables → Actions → New repository secret). The workflow passes that secret only to the world-news generation step; no credential is stored in the repository. Locally, set `AI_API_KEY` (or `OPENAI_API_KEY`) and optionally `AI_API_URL` and `AI_MODEL`. The defaults are the OpenAI API URL and `gpt-4o-mini`.

The `AI_API_KEY` secret is optional: without it, scheduled runs still publish headlines and source links, but mark summaries as unavailable instead of copying publisher descriptions or claiming they are AI-written. If AI generation fails, the same fallback is used and the workflow continues. AI input is limited to the RSS title and a short publisher description; every story links to its source and publication time. The existing sports automation remains in place, and world news has its own page and feed.
