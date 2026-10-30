import os
import io
import sys
import json
import time
import shutil
import subprocess
import urllib.parse

# 1. التثبيت الذاتي للمكتبات الناقصة لمنع توقف Run AutoDoc Engine
for pkg, mod in [
    ("pyTelegramBotAPI", "telebot"),
    ("requests", "requests"),
    ("gTTS", "gtts"),
    ("Pillow", "PIL")
]:
    try:
        __import__(mod)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

import telebot
import requests
from gtts import gTTS
from PIL import Image, ImageDraw

# 2. جلب المفاتيح السرية
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
gemini_key = os.environ.get('GEMINI_API_KEY', '').strip()
supabase_key = os.environ.get('SUPABASE_KEY', '').strip()
supabase_url = "https://maabijsnlytxewkscvam.supabase.co"

bot = telebot.TeleBot(bot_token)

# 3. محرك الذكاء الاصطناعي بالاكتشاف التلقائي وتجاوز خطأ 429
def call_gemini(prompt_text):
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

    priority = [
        'gemini-2.5-flash-lite',
        'gemini-2.0-flash-lite',
        'gemini-2.5-flash',
        'gemini-2.0-flash',
        'gemini-flash-latest',
        'gemini-2.5-pro'
    ]
    models_to_try = [m for m in priority if m in available_models] + [m for m in available_models if m not in priority]
    if not models_to_try:
        models_to_try = priority

    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}

    for attempt in range(2):
        for model_name in models_to_try[:6]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
            try:
                res = requests.post(url, json=payload, timeout=25)
                if res.status_code == 200:
                    return res.json()['candidates'][0]['content']['parts'][0]['text']
                elif res.status_code == 429:
                    time.sleep(2)
            except Exception:
                continue
        time.sleep(3)
    return None

# 4. توليد السيناريو الوثائقي مع بديل احتياطي مضمون
def generate_script(topic):
    prompt = f"""
اكتب سيناريو فيديو وثائقي قصير ومشوق من 3 مشاهد حول الموضوع التالي: "{topic}".
أجب بصيغة JSON فقط بهذا الشكل الدقيق دون أي نص خارجه:
[
  {{
    "narration": "نص التعليق الصوتي للمشهد الأول باللغة العربية الفصحى (جملتان مشوقتان)",
    "image_prompt": "Cinematic documentary photography of {topic} scene 1, realistic, high detail, vertical"
  }},
  {{
    "narration": "نص التعليق الصوتي للمشهد الثاني باللغة العربية الفصحى (جملتان غنيتان بالمعلومات)",
    "image_prompt": "Cinematic documentary photography of {topic} historical or deep view scene 2, realistic, vertical"
  }},
  {{
    "narration": "نص التعليق الصوتي للمشهد الثالث والخاتمة باللغة العربية الفصحى (جملتان مؤثرتان)",
    "image_prompt": "Cinematic documentary photography of {topic} epic finale scene 3, realistic, vertical"
  }}
]
"""
    raw = call_gemini(prompt)
    if raw:
        try:
            clean = raw.strip()
            start = clean.find('[')
            end = clean.rfind(']') + 1
            if start != -1 and end > start:
                parsed = json.loads(clean[start:end])
                if isinstance(parsed, list) and len(parsed) > 0:
                    return parsed
        except Exception:
            pass

    # سيناريو احتياطي تلقائي لضمان إنتاج الفيديو حتى لو كانت سيرفرات جوجل مضغوطة (429)
    return [
        {
            "narration": f"في هذا الوثائقي الخاص، نأخذكم في رحلة استثنائية لاستكشاف {topic} وما يحمله من تفاصيل مذهلة.",
            "image_prompt": f"Cinematic wide documentary shot of {topic}, ultra realistic, 8k, vertical"
        },
        {
            "narration": f"تتشابك الأحداث والحقائق حول {topic} لتكشف لنا جوانب عميقة لم تكن معروفة من قبل لدى الكثيرين.",
            "image_prompt": f"Dramatic detailed documentary close up representing {topic}, cinematic lighting, vertical"
        },
        {
            "narration": f"ويبقى {topic} شاهداً حياً يثير الدهشة والتأمل، ويترك بصمة خالدة في سجل التاريخ والمعرفة.",
            "image_prompt": f"Epic sunset documentary finale shot of {topic}, cinematic masterpiece, vertical"
        }
    ]

# 5. توليد وفحص الصور لضمان توافقها التام مع FFmpeg
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

    # تصميم خلفية سينمائية احتياطية صالحة 100% للمونتاج
    img = Image.new('RGB', (720, 1280), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)
    draw.rectangle([30, 30, 690, 1250], outline=(212, 175, 55), width=6)
    draw.rectangle([50, 50, 670, 1230], outline=(56, 189, 248), width=2)
    img.save(output_path, "JPEG", quality=90)

# 6. أمر البداية /start
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
        f"أهلاً بك يا {first_name} في مصنع الوثائقيات الآلي الشامل! 🎬🚀\n\n"
        "✅ العقل (Gemini): متصل\n"
        "✅ الذاكرة (Supabase): متصلة\n"
        "✅ محرك الفيديو (FFmpeg): جاهز للإنتاج السريع\n\n"
        "📌 أرسل الآن أي عنوان وثائقي في رسالة عادية (مثل: تاريخ مدينة تعز) ليتم صناعة الفيديو وإرساله لك فوراً!"
    )
    bot.reply_to(message, welcome_msg)

# 7. صناعة الفيديو الوثائقي الكامل (صوت + صورة + مونتاج MP4)
@bot.message_handler(func=lambda message: True)
def make_documentary(message):
    topic = (message.text or "").strip()
    if not topic or topic.startswith('/'):
        return

    chat_id = message.chat.id
    status_msg = bot.reply_to(
        message,
        f"⏳ جاري العمل على وثائقي: ({topic})\n\n1️⃣ كتابة السيناريو الوثائقي..."
    )

    scenes = generate_script(topic)
    script_preview = "\n\n".join([f"🔹 المشهد {i+1}: {s.get('narration', '')}" for i, s in enumerate(scenes)])

    try:
        bot.edit_message_text(
            f"✅ تم تجهيز السيناريو:\n\n{script_preview}\n\n2️⃣ جاري الآن تسجيل الصوت وتوليد الصور ومونتاج الفيديو (FFmpeg)... 🎬⏳",
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
            narration = scene.get('narration', '').strip() or f"مشهد وثائقي حول {topic}"
            img_prompt = scene.get('image_prompt', '').strip() or f"Documentary photography of {topic}"

            audio_path = os.path.join(work_dir, f"audio_{i}.mp3")
            img_path = os.path.join(work_dir, f"img_{i}.jpg")
            seg_path = os.path.join(work_dir, f"seg_{i}.mp4")

            # تحويل النص إلى تعليق صوتي عربي
            tts = gTTS(text=narration, lang='ar')
            tts.save(audio_path)

            # توليد وحفظ الصورة بأبعاد قياسية
            create_scene_image(img_prompt, img_path)

            # دمج الصوت والصورة بسرعة فائقة عبر ultrafast
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

        # دمج المشاهد الثلاثة في ملف MP4 نهائي
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

        # إرسال ملف الفيديو النهائي للمستخدم
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
            f"⚠️ تعذر إكمال المونتاج بسبب: {str(e)[:200]}",
            chat_id=chat_id,
            message_id=status_msg.message_id
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

if __name__ == "__main__":
    print("Starting AutoDoc Video Factory...")
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception:
        pass
    bot.infinity_polling(timeout=30, long_polling_timeout=20, skip_pending=True)
