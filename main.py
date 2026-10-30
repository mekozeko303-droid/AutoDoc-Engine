import os
import io
import re
import sys
import time
import random
import shutil
import asyncio
import subprocess
import urllib.parse

# 1. التثبيت الذاتي لمحرك الصوت الوثائقي العصبي (edge-tts) وباقي المكتبات
for pkg, mod in [
    ("pyTelegramBotAPI", "telebot"),
    ("requests", "requests"),
    ("edge-tts", "edge_tts"),
    ("gTTS", "gtts"),
    ("Pillow", "PIL")
]:
    try:
        __import__(mod)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

import telebot
import requests
import edge_tts
from gtts import gTTS
from PIL import Image, ImageDraw

# 2. جلب المفاتيح السرية
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
gemini_key = os.environ.get('GEMINI_API_KEY', '').strip()
supabase_key = os.environ.get('SUPABASE_KEY', '').strip()
supabase_url = "https://maabijsnlytxewkscvam.supabase.co"

bot = telebot.TeleBot(bot_token)

# 3. تصحيح الإملاء العربي لضمان نطق فصيح وسليم
def normalize_arabic_topic(text):
    words = text.split()
    fixed_words = []
    common_taa = {"مدينه": "مدينة", "قلعه": "قلعة", "قريه": "قرية", "دوله": "دولة", "حضاره": "حضارة", "قصه": "قصة", "جزيره": "جزيرة"}
    for w in words:
        fixed_words.append(common_taa.get(w, w))
    return " ".join(fixed_words)

# 4. الاتصال بالذكاء الاصطناعي لتوليد سيناريو وثائقي عميق
def call_gemini(prompt_text):
    models = [
        'gemini-2.5-flash',
        'gemini-2.5-flash-lite',
        'gemini-2.0-flash',
        'gemini-flash-latest',
        'gemini-2.5-pro'
    ]
    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}

    for attempt in range(2):
        for model_name in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
            try:
                res = requests.post(url, json=payload, timeout=25)
                if res.status_code == 200:
                    return res.json()['candidates'][0]['content']['parts'][0]['text']
                elif res.status_code == 429:
                    time.sleep(3)
            except Exception:
                continue
    return None

def generate_script(topic):
    clean_topic = normalize_arabic_topic(topic)
    prompt = (
        f"أنت كاتب أفلام وثائقية بأسلوب ناشيونال جيوغرافيك والجزيرة الوثائقية. "
        f"اكتب سيناريو وثائقي فخم ومشوق من 3 مشاهد عن: ({clean_topic}).\n"
        "التزم حرفياً بهذا التنسيق في 3 أسطر فقط بدون أي مقدمات:\n"
        "SCENE1: [تعليق صوتي عربي فصيح ومهيب للمشهد الأول مع التشكيل الجزئي لأواخر الكلمات] || [Detailed English visual prompt of a specific landmark or historical scene of the topic]\n"
        "SCENE2: [تعليق صوتي عربي فصيح ومهيب للمشهد الثاني] || [Detailed English visual prompt of a second different angle, culture, or nature of the topic]\n"
        "SCENE3: [تعليق صوتي عربي فصيح ومهيب للخاتمة] || [Detailed English visual prompt of an epic panoramic sunset view of the topic]"
    )
    raw = call_gemini(prompt)
    parsed_scenes = []

    if raw:
        for line in raw.splitlines():
            line = line.strip()
            if "SCENE" in line and ":" in line:
                content = line.split(":", 1)[1].strip()
                if "||" in content:
                    ar_text, en_prompt = content.split("||", 1)
                else:
                    ar_text, en_prompt = content, f"Cinematic documentary photography of {clean_topic}, realistic, 8k"
                ar_text = re.sub(r'[\*\"\'\[\]]', '', ar_text).strip()
                en_prompt = re.sub(r'[\*\"\'\[\]]', '', en_prompt).strip()
                if len(ar_text) > 15:
                    parsed_scenes.append({
                        "narration": normalize_arabic_topic(ar_text),
                        "image_prompt": f"{en_prompt}, photorealistic, national geographic style, dramatic lighting, vertical 9:16"
                    })

    if len(parsed_scenes) < 3:
        parsed_scenes = [
            {
                "narration": f"هُنا تَتَجَلَّى عَظَمَةُ التَّارِيخِ؛ حَيْثُ نَأْخُذُكُمْ فِي رِحْلَةٍ وَثَائِقِيَّةٍ خَاصَّةٍ لِاسْتِكْشَافِ أَسْرَارِ {clean_topic} وَمَعَالِمِهَا الخَالِدَةِ.",
                "image_prompt": f"Cinematic aerial documentary photography of {clean_topic}, ancient fortress and mountains, photorealistic, 8k, vertical 9:16"
            },
            {
                "narration": f"تَتَعَانَقُ فِي {clean_topic} تَفَاصِيلُ العِمَارَةِ العَرِيقَةِ مَعَ سِحْرِ الطَّبِيعَةِ، لِتَرْوِيَ فُصُولاً مِنْ أَصَالَةِ المَاضِي وَعُمْقِ الحَضَارَةِ.",
                "image_prompt": f"Detailed street-level documentary shot of {clean_topic} heritage architecture and old city, dramatic sunlight, 8k, vertical 9:16"
            },
            {
                "narration": f"وَعَبْرَ تَعَاقُبِ العُصُورِ، تَبْقَى {clean_topic} شَاهِداً حَيّاً وَرَمْزاً شَامِخاً يَحْفَظُ ذَاكِرَةَ الأَجْيَالِ إِلَى الأَبَدِ.",
                "image_prompt": f"Epic golden hour sunset panoramic documentary view of {clean_topic}, cinematic masterpiece, 8k, vertical 9:16"
            }
        ]

    return parsed_scenes[:3]

# 5. توليد الصوت الوثائقي الرجالي الفخم والهادئ (حامد - مايكروسوفت العصبي)
async def _save_edge_tts(text, output_path):
    communicate = edge_tts.Communicate(
        text=text,
        voice="ar-SA-HamedNeural",
        rate="-6%",
        pitch="-4Hz"
    )
    await communicate.save(output_path)

def generate_voiceover(text, output_path):
    try:
        asyncio.run(_save_edge_tts(text, output_path))
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return
    except Exception:
        pass
    # بديل احتياطي في حال انقطاع سيرفر مايكروسوفت
    gTTS(text=text, lang='ar').save(output_path)

# 6. توليد 3 صور حقيقية مختلفة بدون علامة مائية ومع إعادة المحاولة
def create_scene_image(prompt_en, scene_idx, output_path):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    encoded = urllib.parse.quote(prompt_en)

    # 3 محاولات بمحرك Flux مع فاصل زمني لمنع حظر الصورتين الثانية والثالثة
    for attempt in range(3):
        seed = random.randint(10000, 999999) + (scene_idx * 777)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=720&height=1280&seed={seed}&nologo=true&model=flux"
        try:
            res = requests.get(url, headers=headers, timeout=35)
            if res.status_code == 200 and len(res.content) > 5000:
                img = Image.open(io.BytesIO(res.content)).convert('RGB')
                # قص الجزء السفلي الصغير لإزالة أي شعار محتمل ثم ضبط المقاس
                w, h = img.size
                img = img.crop((0, 0, w, int(h * 0.95))).resize((720, 1280), Image.Resampling.LANCZOS)
                img.save(output_path, "JPEG", quality=95)
                time.sleep(2)
                return
        except Exception:
            pass
        time.sleep(3)

    # سيرفر صور فوتوغرافية احتياطي لضمان عدم ظهور الشاشة الكحلية أبداً
    try:
        fallback_url = f"https://loremflickr.com/720/1280/mountain,castle,history/all?lock={scene_idx + int(time.time())}"
        res = requests.get(fallback_url, headers=headers, timeout=20)
        if res.status_code == 200 and len(res.content) > 5000:
            img = Image.open(io.BytesIO(res.content)).convert('RGB').resize((720, 1280), Image.Resampling.LANCZOS)
            img.save(output_path, "JPEG", quality=95)
            return
    except Exception:
        pass

    img = Image.new('RGB', (720, 1280), color=(15, 23, 42))
    img.save(output_path, "JPEG", quality=90)

# 7. أمر البداية /start
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
        f"أهلاً بك يا {first_name} في مصنع الوثائقيات السينمائي المطور! 🎬🎙️\n\n"
        "✅ الصوت: معلق وثائقي رجالي فخم وهادئ\n"
        "✅ الكاميرا: حركة سينمائية متدرجة (Ken Burns Zoom)\n"
        "✅ الصور: توليد 3 مشاهد كاملة بدقة عالية\n\n"
        "📌 أرسل الآن موضوع الوثائقي (مثل: تاريخ مدينة تعز) لتجربة النسخة السينمائية الجديدة!"
    )
    bot.reply_to(message, welcome_msg)

# 8. صناعة الفيديو السينمائي المتحرك
@bot.message_handler(func=lambda message: True)
def make_documentary(message):
    raw_topic = (message.text or "").strip()
    if not raw_topic or raw_topic.startswith('/'):
        return

    topic = normalize_arabic_topic(raw_topic)
    chat_id = message.chat.id
    status_msg = bot.reply_to(
        message,
        f"⏳ جاري إنتاج الفيلم الوثائقي السينمائي: ({topic})\n\n1️⃣ كتابة النص الوثائقي وتشكيله..."
    )

    scenes = generate_script(topic)
    script_preview = "\n\n".join([f"🎙️ المشهد {i+1}: {s['narration']}" for i, s in enumerate(scenes)])

    try:
        bot.edit_message_text(
            f"✅ تم تأليف النص الوثائقي:\n\n{script_preview}\n\n2️⃣ جاري تسجيل الصوت الرجالي الفخم، وتوليد الـ 3 صور، وتحريك الكاميرا سينمائياً... 🎬⏳",
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

            # توليد الصوت الرجالي العميق
            generate_voiceover(scene['narration'], audio_path)

            # توليد الصورة مع ضمان عدم الحظر
            create_scene_image(scene['image_prompt'], i, img_path)

            # حركة كاميرا سينمائية (تقريب بطيء لمشهد، وتبعيد بطيء للمشهد التالي + تلاشي ناعم)
            if i % 2 == 0:
                zoom_expr = "min(zoom+0.0012,1.25)"
            else:
                zoom_expr = "if(eq(on,1),1.25,max(1.0,zoom-0.0012))"

            vf_filter = (
                f"scale=1440:2560,"
                f"zoompan=z='{zoom_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=720x1280:fps=25,"
                f"fade=t=in:st=0:d=0.6"
            )

            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-framerate", "25", "-i", img_path,
                "-i", audio_path,
                "-vf", vf_filter,
                "-c:v", "libx264", "-preset", "veryfast",
                "-c:a", "aac", "-b:a", "192k",
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
                caption=f"🎬 الفيلم الوثائقي الاحترافي: {topic}\n🎙️ تعليق صوتي رجالي + تحريك سينمائي\n\n📝 النص:\n{script_preview[:700]}",
                reply_to_message_id=message.message_id
            )

        try:
            bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        except Exception:
            pass

    except Exception as e:
        bot.edit_message_text(
            f"⚠️ حدث خطأ أثناء المونتاج السينمائي: {str(e)[:150]}",
            chat_id=chat_id,
            message_id=status_msg.message_id
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

if __name__ == "__main__":
    print("AutoDoc Pro Engine is active...")
    while True:
        try:
            bot.remove_webhook()
            bot.infinity_polling(timeout=30, long_polling_timeout=20, skip_pending=True)
        except Exception as e:
            print(f"Polling restart: {e}")
            time.sleep(5)
