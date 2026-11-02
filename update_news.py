import os
import json
import urllib.request

# 1. جلب المفتاح ديال API
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables!")

# 2. إعداد الطلب المباشر لـ Gemini API عبر الرابط الرسمي
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

prompt_text = "Generate a short sports news article in English about recent football highlights, formatted in clean HTML."

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
        # استخراج النص بطريقة آمنة
        if 'candidates' in result and len(result['candidates']) > 0:
            news_html = result['candidates'][0]['content']['parts'][0]['text']
except Exception as e:
    print(f"Error calling Gemini API: {e}")

# 3. كتابة النتيجة في ملف index.html
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Skysport - Auto News</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f4f4f9; color: #333; }}
        .container {{ max-width: 800px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #e74c3c; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Skysport Automated News</h1>
        <div>
            {news_html}
        </div>
    </div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("News updated successfully via direct API!")
