import os
import json
import urllib.request
import urllib.error

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables!")

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

prompt_text = (
    "Generate a short sports news article in English about recent football highlights. "
    "Format the output in clean HTML using tags like <h2> and <p> without markdown code blocks."
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

news_html = "<p>Could not generate news at this moment.</p>"

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
    <title>Skysport - Auto News</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f4f4f9; color: #333; }}
        .container {{ max-width: 800px; margin: auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
        h1 {{ color: #e74c3c; border-bottom: 2px solid #f1f1f1; padding-bottom: 10px; }}
        .news-body {{ line-height: 1.6; font-size: 16px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Skysport Automated News</h1>
        <div class="news-body">
            {news_html}
        </div>
    </div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("Script finished execution successfully and index.html was updated.")
