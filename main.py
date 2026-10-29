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

def get_ai_reply(prompt_text):
    # 1. تنفيذ طلب ListModels لجلب الموديلات المتاحة فعلياً على مفتاحك
    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}"
    available_models = []
    try:
        r = requests.get(list_url, timeout=10)
        if r.status_code == 200:
            for m in r.json().get('models', []):
                if 'generateContent' in m.get('supportedGenerationMethods', []):
                    name = m['name'].replace('models/', '')
                    if 'gemini' in name and 'embedding' not in name and 'imagen' not in name:
                        available_models.append(name)
    except Exception:
        pass

    # 2. ترتيب الموديلات الحديثة والأسرع أولاً لتفادي ضغط السيرفرات (503)
    priority = [
        'gemini-2.0-flash',
        'gemini-2.0-flash-lite',
        'gemini-2.5-flash',
        'gemini-2.5-flash-lite',
        'gemini-2.5-pro',
        'gemini-flash-latest'
    ]
    
    models_to_try = [m for m in priority if m in available_models] + [m for m in available_models if m not in priority]
    if not models_to_try:
        models_to_try = priority

    payload = {
        "contents": [{
            "parts": [{"text": prompt_text}]
        }]
    }

    # 3. تجربة الموديلات المتاحة حتى ينجح أول موديل متفرغ
    last_err = ""
    for model_name in models_to_try[:8]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
        try:
            res = requests.post(url, json=payload, timeout=15)
            if res.status_code == 200:
                return res.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                last_err = f"{model_name} ({res.status_code})"
        except Exception as e:
            last_err = str(e)
            continue

    return f"الموديلات المكتشفة ({', '.join(models_to_try[:4])}) مشغولة حالياً. آخر حالة: {last_err}"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    msg = bot.reply_to(message, "جاري فحص الموديلات المتاحة وتشغيل العقل والذاكرة... ⏳")
    
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
    final_text = f"حالة المصنع الآلي (الاكتشاف التلقائي):\n🗄️ الذاكرة: {db_status}\n\n🤖 رد الذكاء الاصطناعي:\n{ai_reply}"
    bot.edit_message_text(final_text, chat_id=message.chat.id, message_id=msg.message_id)

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling(skip_pending=True)
