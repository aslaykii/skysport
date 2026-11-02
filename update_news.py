import urllib.request
import xml.etree.ElementTree as ET

# Nastakhdmo RSS Feed rasmi w majani dyal BBC Sport bash n-jibo l-akhbar l-haqiqia
rss_url = "http://feeds.bbci.co.uk/sport/rss.xml"
news_items_html = ""

try:
    req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        xml_data = response.read()
        root = ET.fromstring(xml_data)
        
        count = 0
        for item in root.findall('./channel/item'):
            if count >= 6:
                break
            title = item.find('title').text if item.find('title'] is not None else ""
            description = item.find('description').text if item.find('description') is not None else ""
            
            news_items_html += f"""
                <div class="news-card">
                    <h2>{title}</h2>
                    <p>{description}</p>
                </div>
            """
            count += 1
except Exception as e:
    news_items_html = "<div class='news-card'><p>Could not fetch latest sports news at this moment. Please check back soon.</p></div>"

# Kitabat index.html b design responsive w jdid
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Skysport - Global Sports News</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            background: #f4f6f9;
            color: #333;
        }}
        header {{
            background: #111;
            color: #fff;
            padding: 25px;
            text-align: center;
            border-bottom: 4px solid #e74c3c;
        }}
        h1 {{
            margin: 0;
            font-size: 28px;
            letter-spacing: 1px;
        }}
        .container {{
            max-width: 850px;
            margin: 30px auto;
            padding: 0 20px;
        }}
        .news-card {{
            background: #ffffff;
            padding: 25px;
            margin-bottom: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            border-left: 5px solid #e74c3c;
        }}
        .news-card h2 {{
            margin-top: 0;
            color: #2c3e50;
            font-size: 20px;
        }}
        .news-card p {{
            line-height: 1.6;
            color: #555;
            margin-bottom: 0;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            font-size: 13px;
            color: #777;
            border-top: 1px solid #ddd;
            margin-top: 40px;
        }}
    </style>
</head>
<body>
    <header>
        <h1>SKYSPORT GLOBAL NEWS</h1>
    </header>
    <div class="container">
        {news_items_html}
    </div>
    <div class="footer">
        Auto-updated every hour via RSS Feeds & GitHub Actions.
    </div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("Index.html generated successfully with live RSS news.")
