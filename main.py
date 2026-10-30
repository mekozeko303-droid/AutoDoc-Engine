import os
import io
import re
import sys
import time
import wave
import base64
import random
import shutil
import asyncio
import subprocess
import urllib.parse

# 1. تثبيت وتحديث المكتبات (مع فرض تحديث edge-tts لأحدث نسخة)
subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pyTelegramBotAPI", "requests", "edge-tts", "gTTS", "Pillow"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

import telebot
import requests
import edge_tts
from gtts import gTTS
from PIL import Image, ImageEnhance

# 2. جلب المفاتيح السرية
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
gemini_key = os.environ.get('GEMINI_API_KEY', '').strip()
supabase_key = os.environ.get('SUPABASE_KEY', '').strip()
supabase_url = "https://maabijsnlytxewkscvam.supabase.co"

bot = telebot.TeleBot(bot_token)

# 3. تصحيح الإملاء لضمان نطق عربي سليم وطبيعي
def clean_arabic_text(text):
    replacements = {
        "مدينه": "مدينة", "قلعه": "قلعة", "قريه": "قرية",
        "دوله": "دولة", "حضاره": "حضارة", "قصه": "قصة",
        "جزيره": "جزيرة", "عاصمه": "عاصمة", "تاريخيه": "تاريخية"
    }
    words = text.split()
    return " ".join([replacements.get(w, w) for w in words])

# 4. الاتصال بـ Gemini لكتابة نص وثائقي مترابط ومعلومات حقيقية
def call_gemini(prompt_text):
    models = [
        'gemini-2.5-flash',
        'gemini-2.5-flash-lite',
        'gemini-2.0-flash',
        'gemini-flash-latest'
    ]
    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}

    for model_name in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
        for _ in range(2):
            try:
                res = requests.post(url, json=payload, timeout=25)
                if res.status_code == 200:
                    return res.json()['candidates'][0]['content']['parts'][0]['text']
                elif res.status_code == 429:
                    time.sleep(2)
            except Exception:
                pass
    return None

def generate_documentary_plan(topic):
    clean_topic = clean_arabic_text(topic)
    prompt = (
        f"أنت كاتب أفلام وثائقية محترف في قناة الجزيرة الوثائقية. اكتب نصاً وثائقياً مترابطاً وسلساً جداً وكأنه يرويه حكواتي بشري عن: ({clean_topic}).\n"
        "المطلوب 6 فقرات قصيرة متصلة السرد (كل فقرة جملة واحدة غنية بالمعلومات الحقيقية والتاريخية)، ومع كل فقرة وصف بصري دقيق باللغة الإنجليزية لتوليد الصورة.\n"
        "اكتب 6 أسطر فقط بهذا الشكل الدقيق دون أي مقدمات أو نجوم أو تشكيل مبالغ فيه:\n"
        "1|النص العربي للفقرة الأولى|Detailed English visual description for image 1\n"
        "2|النص العربي للفقرة الثانية|Detailed English visual description for image 2\n"
        "3|النص العربي للفقرة الثالثة|Detailed English visual description for image 3\n"
        "4|النص العربي للفقرة الرابعة|Detailed English visual description for image 4\n"
        "5|النص العربي للفقرة الخامسة|Detailed English visual description for image 5\n"
        "6|النص العربي للفقرة السادسة والخاتمة|Detailed English visual description for image 6"
    )
    raw = call_gemini(prompt)
    scenes = []

    if raw:
        for line in raw.splitlines():
            line = re.sub(r'[\*\#\`\"]', '', line).strip()
            parts = line.split('|')
            if len(parts) >= 3:
                narration = clean_arabic_text(parts[1].strip())
                img_prompt = parts[2].strip()
                if len(narration) > 12:
                    scenes.append({
                        "narration": narration,
                        "image_prompt": f"{img_prompt}, national geographic documentary photography, photorealistic, 8k, dramatic lighting, vertical 9:16"
                    })

    # ضمان 6 مشاهد كاملة دائماً
    default_scenes = [
        (f"تتربع {clean_topic} في قلب التاريخ كواحدة من أعرق الحواضر التي جمعت بين سحر الطبيعة وعبقرية الإنسان.", f"Epic aerial cinematic drone shot of {clean_topic} historic skyline and mountains, realistic documentary photography, 8k"),
        (f"على قمم جبالها وبين أسوارها القديمة، شُيّدت القلاع والحصون الشامخة التي صمدت لقرون طويلة أمام تقلبات الزمان.", f"Ancient historical fortress and citadel on a mountain peak in {clean_topic}, golden sunlight, photorealistic, 8k"),
        (f"وفي أزقتها العتيقة وأسواقها التراثية، ينبض بالحياة إرث ثقافي ومعماري فريد يعكس براعة البناء وروح الأصالة.", f"Old traditional heritage streets and historic architecture of {clean_topic}, cinematic street photography, 8k"),
        (f"كما ازدهرت فيها المدارس التاريخية والمساجد الأثرية التي جعلت منها منارة للعلم والفكر والفنون عبر العصور.", f"Ancient historic domes, minarets, and stone courtyard in {clean_topic}, dramatic rays of light, photorealistic, 8k"),
        (f"وتحيط بها المدرجات الخضراء والوديان الخصبة التي تمنح المكان لوحة طبيعية ساحرة تأسر قلوب الزائرين.", f"Lush green mountain terraces and dramatic valleys surrounding {clean_topic}, misty morning documentary shot, 8k"),
        (f"لتبقى {clean_topic} اليوم شاهداً حياً ورمزاً خالداً يروي للأجيال قصة حضارة عريقة لا تنطفئ شمسها أبداً.", f"Breathtaking golden sunset panoramic view over {clean_topic} with warm glowing lights, masterpiece documentary, 8k")
    ]

    while len(scenes) < 6:
        idx = len(scenes)
        scenes.append({
            "narration": default_scenes[idx][0],
            "image_prompt": default_scenes[idx][1]
        })

    return scenes[:6]

# 5. توليد صوت بشري طبيعي ومتصل بالكامل (Gemini Native Human Audio + Edge Neural)
async def _edge_human_tts(full_text, output_mp3):
    # استخدام صوت شاكر الوثائقي الطبيعي بدون أي تشويه للترددات
    voices = ["ar-EG-ShakirNeural", "ar-AE-HamdanNeural", "ar-SA-HamedNeural"]
    for v in voices:
        try:
            comm = edge_tts.Communicate(text=full_text, voice=v, rate="+0%", pitch="+0Hz")
            await comm.save(output_mp3)
            if os.path.exists(output_mp3) and os.path.getsize(output_mp3) > 2000:
                return True
        except Exception:
            continue
    return False

def generate_continuous_human_voice(scenes, output_mp3):
    # دمج النص بالكامل في سرد بشري واحد متصل بوقفات تنفس طبيعية لمنع أي تقطيع
    full_narration = " ، ... ".join([s["narration"].strip() for s in scenes]) + " ."

    # المحرك الأول: صوت Gemini 2.5 البشري الطبيعي المباشر (Charon)
    tts_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={gemini_key}"
    payload = {
        "contents": [{"parts": [{"text": full_narration}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": "Charon"}
                }
            }
        }
    }
    try:
        res = requests.post(tts_url, json=payload, timeout=35)
        if res.status_code == 200:
            part = res.json()['candidates'][0]['content']['parts'][0]
            if 'inlineData' in part:
                pcm_bytes = base64.b64decode(part['inlineData']['data'])
                wav_tmp = output_mp3 + ".wav"
                with wave.open(wav_tmp, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(24000)
                    wf.writeframes(pcm_bytes)
                subprocess.run([
                    "ffmpeg", "-y", "-i", wav_tmp,
                    "-af", "apad=pad_dur=0.6",
                    "-c:a", "libmp3lame", "-b:a", "192k", output_mp3
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                os.remove(wav_tmp)
                if os.path.exists(output_mp3) and os.path.getsize(output_mp3) > 2000:
                    return
    except Exception:
        pass

    # المحرك الثاني: المعلق البشري العصبي المحدّث من مايكروسوفت (شريط صوتي واحد متصل)
    raw_mp3 = output_mp3 + "_raw.mp3"
    try:
        ok = asyncio.run(_edge_human_tts(full_narration, raw_mp3))
        if ok:
            subprocess.run([
                "ffmpeg", "-y", "-i", raw_mp3,
                "-af", "apad=pad_dur=0.6",
                "-c:a", "libmp3lame", "-b:a", "192k", output_mp3
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            os.remove(raw_mp3)
            return
    except Exception:
        pass

    # بديل أخير في حال انقطاع كل السيرفرات
    gTTS(text=full_narration, lang='ar').save(output_mp3)

def get_audio_duration(audio_path):
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", audio_path
        ]).decode().strip()
        return max(float(out), 18.0)
    except Exception:
        return 30.0

# 6. جلب 6 صور حقيقية ومختلفة (Pollinations + Wikimedia Commons + Picsum)
def fetch_wikimedia_photos(topic):
    urls = []
    headers = {"User-Agent": "AutoDocBot/3.0 (https://github.com/)"}
    for lang in ["ar", "en"]:
        try:
            api = f"https://{lang}.wikipedia.org/w/api.php"
            params = {
                "action": "query", "generator": "search", "gsrsearch": topic,
                "gsrlimit": 10, "prop": "pageimages", "piprop": "original", "format": "json"
            }
            r = requests.get(api, params=params, headers=headers, timeout=10)
            pages = r.json().get("query", {}).get("pages", {})
            for p in pages.values():
                orig = p.get("original", {}).get("source", "")
                if orig and orig.lower().endswith((".jpg", ".jpeg", ".png")):
                    urls.append(orig)
        except Exception:
            pass
    return urls

def save_formatted_image(raw_bytes, output_path):
    img = Image.open(io.BytesIO(raw_bytes)).convert('RGB')
    w, h = img.size
    # قص أي علامة مائية سفلية وضبط نسبة الأبعاد للعرض العمودي
    img = img.crop((0, 0, w, int(h * 0.94)))
    img = img.resize((900, 1600), Image.Resampling.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.08)
    img = ImageEnhance.Color(img).enhance(1.15)
    img.save(output_path, "JPEG", quality=95)

def download_all_scene_images(scenes, topic, work_dir):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36"}
    wiki_urls = fetch_wikimedia_photos(topic)
    image_paths = []

    for i, scene in enumerate(scenes):
        out_path = os.path.join(work_dir, f"img_{i}.jpg")
        saved = False
        encoded = urllib.parse.quote(scene["image_prompt"])
        models = ["flux", "turbo"]

        # المحاولة عبر Pollinations بموديلات وبذور مختلفة
        for m in models:
            seed = random.randint(10000, 999999) + (i * 1337)
            url = f"https://image.pollinations.ai/prompt/{encoded}?width=768&height=1344&seed={seed}&nologo=true&model={m}"
            try:
                res = requests.get(url, headers=headers, timeout=25)
                if res.status_code == 200 and len(res.content) > 8000:
                    save_formatted_image(res.content, out_path)
                    saved = True
                    time.sleep(1.5)
                    break
            except Exception:
                pass

        # البديل الثاني: صور حقيقية من ويكيبيديا لنفس الموضوع
        if not saved and wiki_urls:
            while wiki_urls:
                w_url = wiki_urls.pop(0)
                try:
                    res = requests.get(w_url, headers=headers, timeout=15)
                    if res.status_code == 200 and len(res.content) > 8000:
                        save_formatted_image(res.content, out_path)
                        saved = True
                        break
                except Exception:
                    pass

        # البديل الثالث: صور فوتوغرافية عالية الدقة لضمان عدم ظهور شاشة فارغة أبداً
        if not saved:
            try:
                pic_url = f"https://picsum.photos/seed/{int(time.time()) + i*99}/900/1600"
                res = requests.get(pic_url, headers=headers, timeout=15)
                if res.status_code == 200:
                    save_formatted_image(res.content, out_path)
                    saved = True
            except Exception:
                pass

        if not saved:
            Image.new('RGB', (900, 1600), color=(25, 35, 60)).save(out_path, "JPEG")

        image_paths.append(out_path)

    return image_paths

# 7. تحريك الكاميرا القوي والمتنوع (6 حركات سينمائية مختلفة)
def render_animated_scene(img_path, duration, move_index, seg_path):
    fps = 25
    frames = max(int(duration * fps), 50)
    fade_out_start = max(duration - 0.4, 0.5)

    # 6 حركات كاميرا قوية وواضحة (تقريب قوي، تبعيد، تحريك أفقي، تحريك عمودي، وحركة قطرية)
    movements = [
        # 1. زوم أمامي قوي وسلس (1.0 -> 1.38)
        f"z='1.0+0.38*(on/{frames})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
        # 2. زوم عكسي سينمائي من الداخل للخارج (1.38 -> 1.0)
        f"z='1.38-0.38*(on/{frames})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
        # 3. حركة بانورامية من اليسار إلى اليمين مع تقريب
        f"z='1.28':x='(iw-iw/zoom)*(on/{frames})':y='(ih-ih/zoom)/2'",
        # 4. حركة بانورامية من اليمين إلى اليسار مع تقريب
        f"z='1.28':x='(iw-iw/zoom)*(1-on/{frames})':y='(ih-ih/zoom)/2'",
        # 5. حركة كاميرا عمودية من الأسفل للأعلى مع زوم
        f"z='1.26':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)*(1-on/{frames})'",
        # 6. حركة قطرية ديناميكية مع تقريب تدريجي
        f"z='1.12+0.28*(on/{frames})':x='(iw-iw/zoom)*(on/{frames})':y='(ih-ih/zoom)*(on/{frames})'"
    ]
    chosen_move = movements[move_index % len(movements)]

    vf = (
        f"scale=900:1600,"
        f"zoompan={chosen_move}:d={frames}:s=720x1280:fps={fps},"
        f"fade=t=in:st=0:d=0.35,fade=t=out:st={fade_out_start:.2f}:d=0.35"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", img_path,
        "-vf", vf,
        "-t", f"{duration:.2f}",
        "-c:v", "libx264", "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        seg_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

# 8. أوامر البوت وتوليد الفيديو
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "صديقي"
    try:
        headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}", "Content-Type": "application/json"}
        res = requests.get(f"{supabase_url}/rest/v1/users?telegram_id=eq.{user_id}", headers=headers, timeout=10)
        if res.status_code == 200 and len(res.json()) == 0:
            requests.post(f"{supabase_url}/rest/v1/users", headers=headers, json={
                "telegram_id": user_id, "username": first_name, "client_code": f"USER_{user_id}"
            }, timeout=10)
    except Exception:
        pass

    bot.reply_to(
        message,
        f"أهلاً بك يا {first_name} في مصنع الوثائقيات السينمائي (نسخة الـ 6 مشاهد والصوت البشري المتصل)! 🎬🎙️\n\n"
        "✨ المزايا المفعّلة الآن:\n"
        "• 6 مشاهد مصورة متلاحقة لكل فيديو\n"
        "• 6 حركات كاميرا قوية ومتنوعة (زوم، تبعيد، تحريك بانورامي وقطري)\n"
        "• تعليق صوتي بشري متصل بالكامل بدون أي تقطيع بين الجمل\n\n"
        "📌 أرسل الآن اسم الموضوع (مثل: مدينة تعز) لتجربة الإصدار الجديد!"
    )

@bot.message_handler(func=lambda message: True)
def make_documentary(message):
    raw_topic = (message.text or "").strip()
    if not raw_topic or raw_topic.startswith('/'):
        return

    topic = clean_arabic_text(raw_topic)
    chat_id = message.chat.id
    status_msg = bot.reply_to(
        message,
        f"🎬 جاري إنتاج الوثائقي الموسّع (6 مشاهد): ({topic})\n\n1️⃣ تأليف السرد الوثائقي المتصل..."
    )

    scenes = generate_documentary_plan(topic)
    script_preview = "\n".join([f"• {s['narration']}" for s in scenes])

    try:
        bot.edit_message_text(
            f"✅ تم تأليف النص الوثائقي (6 مشاهد):\n\n{script_preview}\n\n2️⃣ جاري الآن تسجيل الصوت البشري المتصل، وتوليد 6 صور، وتطبيق 6 حركات كاميرا سينمائية... ⏳🎥",
            chat_id=chat_id,
            message_id=status_msg.message_id
        )
    except Exception:
        pass

    work_dir = f"doc_{chat_id}_{int(time.time())}"
    os.makedirs(work_dir, exist_ok=True)

    try:
        # أ) توليد الصوت البشري المتصل في ملف واحد
        master_audio = os.path.join(work_dir, "master_voice.mp3")
        generate_continuous_human_voice(scenes, master_audio)
        total_audio_dur = get_audio_duration(master_audio)

        # ب) جلب الـ 6 صور
        image_paths = download_all_scene_images(scenes, topic, work_dir)

        # ج) توزيع زمن الصوت على المشاهد الـ 6 بدقة حسب طول كل جملة
        char_counts = [max(len(s["narration"]), 10) for s in scenes]
        total_chars = sum(char_counts)
        segment_files = []

        for i, img_path in enumerate(image_paths):
            scene_dur = max(total_audio_dur * (char_counts[i] / total_chars), 3.2)
            seg_path = os.path.join(work_dir, f"seg_{i}.mp4")
            render_animated_scene(img_path, scene_dur, i, seg_path)
            segment_files.append(seg_path)

        # د) دمج المشاهد الـ 6 المتحركة مع الشريط الصوتي البشري المتصل
        concat_list = os.path.join(work_dir, "list.txt")
        with open(concat_list, "w", encoding="utf-8") as f:
            for seg in segment_files:
                f.write(f"file '{os.path.abspath(seg)}'\n")

        silent_video = os.path.join(work_dir, "visuals.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_list, "-c", "copy", silent_video
        ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

        final_video = os.path.join(work_dir, "final_doc.mp4")
        subprocess.run([
            "ffmpeg", "-y",
            "-i", silent_video,
            "-i", master_audio,
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", final_video
        ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

        with open(final_video, "rb") as vf:
            bot.send_video(
                chat_id,
                vf,
                caption=f"🎬 الوثائقي الكامل (6 مشاهد متحركة): {topic}\n🎙️ تعليق صوتي بشري متصل\n\n📝 النص:\n{script_preview[:750]}",
                reply_to_message_id=message.message_id
            )

        try:
            bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        except Exception:
            pass

    except Exception as e:
        bot.edit_message_text(
            f"⚠️ حدث خطأ أثناء الإنتاج: {str(e)[:160]}",
            chat_id=chat_id,
            message_id=status_msg.message_id
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

if __name__ == "__main__":
    print("AutoDoc Cinema v3 Engine is running...")
    while True:
        try:
            bot.remove_webhook()
            bot.infinity_polling(timeout=30, long_polling_timeout=20, skip_pending=True)
        except Exception as e:
            print(f"Polling restart: {e}")
            time.sleep(5)
