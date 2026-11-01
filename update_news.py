import os
from google import genai

# 1. Configuration de la clé API avec le nouveau client officiel
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables!")

client = genai.Client(api_key=api_key)

# 2. Utilisation du modèle moderne et stable
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Generate a short sports news article in English about recent football highlights, formatted in clean HTML.",
)
news_html = response.text

# 3. Écriture du contenu dans index.html
html_content = f"""
<!DOCTYPE html>
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

print("News updated successfully!")
