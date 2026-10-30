import os
import io
import time
import shutil
import subprocess
import urllib.parse
import telebot
import requests
from gtts import gTTS
from PIL import Image, ImageDraw

# 1. جلب المفاتيح السرية
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
gemini_key = os.environ.get('GEMINI_API_KEY', '').strip()
supabase_key = os.environ.get('SUPABASE_KEY', '').strip()
supabase_url = "https://maabijsnlytxewkscvam.supabase.co"

bot = telebot.TeleBot(bot_token)

# 2. الاتصال المباشر بموديلات Gemini الفعالة على مفتاحك
def call_gemini(prompt_text):
    models = [
        'gemini-2.5-flash-lite',
        'gemini-2.5-flash',
        'gemini-flash-latest',
        'gemini-2.5-pro'
    ]
    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}

    for model_name in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
        try:
            res = requests.post(url, json=payload, timeout=20)
            if res.status_code == 200:
                return res.json()['candidates'][0]['content']['parts'][0]['text']
            elif res.status_code == 429:
                time.sleep(2)
        except Exception:
            continue
    return None

# 3. كتابة السيناريو بطريقة نصية مضمونة 100% بدون أخطاء JSON
def generate_script(topic):
    prompt = (
        f"اكتب 3 فقرات قصيرة جداً ومشوقة باللغة العربية الفصحى لفيلم وثائقي عن: {topic}.\n"
        "اجعل كل فقرة في سطر مستقل يبدأ بكلمة SCENE: فقط بدون أي ترقيم أو مقدمات."
    )
    raw = call_gemini(prompt)
    scenes = []
    if raw:
        for line in raw.splitlines():
            clean = line.replace("SCENE:", "").replace("*", "").strip()
            if len(clean) > 20:
                scenes.append(clean)

    # ضمان وجود 3 مشاهد دائماً حتى في أوقات ضغط السيرفر
    if len(scenes) < 3:
        scenes = [
            f"نأخذكم اليوم في رحلة وثائقية خاصة لاستكشاف تاريخ وأسرار {topic} وما يحمله من معالم خالدة.",
            f"تتجلى في {topic} تفاصيل عريقة تجمع بين أصالة الماضي وروعة المكان التي تدهش كل من يشاهدها.",
            f"يبقى {topic} رمزاً حياً وشاهداً تاريخياً يروي للأجيال قصة حضارة لا تُنسى عبر العصور."
        ]

    return [
        {
            "narration": scenes[0],
            "image_prompt": f"Cinematic documentary wide shot of {topic}, historical architecture and nature, realistic, 8k, vertical"
        },
        {
            "narration": scenes[1],
            "image_prompt": f"Detailed documentary photography of {topic} landmarks and culture, dramatic lighting, realistic, vertical"
        },
        {
            "narration": scenes[2],
            "image_prompt": f"Epic golden hour sunset documentary view of {topic}, masterpiece photography, vertical"
        }
    ]

# 4. توليد وحفظ الصور بأبعاد قياسية للمونتاج
def create_scene_image(prompt_en, output_path):
    try:
        encoded = urllib.parse.quote(prompt_en)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=720&height=1280&nologo=true&seed={int(time.time())}"
        res = requests.get(url, timeout=25)
        if res.status_code == 200 and len(res.content) > 1000:
            img = Image.open(io.BytesIO(res.content)).convert('RGB')
            img = img.resize((720, 1280))
            img.save(output_path, "JPEG", quality=90)
            return
    except Exception:
        pass

    img = Image.new('RGB', (720, 1280), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)
    draw.rectangle([30, 30, 690, 1250], outline=(212, 175, 55), width=6)
    draw.rectangle([50, 50, 670, 1230], outline=(56, 189, 248), width=2)
    img.save(output_path, "JPEG", quality=90)

# 5. أمر البداية /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "صديقي"

    try:
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json"
        }
        check_url = f"{supabase_url}/rest/v1/users?telegram_id=eq.{user_id}"
        res = requests.get(check_url, headers=headers, timeout=10)
        if res.status_code == 200 and len(res.json()) == 0:
            requests.post(f"{supabase_url}/rest/v1/users", headers=headers, json={
                "telegram_id": user_id,
                "username": first_name,
                "client_code": f"USER_{user_id}"
            }, timeout=10)
    except Exception:
        pass

    welcome_msg = (
        f"أهلاً بك يا {first_name} في مصنع الوثائقيات الآلي (الإصدار النهائي الشامل)! 🎬🚀\n\n"
        "✅ العقل والذاكرة ومحرك الفيديو جاهزون تماماً.\n"
        "📌 أرسل الآن اسم الموضوع (مثل: مدينة تعز) ليبدأ تصنيع وإرسال الفيديو فوراً!"
    )
    bot.reply_to(message, welcome_msg)

# 6. إنتاج الفيديو الوثائقي الكامل وإرساله
@bot.message_handler(func=lambda message: True)
def make_documentary(message):
    topic = (message.text or "").strip()
    if not topic or topic.startswith('/'):
        return

    chat_id = message.chat.id
    status_msg = bot.reply_to(
        message,
        f"⏳ تم استلام الموضوع: ({topic})\n\n1️⃣ جاري تأليف السيناريو الوثائقي..."
    )

    scenes = generate_script(topic)
    script_preview = "\n\n".join([f"🔹 المشهد {i+1}: {s['narration']}" for i, s in enumerate(scenes)])

    try:
        bot.edit_message_text(
            f"✅ تم تجهيز السيناريو:\n\n{script_preview}\n\n2️⃣ جاري الآن تسجيل التعليق الصوتي وتوليد الصور ومونتاج الفيديو... 🎬⏳",
            chat_id=chat_id,
            message_id=status_msg.message_id
        )
    except Exception:
        pass

    work_dir = f"doc_{chat_id}_{int(time.time())}"
    os.makedirs(work_dir, exist_ok=True)
    segment_files = []

    try:
        for i, scene in enumerate(scenes):
            audio_path = os.path.join(work_dir, f"audio_{i}.mp3")
            img_path = os.path.join(work_dir, f"img_{i}.jpg")
            seg_path = os.path.join(work_dir, f"seg_{i}.mp4")

            gTTS(text=scene['narration'], lang='ar').save(audio_path)
            create_scene_image(scene['image_prompt'], img_path)

            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-framerate", "24", "-i", img_path,
                "-i", audio_path,
                "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
                "-c:a", "aac", "-b:a", "128k",
                "-pix_fmt", "yuv420p",
                "-shortest",
                seg_path
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
            segment_files.append(seg_path)

        concat_file = os.path.join(work_dir, "list.txt")
        with open(concat_file, "w", encoding="utf-8") as f:
            for seg in segment_files:
                f.write(f"file '{os.path.abspath(seg)}'\n")

        final_video = os.path.join(work_dir, "final_doc.mp4")
        concat_cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_file, "-c", "copy", final_video
        ]
        subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

        with open(final_video, "rb") as vf:
            bot.send_video(
                chat_id,
                vf,
                caption=f"🎉 تم إنتاج الفيلم الوثائقي بنجاح!\n📌 الموضوع: {topic}\n\n📝 السيناريو:\n{script_preview[:700]}",
                reply_to_message_id=message.message_id
            )

        try:
            bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        except Exception:
            pass

    except Exception as e:
        bot.edit_message_text(
            f"⚠️ حدث خطأ فني أثناء المونتاج: {str(e)[:150]}",
            chat_id=chat_id,
            message_id=status_msg.message_id
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

if __name__ == "__main__":
    print("AutoDoc Engine is active...")
    while True:
        try:
            bot.remove_webhook()
            bot.infinity_polling(timeout=30, long_polling_timeout=20, skip_pending=True)
        except Exception as e:
            print(f"Polling restart: {e}")
            time.sleep(5)
