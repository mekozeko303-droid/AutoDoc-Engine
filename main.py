import os
import telebot
import requests

# جلب المفاتيح السرية
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
gemini_key = os.environ.get('GEMINI_API_KEY', '').strip()
supabase_key = os.environ.get('SUPABASE_KEY', '').strip()

# تثبيت الرابط النظيف مباشرة
supabase_url = "https://maabijsnlytxewkscvam.supabase.co"

bot = telebot.TeleBot(bot_token)

def ask_gemini(prompt_text):
    # استخدام النسخة المستقرة لتفادي خطأ 503
    payload = {
        "contents": [{
            "parts": [{"text": prompt_text}]
        }]
    }
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
    res = requests.post(url, json=payload, timeout=15)
    if res.status_code == 200:
        return res.json()['candidates'][0]['content']['parts'][0]['text']
    else:
        return f"كود {res.status_code} ({res.text[:100]})"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    msg = bot.reply_to(message, "جاري الاتصال بالعقل والذاكرة (النسخة المستقرة)... ⏳")
    
    db_status = "✅ متصلة بنجاح"

    # 1. فحص وحفظ في قاعدة البيانات Supabase
    try:
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json"
        }
        check_url = f"{supabase_url}/rest/v1/users?telegram_id=eq.{user_id}"
        res = requests.get(check_url, headers=headers, timeout=10)
        
        if res.status_code == 200 and len(res.json()) == 0:
            insert_data = {
                "telegram_id": user_id,
                "username": first_name,
                "client_code": f"USER_{user_id}"
            }
            requests.post(f"{supabase_url}/rest/v1/users", headers=headers, json=insert_data, timeout=10)
        elif res.status_code != 200:
            db_status = f"⚠️ تنبيه قاعدة البيانات ({res.status_code}): {res.text[:80]}"
    except Exception as e:
        db_status = f"⚠️ خطأ: {e}"

    # 2. الاتصال بالذكاء الاصطناعي Gemini
    try:
        prompt = f"أنت مساعد ذكي في مصنع فيديوهات وثائقية. رحب بشكل قصير ومحفز بشخص اسمه {first_name}."
        ai_reply = ask_gemini(prompt)
    except Exception as e:
        ai_reply = f"خطأ اتصال بالذكاء الاصطناعي: {e}"

    # 3. إرسال النتيجة النهائية
    final_text = f"حالة المصنع الآلي (مستقر):\n🗄️ الذاكرة: {db_status}\n\n🤖 رد الذكاء الاصطناعي:\n{ai_reply}"
    bot.edit_message_text(final_text, chat_id=message.chat.id, message_id=msg.message_id)

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling(skip_pending=True)
