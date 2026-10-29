import os
import json
import time
import urllib.parse
import telebot
import requests

# 1. جلب المفاتيح السرية
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
gemini_key = os.environ.get('GEMINI_API_KEY', '').strip()
supabase_key = os.environ.get('SUPABASE_KEY', '').strip()
supabase_url = "https://maabijsnlytxewkscvam.supabase.co"

bot = telebot.TeleBot(bot_token)

# 2. محرك الذكاء الاصطناعي مع الاكتشاف التلقائي
def call_gemini(prompt_text):
    models = ['gemini-2.0-flash', 'gemini-2.5-flash', 'gemini-flash-latest', 'gemini-pro']
    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}

    for model_name in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
        try:
            res = requests.post(url, json=payload, timeout=20)
            if res.status_code == 200:
                return res.json()['candidates'][0]['content']['parts'][0]['text']
            elif res.status_code == 429:
                time.sleep(2)
                continue
        except Exception:
            continue
    return None

# 3. توليد السيناريو الوثائقي المنظم
def generate_script(topic):
    prompt = f"""
أنت كاتب أفلام وثائقية محترف. اكتب سيناريو فيديو وثائقي قصير ومشوق من 3 مشاهد حول الموضوع التالي: "{topic}".
يجب أن ترد بصيغة JSON فقط بدون أي كلام إضافي، بهذا الشكل الدقيق:
[
  {{
    "narration": "نص التعليق الصوتي للمشهد الأول باللغة العربية الفصحى (جملتين)",
    "image_prompt": "Detailed cinematic documentary photography of [describe scene 1 in English], realistic, 8k"
  }},
  {{
    "narration": "نص التعليق الصوتي للمشهد الثاني باللغة العربية الفصحى (جملتين)",
    "image_prompt": "Detailed cinematic documentary photography of [describe scene 2 in English], realistic, 8k"
  }},
  {{
    "narration": "نص التعليق الصوتي للمشهد الثالث والخاتمة باللغة العربية الفصحى (جملتين)",
    "image_prompt": "Detailed cinematic documentary photography of [describe scene 3 in English], realistic, 8k"
  }}
]
"""
    raw = call_gemini(prompt)
    if not raw:
        return None
    try:
        clean = raw.strip()
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        start = clean.find('[')
        end = clean.rfind(']') + 1
        return json.loads(clean[start:end])
    except Exception:
        return None

# 4. أمر البداية /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "صديقي"
    
    try:
        headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}", "Content-Type": "application/json"}
        check_url = f"{supabase_url}/rest/v1/users?telegram_id=eq.{user_id}"
        res = requests.get(check_url, headers=headers, timeout=10)
        if res.status_code == 200 and len(res.json()) == 0:
            requests.post(f"{supabase_url}/rest/v1/users", headers=headers, json={
                "telegram_id": user_id, "username": first_name, "client_code": f"USER_{user_id}"
            }, timeout=10)
    except Exception:
        pass

    welcome_msg = (
        f"أهلاً بك يا {first_name} في مصنع الوثائقيات الآلي! 🎬🚀\n\n"
        "✅ الذاكرة والعقل يعملان بكفاءة تامة.\n\n"
        "💡 **كيف تستخدم المصنع الآن:**\n"
        "فقط أرسل لي في رسالة عادية أي موضوع وثائقي تريده (مثل: *تاريخ مدينة تعز* أو *أسرار الفضاء*) وسأقوم بتوليد السيناريو والروابط والصور وإرسالها لك فوراً!"
    )
    bot.reply_to(message, welcome_msg)

# 5. استقبال الموضوع وإنتاج السيناريو والصور الفورية
@bot.message_handler(func=lambda message: True)
def make_documentary(message):
    topic = message.text.strip()
    if topic.startswith('/'):
        return

    chat_id = message.chat.id
    status_msg = bot.reply_to(message, f"⏳ تم استلام الفكرة: ({topic})\n\n1️⃣ جاري كتابة السيناريو الوثائقي عبر الذكاء الاصطناعي...")

    scenes = generate_script(topic)
    if not scenes or not isinstance(scenes, list):
        bot.edit_message_text("⚠️ حدث ضغط مؤقت في الذكاء الاصطناعي، يرجى إعادة إرسال الموضوع بعد ثوانٍ.", chat_id=chat_id, message_id=status_msg.message_id)
        return

    # تجهيز الرد بالسيناريو وروابط الصور لكل مشهد
    result_text = f"🎉 **تم إنتاج السيناريو الوثائقي بنجاح!**\n📌 الموضوع: {topic}\n\n"
    for i, scene in enumerate(scenes):
        narration = scene.get('narration', '')
        img_prompt = scene.get('image_prompt', topic)
        img_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(img_prompt)}?width=720&height=1280&nologo=true"
        
        result_text += f"🔹 **المشهد {i+1}:**\n🗣️ `{narration}`\n🖼️ [رابط الصورة السينمائية]({img_url})\n\n"

    bot.edit_message_text(result_text, chat_id=chat_id, message_id=status_msg.message_id, disable_web_page_preview=False)

if __name__ == "__main__":
    print("AutoDoc Stable Factory is running...")
    bot.infinity_polling(skip_pending=True)
