import urllib.request
import xml.etree.ElementTree as ET

rss_url = "http://feeds.bbci.co.uk/sport/rss.xml"
news_items_html = ""

try:
    req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        xml_data = response.read()
        root = ET.fromstring(xml_data)
        
        count = 0
        for item in root.findall('./channel/item'):
            if count >= 8: # جلب ما يصل إلى 8 أخبار لتكون الصفحة غنية بالمحتوى
                break
            title = item.find('title').text if item.find('title') is not None else ""
            description = item.find('description').text if item.find('description') is not None else ""
            
            news_items_html += f"""
                <article class="news-card">
                    <h2>{title}</h2>
                    <p>{description}</p>
                </article>
            """
            count += 1
except Exception as e:
    news_items_html = "<div class='news-card'><p>Could not fetch latest sports news at this moment. Please check back soon.</p></div>"

# تصميم عصري واحترافي للموقع (Modern UI/UX)
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Skysport - Global Sports News</title>
    <style>
        :root {{
            --primary-color: #ff1801;
            --bg-color: #0f1016;
            --card-bg: #1a1c24;
            --text-main: #ffffff;
            --text-muted: #a0a5b8;
        }}
        body {{
            font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            background-color: var(--bg-color);
            color: var(--text-main);
        }}
        header {{
            background: linear-gradient(135deg, #1a1c24, #0f1016);
            color: #fff;
            padding: 35px 20px;
            text-align: center;
            border-bottom: 3px solid var(--primary-color);
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }}
        header h1 {{
            margin: 0;
            font-size: 32px;
            letter-spacing: 2px;
            text-transform: uppercase;
            font-weight: 800;
        }}
        header p {{
            margin: 8px 0 0 0;
            color: var(--text-muted);
            font-size: 14px;
        }}
        .container {{
            max-width: 900px;
            margin: 40px auto;
            padding: 0 20px;
        }}
        .news-card {{
            background: var(--card-bg);
            padding: 25px;
            margin-bottom: 25px;
            border-radius: 12px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.3);
            border-left: 5px solid var(--primary-color);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}
        .news-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 12px 30px rgba(255,24,1,0.2);
        }}
        .news-card h2 {{
            margin-top: 0;
            color: #ffffff;
            font-size: 22px;
            line-height: 1.4;
        }}
        .news-card p {{
            line-height: 1.7;
            color: var(--text-muted);
            font-size: 15px;
            margin-bottom: 0;
        }}
        .footer {{
            text-align: center;
            padding: 30px;
            font-size: 13px;
            color: var(--text-muted);
            border-top: 1px solid #222;
            margin-top: 50px;
            background: #0b0c10;
        }}
    </style>
</head>
<body>
    <header>
        <h1>SKYSPORT GLOBAL NEWS</h1>
        <p>Your ultimate destination for live global sports headlines</p>
    </header>
    <div class="container">
        {news_items_html}
    </div>
    <div class="footer">
        Auto-updated every hour via RSS Feeds & GitHub Actions. Designed for Sports Fans.
    </div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("Modern UI index.html generated successfully.")
