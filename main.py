import os
import telebot
import google.generativeai as genai
from supabase import create_client, Client

# 1. جلب المفاتيح السرية من الخزنة
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
gemini_key = os.environ.get('GEMINI_API_KEY')
supabase_url = os.environ.get('SUPABASE_URL')
supabase_key = os.environ.get('SUPABASE_KEY')

# 2. تشغيل أدوات المصنع
bot = telebot.TeleBot(bot_token)
genai.configure(api_key=gemini_key)
model = genai.GenerativeModel('gemini-1.5-flash')
supabase: Client = create_client(supabase_url, supabase_key)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    # رسالة مؤقتة لتطمين المستخدم
    msg = bot.reply_to(message, "جاري إيقاظ الذكاء الاصطناعي وفحص الذاكرة... ⏳")
    
    try:
        # 3. تجربة الذاكرة (قاعدة البيانات)
        user_exists = supabase.table('users').select('*').eq('telegram_id', user_id).execute()
        if not user_exists.data:
            supabase.table('users').insert({
                'telegram_id': user_id,
                'username': first_name,
                'client_code': f"USER_{user_id}"
            }).execute()
        
        # 4. تجربة العقل (الذكاء الاصطناعي)
        prompt = f"أنت مساعد ذكي في مصنع فيديوهات وثائقية. رحب بشكل قصير جداً ومحفز بشخص اسمه {first_name} يستخدم النظام لأول مرة."
        response = model.generate_content(prompt)
        
        # إرسال النتيجة النهائية
        bot.edit_message_text(
            f"تم ربط العقل والذاكرة بنجاح! ✅\n\n🤖 الذكاء الاصطناعي يقول لك:\n{response.text}", 
            chat_id=message.chat.id, 
            message_id=msg.message_id
        )
        
    except Exception as e:
        bot.edit_message_text(f"حدث خطأ أثناء الربط: {e}", chat_id=message.chat.id, message_id=msg.message_id)

if __name__ == "__main__":
    bot.infinity_polling()
