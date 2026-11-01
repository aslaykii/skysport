import os
import google.generativeai as genai

# 1. إعداد API Key
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("لم يتم العثور على GEMINI_API_KEY في الأسرار!")
genai.configure(api_key=api_key)

# 2. توليد خبر رياضي جديد بـ Gemini
model = genai.GenerativeModel("gemini-1.5-flash")
prompt = """
أنت محرر رياضي محترف لموقع SkySport. 
اكتب خبراً رياضياً جديداً ومثيراً عن أهم المستجدات في كرة القدم.
أعطني النتيجة حصرياً على شكل كود HTML جاهز لعنصر div يحتوي على عنوان فئة card و title ومحتوى قصير، بدون أي شي آخر خارجه، لكي يتم إضافته مباشرة للموقع.
"""

response = model.generate_content(prompt)
new_news_html = response.text.strip()

# 3. قراءة ملف index.html الحالي
try:
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
except FileNotFoundError:
    print("ملف index.html غير موجود!")
    exit(1)

# 4. إضافة الخبر الجديد للموقع أوتوماتيكياً
target_marker = '<div class="grid-cards">'
if target_marker in html_content:
    updated_html = html_content.replace(target_marker, f'{target_marker}\n{new_news_html}')
    
    # 5. حفظ التعديلات في ملف index.html
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(updated_html)
    print("تم تحديث الموقع ونشر الخبر الجديد بنجاح!")
else:
    print("لم يتم العثور على مكان إدراج الأخبار في index.html")
