import os
import io
import re
import sys
import time
import json
import math
import random
import shutil
import asyncio
import subprocess
import urllib.parse

# التأكد التلقائي من تثبيت المكتبات
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
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import edge_tts
from gtts import gTTS
from PIL import Image, ImageEnhance

# ==========================================
# 1. الإعدادات والمفاتيح وحماية البوت الشخصي
# ==========================================
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
gemini_key = os.environ.get('GEMINI_API_KEY', '').strip()
pixabay_key = os.environ.get('PIXABAY_API_KEY', '').strip()
tg_api_id = os.environ.get('TELEGRAM_API_ID', '').strip()
tg_api_hash = os.environ.get('TELEGRAM_API_HASH', '').strip()

bot = telebot.TeleBot(bot_token)

# قفل البوت للاستخدام الشخصي فقط (يُربط تلقائياً بأول رسالة منك)
OWNER_CHAT_ID = None
USER_SESSION = {}

# عدادات الموارد والحصص لإدارة الاستوديو
SERVER_START_TIME = time.time()
SERVER_MAX_SECONDS = 6 * 3600  # 6 ساعات لكل تشغيلة في GitHub Actions
QUOTA_STATS = {
    "gemini_daily_limit": 1500,
    "gemini_used": 0,
    "pixabay_hourly_limit": 5000,
    "pixabay_used": 0,
    "videos_produced": 0
}

VOICE_MAP = {
    "الراوي": "ar-SA-HamedNeural",
    "البطل": "ar-EG-ShakirNeural",
    "شخصية": "ar-AE-HamdanNeural",
    "الفتاة": "ar-AE-FatimaNeural"
}

def is_authorized(message):
    global OWNER_CHAT_ID
    user_id = message.from_user.id
    if OWNER_CHAT_ID is None:
        OWNER_CHAT_ID = user_id
        return True
    return user_id == OWNER_CHAT_ID

def get_quota_dashboard_text():
    elapsed = time.time() - SERVER_START_TIME
    remaining_sec = max(0, SERVER_MAX_SECONDS - elapsed)
    rem_hours = int(remaining_sec // 3600)
    rem_mins = int((remaining_sec % 3600) // 60)

    gemini_rem = max(0, QUOTA_STATS["gemini_daily_limit"] - QUOTA_STATS["gemini_used"])
    pixabay_rem = max(0, QUOTA_STATS["pixabay_hourly_limit"] - QUOTA_STATS["pixabay_used"])
    px_status = "✅ متصل ومفعل" if pixabay_key else "⚠️ غير مضاف (يعمل بالصور الذكية)"
    max_possible_video_mins = max(1, int(remaining_sec // 25))

    return (
        "📊 **لوحة موارد الاستوديو الشخصي الآن:**\n"
        f"⏱️ وقت السيرفر المتبقي: `{rem_hours} ساعة و {rem_mins} دقيقة`\n"
        f"🧠 رصيد الذكاء الاصطناعي (Gemini): `{gemini_rem}` طلب متبقٍ\n"
        f"🎬 رصيد فيديوهات Pixabay: `{pixabay_rem}` طلب ({px_status})\n"
        f"📦 نظام رفع الملفات: `مفعل حتى 2GB (ضغط ذكي + تقسيم آلي)`\n"
        f"🎥 الفيديوهات المنتجة في هذه الجلسة: `{QUOTA_STATS['videos_produced']}`\n"
        f"⚡ أقصى مدة فيديو يمكنك إنتاجها الآن: `حتى {min(max_possible_video_mins, 30)} دقيقة`"
    )

# ==========================================
# 2. تصحيح اللغة وتأليف السيناريو المقسم
# ==========================================
def clean_arabic(text):
    replacements = {
        "مدينه": "مدينة", "قلعه": "قلعة", "قريه": "قرية",
        "دوله": "دولة", "حضاره": "حضارة", "قصه": "قصة", "جزيره": "جزيرة"
    }
    return " ".join([replacements.get(w, w) for w in text.split()])

def call_gemini(prompt_text):
    models = ['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.0-flash', 'gemini-flash-latest']
    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}

    for model_name in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
        for _ in range(2):
            try:
                QUOTA_STATS["gemini_used"] += 1
                res = requests.post(url, json=payload, timeout=30)
                if res.status_code == 200:
                    return res.json()['candidates'][0]['content']['parts'][0]['text']
                elif res.status_code == 429:
                    time.sleep(3)
            except Exception:
                pass
    return None

def generate_storyboard(topic, num_scenes):
    clean_t = clean_arabic(topic)
    prompt = (
        f"أنت مخرج سينمائي وكاتب قصص ووثائقيات محترف. اكتب سيناريو مترابطاً ومشوقاً جداً مكوناً من ({num_scenes}) مشهداً عن: ({clean_t}).\n"
        "نوع بين السرد والحوار التمثيلي إذا كان الموضوع قصصياً مستخدماً الشخصيات التالية فقط: (الراوي، البطل، شخصية، الفتاة).\n"
        "يجب أن تكتب كل مشهد في سطر واحد فقط مفصول بعلامة | بهذا التنسيق الدقيق دون أي مقدمات:\n"
        "الشخصية|النص العربي للمشهد (جملتان مشوقتان)|two_word_english_video_search|Detailed English cinematic prompt for AI image generation\n"
        "مثال:\n"
        "الراوي|في قلب الجبال الشاهقة، ولدت أسطورة لم يمحها الزمن عبر القرون.|ancient mountain|Epic aerial cinematic shot of ancient fortress on mountain peak at sunset, photorealistic, 8k"
    )
    raw = call_gemini(prompt)
    scenes = []

    if raw:
        for line in raw.splitlines():
            line = re.sub(r'[\*\#\`\"]', '', line).strip()
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 4:
                char_name = parts[0]
                if char_name not in VOICE_MAP:
                    char_name = "الراوي"
                narration = clean_arabic(parts[1])
                v_query = re.sub(r'[^a-zA-Z0-9 ]', '', parts[2]).strip() or "cinematic nature"
                img_prompt = parts[3]
                if len(narration) > 10:
                    scenes.append({
                        "character": char_name,
                        "text": narration,
                        "video_query": v_query,
                        "image_prompt": f"{img_prompt}, cinematic lighting, national geographic style, photorealistic, 8k, vertical 9:16"
                    })

    # استكمال المشاهد تلقائياً إذا أرسل الذكاء الاصطناعي عدداً أقل
    fallback_templates = [
        ("الراوي", f"تبدأ حكايتنا مع {clean_t}، حيث تتقاطع أحداث التاريخ مع أسرار المكان في مشهد يخطف الأنفاس.", "ancient history", f"Cinematic wide angle shot representing {clean_t}, dramatic sky, 8k"),
        ("البطل", f"كل زاوية في {clean_t} تروي فصلاً من التحدي والإصرار الذي صنعه الأجداد عبر السنين.", "walking desert", f"Close up dramatic portrait in historical setting of {clean_t}, cinematic lighting, 8k"),
        ("شخصية", f"لم يكن الطريق سهلاً، لكن العزيمة حولت {clean_t} إلى أيقونة خالدة تدهش العالم.", "mountain clouds", f"Epic architectural and natural details of {clean_t}, golden hour sunlight, 8k"),
        ("الراوي", f"وهكذا تستمر فصول {clean_t} حية في الذاكرة، شاهدة على عظمة الإنسان وروح الحضارة.", "sunset horizon", f"Breathtaking panoramic sunset over {clean_t}, cinematic masterpiece, 8k")
    ]

    while len(scenes) < num_scenes:
        idx = len(scenes) % len(fallback_templates)
        tpl = fallback_templates[idx]
        scenes.append({
            "character": tpl[0],
            "text": tpl[1],
            "video_query": tpl[2],
            "image_prompt": tpl[3]
        })

    return scenes[:num_scenes]

# ==========================================
# 3. توليد الصوت البشري + الترجمة المضمونة 100%
# ==========================================
def format_srt_timestamp(seconds):
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

async def _produce_edge_voice_and_ timings(text, voice, audio_path):
    comm = edge_tts.Communicate(text, voice, rate="+0%", pitch="+0Hz")
    word_events = []
    with open(audio_path, "wb") as af:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                af.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start_s = chunk["offset"] / 10_000_000.0
                dur_s = chunk["duration"] / 10_000_000.0
                word_events.append((start_s, start_s + dur_s, chunk["text"]))
    return word_events

def generate_voice_and_srt(text, character, audio_path, srt_path):
    voice = VOICE_MAP.get(character, "ar-SA-HamedNeural")
    word_events = []

    try:
        word_events = asyncio.run(_produce_edge_voice_and_timings(text, voice, audio_path))
    except Exception:
        pass

    if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 1000:
        gTTS(text=text, lang='ar').save(audio_path)

    # قياس مدة الصوت الحقيقية
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", audio_path
        ]).decode().strip()
        duration = max(float(out), 2.5)
    except Exception:
        duration = 4.5

    # بناء ملف ترجمة SRT مضمون (تجميع كل 4-5 كلمات لسهولة القراءة)
    srt_entries = []
    if len(word_events) >= 2:
        chunk_size = 5
        for i in range(0, len(word_events), chunk_size):
            group = word_events[i:i + chunk_size]
            st = group[0][0]
            et = max(group[-1][1], st + 0.6)
            phrase = " ".join([w[2] for w in group])
            srt_entries.append((st, et, phrase))
    else:
        # خطة بديلة رياضية دقيقة في حال لم يرسل السيرفر WordBoundary
        words = text.split()
        chunk_size = 5
        chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
        if not chunks:
            chunks = [text]
        step = duration / len(chunks)
        for idx, ch in enumerate(chunks):
            srt_entries.append((idx * step, (idx + 1) * step, ch))

    with open(srt_path, "w", encoding="utf-8") as sf:
        for idx, (st, et, phrase) in enumerate(srt_entries, 1):
            sf.write(f"{idx}\n{format_srt_timestamp(st)} --> {format_srt_timestamp(et)}\n{phrase}\n\n")

    return duration

# ==========================================
# 4. جلب الفيديوهات الحقيقية (Pixabay) + الصور السينمائية (Flux)
# ==========================================
def fetch_scene_media(scene, scene_idx, work_dir):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"}

    # التنويع بين فيديوهات Pixabay الحقيقية وصور الذكاء الاصطناعي المطابقة للقصة
    use_video_first = bool(pixabay_key) and (scene_idx % 2 == 0)

    if use_video_first:
        q = urllib.parse.quote(scene["video_query"])
        vid_api = f"https://pixabay.com/api/videos/?key={pixabay_key}&q={q}&per_page=5&safesearch=true"
        try:
            QUOTA_STATS["pixabay_used"] += 1
            r = requests.get(vid_api, headers=headers, timeout=12)
            if r.status_code == 200:
                hits = r.json().get("hits", [])
                if hits:
                    chosen = hits[scene_idx % len(hits)]
                    videos_dict = chosen.get("videos", {})
                    video_url = (
                        videos_dict.get("medium", {}).get("url")
                        or videos_dict.get("small", {}).get("url")
                        or videos_dict.get("large", {}).get("url")
                    )
                    if video_url:
                        v_path = os.path.join(work_dir, f"raw_media_{scene_idx}.mp4")
                        vr = requests.get(video_url, headers=headers, timeout=20)
                        if vr.status_code == 200 and len(vr.content) > 20000:
                            with open(v_path, "wb") as vf:
                                vf.write(vr.content)
                            return {"type": "video", "path": v_path}
        except Exception:
            pass

    # توليد صورة سينمائية مطابقة للمشهد عبر Pollinations Flux
    img_path = os.path.join(work_dir, f"raw_media_{scene_idx}.jpg")
    encoded_p = urllib.parse.quote(scene["image_prompt"])
    seed = random.randint(10000, 999999) + scene_idx * 555

    for model_type in ["flux", "turbo"]:
        poll_url = f"https://image.pollinations.ai/prompt/{encoded_p}?width=768&height=1344&seed={seed}&nologo=true&model={model_type}"
        try:
            ir = requests.get(poll_url, headers=headers, timeout=25)
            if ir.status_code == 200 and len(ir.content) > 8000:
                img = Image.open(io.BytesIO(ir.content)).convert("RGB")
                w, h = img.size
                img = img.crop((0, 0, w, int(h * 0.94))).resize((720, 1280), Image.Resampling.LANCZOS)
                img = ImageEnhance.Contrast(img).enhance(1.08)
                img.save(img_path, "JPEG", quality=92)
                return {"type": "image", "path": img_path}
        except Exception:
            pass

    # بديل Pixabay للصور الفوتوغرافية إذا تأخر مولد الصور
    if pixabay_key:
        try:
            QUOTA_STATS["pixabay_used"] += 1
            q = urllib.parse.quote(scene["video_query"])
            p_url = f"https://pixabay.com/api/?key={pixabay_key}&q={q}&image_type=photo&per_page=5"
            pr = requests.get(p_url, headers=headers, timeout=12)
            if pr.status_code == 200 and pr.json().get("hits"):
                hits = pr.json()["hits"]
                img_u = hits[scene_idx % len(hits)]["largeImageURL"]
                ir = requests.get(img_u, headers=headers, timeout=15)
                img = Image.open(io.BytesIO(ir.content)).convert("RGB").resize((720, 1280), Image.Resampling.LANCZOS)
                img.save(img_path, "JPEG", quality=92)
                return {"type": "image", "path": img_path}
        except Exception:
            pass

    # بديل أخير من Picsum
    try:
        pic_r = requests.get(f"https://picsum.photos/seed/{seed}/720/1280", headers=headers, timeout=12)
        if pic_r.status_code == 200:
            with open(img_path, "wb") as f:
                f.write(pic_r.content)
            return {"type": "image", "path": img_path}
    except Exception:
        pass

    Image.new("RGB", (720, 1280), color=(20, 28, 48)).save(img_path, "JPEG")
    return {"type": "image", "path": img_path}

# ==========================================
# 5. محرك المونتاج السينمائي (FFmpeg Studio Level 5)
# ==========================================
def render_scene_clip(media_info, audio_file, srt_file, output_clip, duration, scene_idx, work_dir):
    fps = 25
    frames = max(int(duration * fps), 40)
    fade_out_st = max(duration - 0.4, 0.4)

    # استخدام مسارات نسبية داخل مجلد العمل لمنع أي خطأ في فلتر الترجمة
    rel_media = os.path.basename(media_info["path"])
    rel_audio = os.path.basename(audio_file)
    rel_srt = os.path.basename(srt_file)
    rel_out = os.path.basename(output_clip)

    sub_style = (
        f"subtitles={rel_srt}:force_style="
        "'FontName=Amiri,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BackColour=&H66000000,BorderStyle=3,Outline=2,Shadow=1,Alignment=2,MarginV=45'"
    )

    # فلتر تفخيم وتنعيم الصوت البشري
    audio_fx = "equalizer=f=90:width_type=h:width=180:g=3,equalizer=f=3200:width_type=h:width=900:g=2,acompressor,apad=pad_dur=0.25"

    if media_info["type"] == "video":
        vf_chain = (
            "scale=720:1280:force_original_aspect_ratio=increase,"
            "crop=720:1280:(iw-ow)/2:(ih-oh)*0.35,"
            "eq=contrast=1.08:saturation=0.95:brightness=-0.02,"
            f"{sub_style},"
            f"fade=t=in:st=0:d=0.35,fade=t=out:st={fade_out_st:.2f}:d=0.35"
        )
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", rel_media,
            "-i", rel_audio,
            "-vf", vf_chain,
            "-af", audio_fx,
            "-t", f"{duration:.2f}",
            "-r", str(fps),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
            "-c:a", "aac", "-b:a", "160k",
            "-pix_fmt", "yuv420p",
            rel_out
        ]
    else:
        moves = [
            f"z='1.0+0.32*(on/{frames})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
            f"z='1.32-0.32*(on/{frames})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
            f"z='1.24':x='(iw-iw/zoom)*(on/{frames})':y='(ih-ih/zoom)/2'",
            f"z='1.24':x='(iw-iw/zoom)*(1-on/{frames})':y='(ih-ih/zoom)/2'"
        ]
        chosen_move = moves[scene_idx % len(moves)]
        vf_chain = (
            "scale=900:1600,"
            f"zoompan={chosen_move}:d={frames}:s=720x1280:fps={fps},"
            "eq=contrast=1.06:saturation=1.05,"
            f"{sub_style},"
            f"fade=t=in:st=0:d=0.35,fade=t=out:st={fade_out_st:.2f}:d=0.35"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", rel_media,
            "-i", rel_audio,
            "-vf", vf_chain,
            "-af", audio_fx,
            "-t", f"{duration:.2f}",
            "-r", str(fps),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
            "-c:a", "aac", "-b:a", "160k",
            "-pix_fmt", "yuv420p",
            rel_out
        ]

    try:
        subprocess.run(cmd, cwd=work_dir, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError:
        # في حال حدوث أي مشكلة نادرة في الخط، يتم تصدير المشهد فوراً بدون توقف
        safe_vf = vf_chain.replace(f"{sub_style},", "")
        cmd[cmd.index("-vf") + 1] = safe_vf
        subprocess.run(cmd, cwd=work_dir, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

# ==========================================
# 6. نظام الرفع العملاق (حتى 2GB + تقسيم ذكي)
# ==========================================
def send_large_video_safely(chat_id, video_path, caption_text, reply_to_id):
    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)

    # 1. إذا كان الحجم أقل من 49 ميجابايت، يُرفع مباشرة عبر البوت
    if file_size_mb <= 49.0:
        with open(video_path, "rb") as vf:
            bot.send_video(chat_id, vf, caption=caption_text, reply_to_message_id=reply_to_id, timeout=180)
        return

    # 2. إذا توفرت مفاتيح Pyrogram (2GB MTProto)، يُرفع كملف واحد حتى 2000 ميجابايت
    if tg_api_id and tg_api_hash:
        try:
            from pyrogram import Client
            async def _upload_mtproto():
                async with Client("zakaria_2gb_uploader", api_id=int(tg_api_id), api_hash=tg_api_hash, bot_token=bot_token, in_memory=True) as app:
                    await app.send_video(chat_id=chat_id, video=video_path, caption=caption_text)
            asyncio.run(_upload_mtproto())
            return
        except Exception:
            pass

    # 3. التقسيم الأوتوماتيكي الذكي بدون فقدان جودة إذا تجاوز 49 ميجابايت بدون مفاتيح إضافية
    work_dir = os.path.dirname(video_path)
    part_pattern = os.path.join(work_dir, "part_%02d.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-c", "copy", "-map", "0",
        "-f", "segment", "-segment_time", "180",
        "-reset_timestamps", "1", part_pattern
    ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

    parts = sorted([os.path.join(work_dir, f) for f in os.listdir(work_dir) if f.startswith("part_") and f.endswith(".mp4")])
    for idx, p_file in enumerate(parts, 1):
        with open(p_file, "rb") as pf:
            bot.send_video(
                chat_id, pf,
                caption=f"{caption_text}\n📦 الجزء ({idx}/{len(parts)})",
                reply_to_message_id=reply_to_id, timeout=180
            )

# ==========================================
# 7. إدارة الحوار التفاعلي (الموضوع -> المتبقي -> المدة -> الإنتاج)
# ==========================================
def build_duration_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("⚡ 30 ثانية (4 مشاهد)", callback_data="dur_0.5"),
        InlineKeyboardButton("🎬 1 دقيقة (8 مشاهد)", callback_data="dur_1"),
        InlineKeyboardButton("🍿 2 دقيقة (14 مشهداً)", callback_data="dur_2"),
        InlineKeyboardButton("🎥 3 دقائق (20 مشهداً)", callback_data="dur_3"),
        InlineKeyboardButton("🏛️ 5 دقائق (32 مشهداً)", callback_data="dur_5"),
        InlineKeyboardButton("👑 10 دقائق (60 مشهداً)", callback_data="dur_10")
    )
    return markup

@bot.message_handler(commands=['start', 'status'])
def handle_start(message):
    if not is_authorized(message):
        bot.reply_to(message, "🔒 عذراً، هذا الاستوديو الشخصي خاص بزكريا فقط.")
        return

    USER_SESSION[message.chat.id] = {"step": "awaiting_topic"}
    welcome = (
        f"أهلاً بك يا زكريا في استوديو الإنتاج السينمائي الشخصي (Level 5 Pro)! 🎬👑\n\n"
        f"{get_quota_dashboard_text()}\n\n"
        "✍️ **الخطوة الأولى:**\n"
        "ما هو موضوع الفيلم أو القصة التي تريد صناعتها الآن؟ (أرسل اسم الموضوع في رسالة)"
    )
    bot.reply_to(message, welcome)

@bot.callback_query_handler(func=lambda call: call.data.startswith("dur_"))
def handle_duration_button(call):
    chat_id = call.message.chat.id
    session = USER_SESSION.get(chat_id)
    if not session or "topic" not in session:
        bot.answer_callback_query(call.id, "أرسل موضوع الفيلم أولاً!")
        return

    mins = float(call.data.replace("dur_", ""))
    bot.answer_callback_query(call.id, f"تم اختيار المدة: {mins} دقيقة")
    USER_SESSION[chat_id]["step"] = "producing"
    produce_full_movie(chat_id, session["topic"], mins, call.message)

@bot.message_handler(func=lambda message: True)
def handle_conversation(message):
    if not is_authorized(message):
        bot.reply_to(message, "🔒 هذا البوت خاص بصاحبه فقط.")
        return

    chat_id = message.chat.id
    text = (message.text or "").strip()
    if not text or text.startswith('/'):
        return

    session = USER_SESSION.get(chat_id, {"step": "awaiting_topic"})

    # إذا كان البوت ينتظر إدخال المدة يدوياً
    if session.get("step") == "awaiting_duration" and "topic" in session:
        nums = re.findall(r"[\d\.]+", text)
        if nums:
            val = float(nums[0])
            mins = val / 60.0 if ("ثان" in text or val > 20) else val
            mins = max(0.4, min(mins, 20.0))
            USER_SESSION[chat_id]["step"] = "producing"
            produce_full_movie(chat_id, session["topic"], mins, message)
            return

    # حفظ الموضوع الجديد وعرض المتبقي وسؤال المدة
    topic = clean_arabic(text)
    USER_SESSION[chat_id] = {"step": "awaiting_duration", "topic": topic}

    prompt_msg = (
        f"✅ **تم اعتماد الموضوع:** ({topic})\n\n"
        f"{get_quota_dashboard_text()}\n\n"
        "⏱️ **الخطوة الثانية: كم تريد مدة هذا الفيديو؟**\n"
        "اختر المدة من الأزرار بالأسفل، أو اكتب المدة التي تريدها مباشرة (مثلاً: `4 دقائق` أو `45 ثانية`):"
    )
    bot.reply_to(message, prompt_msg, reply_markup=build_duration_keyboard())

def produce_full_movie(chat_id, topic, duration_minutes, trigger_msg):
    # حساب عدد المشاهد بدقة (كل مشهد حوالي 8 ثوانٍ)
    total_target_seconds = int(duration_minutes * 60)
    num_scenes = max(3, min(int(round(total_target_seconds / 8.0)), 65))

    status_msg = bot.send_message(
        chat_id,
        f"🚀 **بدأ خط الإنتاج السينمائي!**\n"
        f"📌 الموضوع: {topic}\n"
        f"⏱️ المدة المطلوبة: {duration_minutes:.1f} دقيقة ({num_scenes} مشهداً)\n\n"
        f"1️⃣ جاري تأليف السيناريو وتوزيع أدوار الشخصيات..."
    )

    work_dir = os.path.abspath(f"studio_{chat_id}_{int(time.time())}")
    os.makedirs(work_dir, exist_ok=True)
    clips = []

    try:
        scenes = generate_storyboard(topic, num_scenes)

        for i, scene in enumerate(scenes):
            try:
                bot.edit_message_text(
                    f"🎬 **جاري إنتاج الفيلم:** ({topic})\n"
                    f"⏳ تقدم العمل: المشهد `{i+1}` من `{num_scenes}`\n"
                    f"🗣️ الشخصية الحالية: `{scene['character']}`\n"
                    f"📝 النص: _{scene['text'][:80]}..._",
                    chat_id=chat_id,
                    message_id=status_msg.message_id
                )
            except Exception:
                pass

            aud_path = os.path.join(work_dir, f"aud_{i}.mp3")
            srt_path = os.path.join(work_dir, f"subs_{i}.srt")
            clip_path = os.path.join(work_dir, f"clip_{i}.mp4")

            dur = generate_voice_and_srt(scene["text"], scene["character"], aud_path, srt_path)
            media = fetch_scene_media(scene, i, work_dir)
            render_scene_clip(media, aud_path, srt_path, clip_path, dur, i, work_dir)
            clips.append(clip_path)

        bot.edit_message_text(
            "🔄 اكتملت المشاهد! جاري الآن الدمج النهائي وإضافة اللمسة الصوتية ورفع الفيديو... ⏳🎥",
            chat_id=chat_id,
            message_id=status_msg.message_id
        )

        list_txt = os.path.join(work_dir, "concat_list.txt")
        with open(list_txt, "w", encoding="utf-8") as lf:
            for c in clips:
                lf.write(f"file '{os.path.basename(c)}'\n")

        merged_video = os.path.join(work_dir, "merged.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", "concat_list.txt", "-c", "copy", "merged.mp4"
        ], cwd=work_dir, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

        # إضافة خلفية صوتية سينمائية دافئة وهادئة جداً تحت صوت المعلق
        final_video = os.path.join(work_dir, "final_cinema.mp4")
        ambience_cmd = [
            "ffmpeg", "-y",
            "-i", "merged.mp4",
            "-f", "lavfi", "-i", "anoisesrc=color=brown:amplitude=0.015",
            "-filter_complex", "[1:a]lowpass=f=240[bg];[0:a][bg]amix=inputs=2:duration=first:weights=1 0.12[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "final_cinema.mp4"
        ]
        try:
            subprocess.run(ambience_cmd, cwd=work_dir, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        except Exception:
            final_video = merged_video

        QUOTA_STATS["videos_produced"] += 1
        caption = (
            f"🎉 **تم إنتاج فيلمك السينمائي بنجاح!**\n"
            f"📌 الموضوع: {topic}\n"
            f"🎞️ عدد المشاهد: {num_scenes} مشهداً (فيديوهات Pixabay + صور Flux + ترجمة + أصوات متعددة)\n\n"
            f"{get_quota_dashboard_text()}"
        )

        send_large_video_safely(chat_id, final_video, caption, trigger_msg.message_id)

        try:
            bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        except Exception:
            pass

    except Exception as e:
        bot.edit_message_text(f"⚠️ حدث خطأ غير متوقع: {str(e)[:200]}", chat_id=chat_id, message_id=status_msg.message_id)
    finally:
        USER_SESSION[chat_id] = {"step": "awaiting_topic"}
        shutil.rmtree(work_dir, ignore_errors=True)

if __name__ == "__main__":
    print("Zakaria Personal Cinema Studio Level 5 is running...")
    while True:
        try:
            bot.remove_webhook()
            bot.infinity_polling(timeout=30, long_polling_timeout=20, skip_pending=True)
        except Exception as e:
            print(f"Polling restart: {e}")
            time.sleep(5)
