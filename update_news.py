import urllib.request
import xml.etree.ElementTree as ET

# رابط RSS الرسمي ديال الأخبار الرياضية (BBC Sport مثلاً مجاني ومتاح للجميع)
rss_url = "http://feeds.bbci.co.uk/sport/rss.xml"

news_items_html = ""

try:
    req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        xml_data = response.read()
        root = ET.fromstring(xml_data)
        
        # جلب آخر 5 أخبار رياضية من الـ RSS
        count = 0
        for item in root.findall('./channel/item'):
            if count >= 5:
                break
            title = item.find('title').text if item.find('title') is not None else ""
            description = item.find('description').text if item.find('description') is not None else ""
            
            news_items_html += f"""
                <div class="news-item">
                    <h2>{title}</h2>
                    <p>{description}</p>
                </div>
            """
            count += 1
except Exception as e:
    print(f"Error fetching RSS: {e}")
    news_items_html = "<p>Could not fetch latest sports news at this moment.</p>"

# تصميم الصفحة
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Skysport - Live RSS News</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; background: #f8f9fa; color: #212529; }}
        header {{ background: #111; color: #fff; padding: 20px; text-align: center; border-bottom: 4px solid #e74c3c; }}
        .container {{ max-width: 900px; margin: 30px auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
        h1 {{ margin: 0; font-size: 28px; color: #fff; letter-spacing: 1px; }}
        .news-item {{ border-bottom: 1px solid #eee; padding-bottom: 20px; margin-bottom: 20px; }}
        .news-item:last-child {{ border-bottom: none; }}
        h2 {{ color: #2c3e50; font-size: 20px; }}
        p {{ line-height: 1.6; font-size: 15px; color: #555; }}
        .footer {{ margin-top: 40px; font-size: 13px; color: #777; text-align: center; border-top: 1px solid #eaeaea; padding-top: 20px; }}
    </style>
</head>
<body>
    <header>
        <h1>SKYSPORT LIVE NEWS</h1>
    </header>
    <div class="container">
        {news_items_html}
        <div class="footer">
            Auto-updated hourly via RSS Feeds & GitHub Actions (No API Key required).
        </div>
    </div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("RSS news updated successfully in index.html.")
