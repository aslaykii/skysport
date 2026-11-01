import os
import google.generativeai as genai

# 1. Setup API Key
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables!")
genai.configure(api_key=api_key)

# 2. Generate new sports news with Gemini
model = genai.GenerativeModel("gemini-1.5-flash")
prompt = """
You are a professional sports editor for SkySport. 
Write a short, exciting sports news article about recent football updates.
Provide the output strictly as a ready-to-use HTML snippet containing a div with a card class, a title, and a short description paragraph, with no extra markdown formatting or text outside of it.
"""

response = model.generate_content(prompt)
new_news_html = response.text.strip()

# 3. Read current index.html file
try:
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
except FileNotFoundError:
    print("index.html file not found!")
    exit(1)

# 4. Automatically insert the new news into the site
target_marker = '<div class="grid-cards">'
if target_marker in html_content:
    updated_html = html_content.replace(target_marker, f'{target_marker}\n{new_news_html}')
    
    # 5. Save changes to index.html
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(updated_html)
    print("Website successfully updated with the new news!")
else:
    print("Target insertion marker not found in index.html")
