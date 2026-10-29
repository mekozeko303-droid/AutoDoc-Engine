import os
import telebot
import requests
import google.generativeai as genai

# جلب المفاتيح السرية
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
gemini_key = os.environ.get('GEMINI_API_KEY', '').strip()
supabase_key = os.environ.get('SUPABASE_KEY', '').strip()

# الروابط
supabase_url = "https://maabijsnlytxewkscvam.supabase.co"
bot = telebot.TeleBot(bot_token)

# تشغيل مكتبة جوجل
genai.configure(api_key=gemini_key)

def get_ai_reply(prompt):
    # القناص الذكي: تجربة أشهر الموديلات بالترتيب لضمان عمل أحدهم مع مفتاحك
    models = ['gemini-pro', 'gemini-1.5-flash-latest', 'gemini-1.0-pro', 'gemini-1.5-pro']
    last_err = ""
    for m in models:
        try:
            model = genai.GenerativeModel(m)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            last_err = str(e)
            continue
    return f"لم ينجح أي موديل. آخر خطأ: {last_err}"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    msg = bot.reply_to(message, "جاري تشغيل العقل والذاكرة (النسخة الذكية)... ⏳")
    
    db_status = "✅ متصلة بنجاح"

    # 1. الاتصال بالذاكرة (Supabase)
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
            db_status = f"⚠️ تنبيه الذاكرة: {res.status_code}"
    except Exception as e:
        db_status = f"⚠️ خطأ: {e}"

    # 2. الاتصال بالعقل (Gemini)
    prompt = f"أنت مساعد ذكي في مصنع فيديوهات وثائقية. رحب بشكل قصير جداً ومحفز بشخص اسمه {first_name} يستخدم النظام لأول مرة."
    ai_reply = get_ai_reply(prompt)

    # 3. إرسال النتيجة النهائية
    final_text = f"حالة المصنع الآلي (النسخة الذكية):\n🗄️ الذاكرة: {db_status}\n\n🤖 رد الذكاء الاصطناعي:\n{ai_reply}"
    bot.edit_message_text(final_text, chat_id=message.chat.id, message_id=msg.message_id)

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling(skip_pending=True)
