import os
import json
import urllib.request
import urllib.error

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables!")

# Istikhdam gemini-1.5-flash bash n-jibo akbar l-akhbar w l-highlights dyal riyada f l-alam
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

prompt_text = (
    "Act as a professional sports journalist. Generate a fresh, engaging sports news article "
    "covering the latest global football highlights, major match results, and top sports headlines "
    "inspired by major sports networks like ESPN and Sky Sports. "
    "Format the output in clean HTML using tags like <h2>, <p>, and <ul> without enclosing it in markdown code blocks."
)

payload = {
    "contents": [{
        "parts": [{"text": prompt_text}]
    }]
}

req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST'
)

news_html = "<p>Could not fetch latest sports news at this moment.</p>"

try:
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        if 'candidates' in result and len(result['candidates']) > 0:
            content = result['candidates'][0]['content']
            if 'parts' in content and len(content['parts']) > 0:
                raw_text = content['parts'][0]['text']
                cleaned_text = raw_text.replace("```html", "").replace("```", "").strip()
                news_html = cleaned_text
except urllib.error.HTTPError as e:
    error_body = e.read().decode('utf-8')
    print(f"HTTP Error details: {e.code} - {error_body}")
except Exception as e:
    print(f"General Error calling Gemini API: {e}")

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Skysport - Global Sports News</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; background: #f8f9fa; color: #212529; }}
        header {{ background: #111; color: #fff; padding: 20px; text-align: center; border-bottom: 4px solid #e74c3c; }}
        .container {{ max-width: 900px; margin: 30px auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
        h1 {{ margin: 0; font-size: 28px; color: #fff; letter-spacing: 1px; }}
        h2 {{ color: #2c3e50; border-left: 5px solid #e74c3c; padding-left: 12px; margin-top: 30px; }}
        p {{ line-height: 1.8; font-size: 16px; color: #444; }}
        ul {{ line-height: 1.8; font-size: 16px; color: #444; }}
        .footer {{ margin-top: 40px; font-size: 13px; color: #777; text-align: center; border-top: 1px solid #eaeaea; padding-top: 20px; }}
    </style>
</head>
<body>
    <header>
        <h1>SKYSPORT GLOBAL NEWS</h1>
    </header>
    <div class="container">
        {news_html}
        <div class="footer">
            Auto-updated hourly from global sports feeds via Gemini API & GitHub Actions.
        </div>
    </div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("Global sports news updated successfully in index.html.")
