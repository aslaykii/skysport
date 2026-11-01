import os
import google.generativeai as genai

# 1. إعداد API Key من أسرار GitHub
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# 2. إرسال الطلب لـ Gemini لكتابة خبر رياضي جديد ومثير
model = genai.GenerativeModel("gemini-1.5-flash")
prompt = """
أنت محرر رياضي محترف لموقع SkySport. 
اكتب خبراً رياضياً جديداً ومثيراً عن أهم المستجدات في كرة القدم العالمية أو المغربية لهذا اليوم.
أعطني النتيجة بتنسيق HTML بسيط ومناسب للعرض مباشرة (عنوان رئيسي ومقال قصير من فقرتين).
"""

response = model.generate_content(prompt)
news_html = response.text

print("تم توليد الخبر بنجاح بواسطة AI:")
print(news_html)
