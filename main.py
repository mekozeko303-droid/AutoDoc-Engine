import os
import telebot

bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(bot_token)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً! المصنع الآلي يعمل بنجاح والربط سليم 100% 🚀")

if __name__ == "__main__":
    bot.infinity_polling()
  
