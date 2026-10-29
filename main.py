import os
import telebot
import requests

# جلب المفاتيح السرية
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
gemini_key = os.environ.get('GEMINI_API_KEY', '').strip()
supabase_key = os.environ.get('SUPABASE_KEY', '').strip()

# رابط قاعدة البيانات
supabase_url = "https://maabijsnlytxewkscvam.supabase.co"

bot = telebot.TeleBot(bot_token)

def ask_gemini(prompt_text):
    payload = {
        "contents": [{
            "parts": [{"text": prompt_text}]
        }]
    }
    
    # قائمة بأشهر وأحدث الموديلات لضمان عمل أحدهم (قناص الموديلات)
    models_to_try = [
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash", 
        "gemini-pro"
    ]
    
    last_error = ""
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            last_error = f"{res.status_code}: {res.text[:60]}"
            
    return f"تعذر الاتصال بـ Gemini، آخر خطأ: {last_error}"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    msg = bot.reply_to(message, "جاري إيقاظ العقل والذاكرة... ⏳")
    
    db_status = "✅ متصلة بنجاح"

    # 1. الاتصال بقاعدة البيانات
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

    # 2. الاتصال بالذكاء الاصطناعي
    try:
        prompt = f"أنت مساعد ذكي في مصنع فيديوهات وثائقية. رحب بشكل قصير جداً ومحفز بشخص اسمه {first_name} يستخدم النظام لأول مرة."
        ai_reply = ask_gemini(prompt)
    except Exception as e:
        ai_reply = f"خطأ اتصال: {e}"

    # 3. النتيجة
    final_text = f"حالة المصنع الآلي (الإصدار النهائي):\n🗄️ الذاكرة: {db_status}\n\n🤖 رد الذكاء الاصطناعي:\n{ai_reply}"
    bot.edit_message_text(final_text, chat_id=message.chat.id, message_id=msg.message_id)

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling(skip_pending=True)
