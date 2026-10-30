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

# 1. التثبيت الذاتي للمكتبات لضمان عدم توقف السيرفر أبداً
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
from PIL import Image, ImageEnhance, ImageDraw

# ==========================================
# 1. المفاتيح السرية وحماية الاستوديو الشخصي
# ==========================================
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
gemini_key = os.environ.get('GEMINI_API_KEY', '').strip()
pixabay_key = os.environ.get('PIXABAY_API_KEY', '').strip()
tg_api_id = os.environ.get('TELEGRAM_API_ID', '').strip()
tg_api_hash = os.environ.get('TELEGRAM_API_HASH', '').strip()

bot = telebot.TeleBot(bot_token)

OWNER_CHAT_ID = None
USER_SESSION = {}

SERVER_START_TIME = time.time()
SERVER_MAX_SECONDS = 6 * 3600  # 6 ساعات لكل جلسة مجانية على GitHub

QUOTA_STATS = {
    "gemini_daily_limit": 1500,
    "gemini_used": 0,
    "pixabay_hourly_limit": 5000,
    "pixabay_used": 0,
    "videos_produced": 0
}

# توزيع أصوات البشر الطبيعية (Gemini Native Audio + Edge Neural)
GEMINI_VOICE_MAP = {
    "الراوي": "Charon",    # صوت وثائقي رجالي عميق وهادئ
    "البطل": "Fenrir",     # صوت شاب قوي وحماسي
    "شخصية": "Puck",       # صوت شخص ثاني مميز
    "الفتاة": "Kore"       # صوت نسائي طبيعي
}

EDGE_VOICE_MAP = {
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

def get_quota_dashboard():
    elapsed = time.time() - SERVER_START_TIME
    rem_sec = max(0, SERVER_MAX_SECONDS - elapsed)
    rem_h = int(rem_sec // 3600)
    rem_m = int((rem_sec % 3600) // 60)

    gem_rem = max(0, QUOTA_STATS["gemini_daily_limit"] - QUOTA_STATS["gemini_used"])
    pix_rem = max(0, QUOTA_STATS["pixabay_hourly_limit"] - QUOTA_STATS["pixabay_used"])
    pix_state = "✅ متصل ومفعل" if pixabay_key else "⚠️ غير مضاف (يعمل بـ Flux + ويكيبيديا)"
    max_mins = max(1, min(int(rem_sec // 25), 30))

    return (
        "📊 **لوحة تحكم وموارد الاستوديو (Level 6 Ultra):**\n"
        f"⏱️ وقت السيرفر المتبقي: `{rem_h} ساعة و {rem_m} دقيقة`\n"
        f"🧠 رصيد الذكاء الاصطناعي (Gemini): `{gem_rem}` طلب متبقٍ\n"
        f"🎬 رصيد فيديوهات Pixabay: `{pix_rem}` طلب ({pix_state})\n"
        f"🎙️ محرك الصوت: `بشري متعدد الشخصيات + مؤثرات انتقال Whoosh`\n"
        f"📦 سعة الإرسال: `مفعلة حتى 2GB (ضغط ذكي + تقسيم آلي)`\n"
        f"🎥 الفيديوهات المنتجة اليوم: `{QUOTA_STATS['videos_produced']}`\n"
        f"⚡ أقصى مدة فيديو متاحة الآن: `حتى {max_mins} دقيقة`"
    )

# ==========================================
# 2. المعالجة اللغوية وكتابة السيناريو السينمائي
# ==========================================
def clean_arabic(text):
    fixes = {
        "مدينه": "مدينة", "قلعه": "قلعة", "قريه": "قرية",
        "دوله": "دولة", "حضاره": "حضارة", "قصه": "قصة",
        "جزيره": "جزيرة", "عاصمه": "عاصمة", "تاريخيه": "تاريخية"
    }
    return " ".join([fixes.get(w, w) for w in text.split()])

def call_gemini_text(prompt_text):
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
                    time.sleep(2.5)
            except Exception:
                pass
    return None

def generate_storyboard(topic, num_scenes):
    clean_t = clean_arabic(topic)
    prompt = (
        f"أنت مخرج سينمائي وكاتب قصص ووثائقيات بأسلوب نانو بنانا والجزيرة الوثائقية. "
        f"اكتب سيناريو مترابطاً ومشوقاً جداً مكوناً من ({num_scenes}) مشهداً عن: ({clean_t}).\n"
        "وزّع الأدوار بذكاء بين الشخصيات التالية: (الراوي، البطل، شخصية، الفتاة) بحيث يبدو كقصة حية متكاملة.\n"
        "يجب كتابة كل مشهد في سطر واحد فقط مفصول بعلامة | بهذا التنسيق الدقيق دون أي مقدمات:\n"
        "الشخصية|النص العربي للمشهد (جملتان قويتين وسليمتين لغوياً)|two_word_english_video_keyword|Detailed English visual prompt describing the exact historical or story scene\n"
        "تنبيه صارم: في حقل الكلمات الإنجليزية، اكتب كلمات تصف بيئة الموضوع بدقة (مثل ancient fortress أو mountain village أو desert warrior) ولا تكتب كلمات عشوائية."
    )
    raw = call_gemini_text(prompt)
    scenes = []

    if raw:
        for line in raw.splitlines():
            line = re.sub(r'[\*\#\`\"]', '', line).strip()
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 4:
                char_name = parts[0] if parts[0] in GEMINI_VOICE_MAP else "الراوي"
                narration = clean_arabic(parts[1])
                v_query = re.sub(r'[^a-zA-Z0-9 ]', '', parts[2]).strip() or "ancient history"
                img_prompt = parts[3]
                if len(narration) > 10:
                    scenes.append({
                        "character": char_name,
                        "text": narration,
                        "video_query": v_query,
                        "image_prompt": f"{img_prompt}, photorealistic cinematic documentary shot, dramatic lighting, 8k, vertical 9:16"
                    })

    # مشاهد احتياطية مترابطة عند الحاجة
    backups = [
        ("الراوي", f"تبدأ فصول هذه القصة الاستثنائية مع {clean_t}، حيث تتعانق هيبة المكان مع أسرار التاريخ العريق.", "ancient mountain", f"Epic aerial cinematic documentary view of {clean_t}, ancient architecture and dramatic mountains, 8k"),
        ("البطل", f"هنا في {clean_t}، خُطّت ملاحم الصمود والإبداع التي صنعت حضارة لا تعرف المستحيل.", "historic castle", f"Dramatic close-up cinematic shot inside {clean_t}, golden sunlight beams, ancient stone walls, 8k"),
        ("شخصية", f"كل حجر وكل زاوية في {clean_t} تروي للزائرين حكاية مجدٍ تليد تناقلته الأجيال بفخر واعتزاز.", "old heritage", f"Traditional heritage street and authentic historic details of {clean_t}, national geographic style, 8k"),
        ("الراوي", f"لتبقى {clean_t} منارة خالدة وشاهداً حياً يبهر العقول ويحفظ ذاكرة التاريخ إلى الأبد.", "sunset mountains", f"Breathtaking golden hour sunset panoramic view over {clean_t}, cinematic masterpiece, 8k")
    ]

    while len(scenes) < num_scenes:
        tpl = backups[len(scenes) % len(backups)]
        scenes.append({
            "character": tpl[0],
            "text": tpl[1],
            "video_query": tpl[2],
            "image_prompt": tpl[3]
        })

    return scenes[:num_scenes]

# ==========================================
# 3. محرك الصوت البشري (Gemini Native + Edge Neural + Whoosh SFX)
# ==========================================
def format_srt_time(seconds):
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def try_gemini_human_voice(text, character, output_mp3):
    voice_name = GEMINI_VOICE_MAP.get(character, "Charon")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={gemini_key}"
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice_name}
                }
            }
        }
    }
    try:
        QUOTA_STATS["gemini_used"] += 1
        res = requests.post(url, json=payload, timeout=25)
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
                    "-c:a", "libmp3lame", "-b:a", "192k", output_mp3
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                os.remove(wav_tmp)
                return os.path.exists(output_mp3) and os.path.getsize(output_mp3) > 1500
    except Exception:
        pass
    return False

async def _edge_voice_with_timings(text, voice, output_mp3):
    comm = edge_tts.Communicate(text, voice, rate="+0%", pitch="+0Hz")
    events = []
    with open(output_mp3, "wb") as af:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                af.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                st = chunk["offset"] / 10_000_000.0
                dt = chunk["duration"] / 10_000_000.0
                events.append((st, st + dt, chunk["text"]))
    return events

def generate_scene_audio_and_srt(text, character, audio_path, srt_path):
    word_events = []
    # 1. محاولة توليد الصوت البشري الفخم من Gemini (نفس صوت فيديو تعز المتصل)
    used_gemini = try_gemini_human_voice(text, character, audio_path)

    # 2. إذا كان السيرفر مضغوطاً، نستخدم محرك Edge العصبي مع التوقيت الدقيق للكلمات
    if not used_gemini:
        e_voice = EDGE_VOICE_MAP.get(character, "ar-SA-HamedNeural")
        try:
            word_events = asyncio.run(_edge_voice_with_timings(text, e_voice, audio_path))
        except Exception:
            pass

    if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 1000:
        gTTS(text=text, lang='ar').save(audio_path)

    # قياس مدة الصوت بدقة
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", audio_path
        ]).decode().strip()
        duration = max(float(out), 2.8)
    except Exception:
        duration = 4.5

    # بناء ملف الترجمة المحروقة (SRT)
    entries = []
    if len(word_events) >= 2:
        step_words = 5
        for i in range(0, len(word_events), step_words):
            grp = word_events[i:i + step_words]
            st = grp[0][0]
            et = max(grp[-1][1], st + 0.6)
            entries.append((st, et, " ".join([w[2] for w in grp])))
    else:
        words = text.split()
        step_words = 5
        chunks = [" ".join(words[i:i + step_words]) for i in range(0, len(words), step_words)] or [text]
        seg_t = duration / len(chunks)
        for idx, ch in enumerate(chunks):
            entries.append((idx * seg_t, (idx + 1) * seg_t, ch))

    with open(srt_path, "w", encoding="utf-8") as sf:
        for idx, (st, et, phrase) in enumerate(entries, 1):
            sf.write(f"{idx}\n{format_srt_time(st)} --> {format_srt_time(et)}\n{phrase}\n\n")

    return duration

# ==========================================
# 4. الجلب البصري الذكي (بدون صور عشوائية نهائياً)
# ==========================================
BANNED_RANDOM_WORDS = {"laptop", "computer", "macbook", "office", "bicycle", "bike", "car", "phone", "desk"}

def fetch_wikimedia_real_photos(topic):
    urls = []
    headers = {"User-Agent": "ZakariaCinemaStudio/6.0"}
    for lang in ["ar", "en"]:
        try:
            api = f"https://{lang}.wikipedia.org/w/api.php"
            params = {
                "action": "query", "generator": "search", "gsrsearch": topic,
                "gsrlimit": 12, "prop": "pageimages", "piprop": "original", "format": "json"
            }
            r = requests.get(api, params=params, headers=headers, timeout=10)
            pages = r.json().get("query", {}).get("pages", {})
            for p in pages.values():
                src = p.get("original", {}).get("source", "")
                if src and src.lower().endswith((".jpg", ".jpeg", ".png")):
                    urls.append(src)
        except Exception:
            pass
    return urls

def format_and_save_image(raw_bytes, out_path):
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    w, h = img.size
    # قص أي علامة مائية سفلية وضبط الأبعاد السينمائية
    img = img.crop((0, 0, w, int(h * 0.94))).resize((900, 1600), Image.Resampling.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.08)
    img = ImageEnhance.Color(img).enhance(1.12)
    img.save(out_path, "JPEG", quality=95)

def fetch_scene_visual(scene, scene_idx, topic, wiki_pool, work_dir):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"}

    # 1. الطبقة الأولى: فيديوهات Pixabay الحقيقية المفلترة (تُدمج بالتناوب مع صور القصة المخصصة)
    if pixabay_key and (scene_idx % 2 == 1):
        q = urllib.parse.quote(scene["video_query"])
        v_url = f"https://pixabay.com/api/videos/?key={pixabay_key}&q={q}&per_page=8&safesearch=true"
        try:
            QUOTA_STATS["pixabay_used"] += 1
            r = requests.get(v_url, headers=headers, timeout=12)
            if r.status_code == 200:
                hits = r.json().get("hits", [])
                valid_hits = []
                for h in hits:
                    tags = set(h.get("tags", "").lower().replace(",", " ").split())
                    if not (tags & BANNED_RANDOM_WORDS):
                        valid_hits.append(h)
                if valid_hits:
                    chosen = valid_hits[scene_idx % len(valid_hits)]
                    v_dict = chosen.get("videos", {})
                    v_link = v_dict.get("medium", {}).get("url") or v_dict.get("small", {}).get("url")
                    if v_link:
                        vid_path = os.path.join(work_dir, f"visual_{scene_idx}.mp4")
                        vr = requests.get(v_link, headers=headers, timeout=20)
                        if vr.status_code == 200 and len(vr.content) > 25000:
                            with open(vid_path, "wb") as vf:
                                vf.write(vr.content)
                            return {"type": "video", "path": vid_path}
        except Exception:
            pass

    img_path = os.path.join(work_dir, f"visual_{scene_idx}.jpg")

    # 2. الطبقة الثانية: توليد صورة مخصصة للمشهد عبر Pollinations (Flux / Flux-Realism / Turbo)
    encoded_p = urllib.parse.quote(scene["image_prompt"])
    for attempt, model_name in enumerate(["flux", "turbo"]):
        seed = random.randint(10000, 999999) + (scene_idx * 999) + attempt
        p_url = f"https://image.pollinations.ai/prompt/{encoded_p}?width=768&height=1344&seed={seed}&nologo=true&model={model_name}"
        try:
            ir = requests.get(p_url, headers=headers, timeout=25)
            if ir.status_code == 200 and len(ir.content) > 8000:
                format_and_save_image(ir.content, img_path)
                time.sleep(1.0)
                return {"type": "image", "path": img_path}
        except Exception:
            time.sleep(1.5)

    # 3. الطبقة الثالثة: صور حقيقية وتاريخية لنفس الموضوع من ويكيبيديا (Wikimedia Commons)
    while wiki_pool:
        w_url = wiki_pool.pop(0)
        try:
            wr = requests.get(w_url, headers=headers, timeout=15)
            if wr.status_code == 200 and len(wr.content) > 8000:
                format_and_save_image(wr.content, img_path)
                return {"type": "image", "path": img_path}
        except Exception:
            pass

    # 4. الطبقة الرابعة: صور Pixabay الفوتوغرافية المطابقة لوصف المشهد
    if pixabay_key:
        try:
            QUOTA_STATS["pixabay_used"] += 1
            q = urllib.parse.quote(scene["video_query"])
            p_api = f"https://pixabay.com/api/?key={pixabay_key}&q={q}&image_type=photo&per_page=6&safesearch=true"
            pr = requests.get(p_api, headers=headers, timeout=12)
            if pr.status_code == 200 and pr.json().get("hits"):
                hits = pr.json()["hits"]
                img_u = hits[scene_idx % len(hits)]["largeImageURL"]
                ir = requests.get(img_u, headers=headers, timeout=15)
                if ir.status_code == 200 and len(ir.content) > 8000:
                    format_and_save_image(ir.content, img_path)
                    return {"type": "image", "path": img_path}
        except Exception:
            pass

    # لوحة سينمائية مرسومة عند الطوارئ القصوى (بدون أي صور لابتوب أو دراجات عشوائية أبداً)
    canvas = Image.new("RGB", (900, 1600), color=(14, 20, 36))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([45, 45, 855, 1555], outline=(212, 175, 55), width=5)
    canvas.save(img_path, "JPEG", quality=92)
    return {"type": "image", "path": img_path}

# ==========================================
# 5. محرك المونتاج الخارق (خدعة نانو بنانا Speed-Ramp + Whoosh SFX)
# ==========================================
def render_level6_scene(media_info, audio_file, srt_file, output_clip, duration, scene_idx, work_dir):
    fps = 25
    F = max(int(duration * fps), 45)
    fade_out_st = max(duration - 0.35, 0.4)
    whoosh_delay_ms = int(max(duration - 0.42, 0.2) * 1000)

    rel_media = os.path.basename(media_info["path"])
    rel_audio = os.path.basename(audio_file)
    rel_srt = os.path.basename(srt_file)
    rel_out = os.path.basename(output_clip)

    sub_style = (
        f"subtitles={rel_srt}:force_style="
        "'FontName=Amiri,FontSize=21,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BackColour=&H66000000,BorderStyle=3,Outline=2,Shadow=1,Alignment=2,MarginV=48'"
    )

    # دمج الصوت البشري العميق + مؤثر هواء الانتقال السريع (Whoosh SFX) في آخر جزء من الثانية
    audio_filter_complex = (
        f"[1:a]equalizer=f=90:width_type=h:width=180:g=3,"
        f"equalizer=f=3200:width_type=h:width=900:g=2,acompressor,apad=pad_dur=0.25[voice];"
        f"anoisesrc=color=pink:duration=0.38:amplitude=0.09,"
        f"bandpass=f=550:width_type=h:w=450,"
        f"afade=t=in:st=0:d=0.12,afade=t=out:st=0.18:d=0.20,"
        f"adelay={whoosh_delay_ms}|{whoosh_delay_ms}[whoosh];"
        f"[voice][whoosh]amix=inputs=2:duration=first:weights=1 0.35[aout]"
    )

    if media_info["type"] == "video":
        vf_chain = (
            "scale=720:1280:force_original_aspect_ratio=increase,"
            "crop=720:1280:(iw-ow)/2:(ih-oh)*0.35,"
            "eq=contrast=1.08:saturation=1.05:brightness=-0.01,"
            f"{sub_style},"
            f"fade=t=in:st=0:d=0.28,fade=t=out:st={fade_out_st:.2f}:d=0.32"
        )
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", rel_media,
            "-i", rel_audio,
            "-filter_complex", audio_filter_complex,
            "-vf", vf_chain,
            "-map", "0:v", "-map", "[aout]",
            "-t", f"{duration:.2f}",
            "-r", str(fps),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "160k",
            "-pix_fmt", "yuv420p",
            rel_out
        ]
    else:
        # خدعة نانو بنانا الرياضية: حركة بطيئة وناعمة طوال المشهد ثم قفزة سريعة خاطفة (t^5) في النهاية بدون فواصل منقوطة
        t_Ratio = f"(on/{F})"
        fast_tail = f"({t_Ratio}*{t_Ratio}*{t_Ratio}*{t_Ratio}*{t_Ratio})"

        nano_moves = [
            # 1. زوم بطيء ثم اندفاع خاطف للأمام في آخر نصف ثانية
            f"z='1.0+0.14*{t_Ratio}+0.34*{fast_tail}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
            # 2. زوم عكسي هادئ ثم سحب سريع للخلف
            f"z='1.48-0.14*{t_Ratio}-0.34*{fast_tail}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
            # 3. مسح أفقي بطيء لليمين ثم انزلاق خاطف (Whip-Pan Right)
            f"z='1.28+0.12*{fast_tail}':x='(iw-iw/zoom)*(0.25*{t_Ratio}+0.75*{fast_tail})':y='(ih-ih/zoom)/2'",
            # 4. مسح أفقي بطيء لليسار ثم انزلاق خاطف (Whip-Pan Left)
            f"z='1.28+0.12*{fast_tail}':x='(iw-iw/zoom)*(1.0-0.25*{t_Ratio}-0.75*{fast_tail})':y='(ih-ih/zoom)/2'"
        ]
        chosen_move = nano_moves[scene_idx % len(nano_moves)]

        vf_chain = (
            "scale=900:1600,"
            f"zoompan={chosen_move}:d={F}:s=720x1280:fps={fps},"
            "eq=contrast=1.08:saturation=1.08,"
            f"{sub_style},"
            f"fade=t=in:st=0:d=0.25,fade=t=out:st={fade_out_st:.2f}:d=0.30"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", rel_media,
            "-i", rel_audio,
            "-filter_complex", audio_filter_complex,
            "-vf", vf_chain,
            "-map", "0:v", "-map", "[aout]",
            "-t", f"{duration:.2f}",
            "-r", str(fps),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "160k",
            "-pix_fmt", "yuv420p",
            rel_out
        ]

    try:
        subprocess.run(cmd, cwd=work_dir, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError:
        # خطة أمان فورية إذا تعذر تحميل الخط في أي مشهد
        safe_vf = vf_chain.replace(f"{sub_style},", "")
        cmd[cmd.index("-vf") + 1] = safe_vf
        subprocess.run(cmd, cwd=work_dir, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

# ==========================================
# 6. الرفع الآمن حتى 2 جيجابايت
# ==========================================
def upload_final_movie(chat_id, video_path, caption_text, reply_to_id):
    size_mb = os.path.getsize(video_path) / (1024 * 1024)

    if size_mb <= 49.0:
        with open(video_path, "rb") as vf:
            bot.send_video(chat_id, vf, caption=caption_text, reply_to_message_id=reply_to_id, timeout=180)
        return

    if tg_api_id and tg_api_hash:
        try:
            from pyrogram import Client
            async def _send_2gb():
                async with Client("zakaria_2gb", api_id=int(tg_api_id), api_hash=tg_api_hash, bot_token=bot_token, in_memory=True) as app:
                    await app.send_video(chat_id=chat_id, video=video_path, caption=caption_text)
            asyncio.run(_send_2gb())
            return
        except Exception:
            pass

    work_dir = os.path.dirname(video_path)
    part_tpl = os.path.join(work_dir, "part_%02d.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-c", "copy", "-map", "0",
        "-f", "segment", "-segment_time", "180",
        "-reset_timestamps", "1", part_tpl
    ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

    parts = sorted([os.path.join(work_dir, f) for f in os.listdir(work_dir) if f.startswith("part_") and f.endswith(".mp4")])
    for idx, p_file in enumerate(parts, 1):
        with open(p_file, "rb") as pf:
            bot.send_video(chat_id, pf, caption=f"{caption_text}\n📦 الجزء ({idx}/{len(parts)})", reply_to_message_id=reply_to_id, timeout=180)

# ==========================================
# 7. الحوار الشخصي التفاعلي وإدارة الإنتاج
# ==========================================
def get_duration_buttons():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("⚡ 30 ثانية (4 مشاهد)", callback_data="dur_0.5"),
        InlineKeyboardButton("🎬 1 دقيقة (8 مشاهد)", callback_data="dur_1"),
        InlineKeyboardButton("🍿 2 دقيقة (15 مشهداً)", callback_data="dur_2"),
        InlineKeyboardButton("🎥 3 دقائق (22 مشهداً)", callback_data="dur_3"),
        InlineKeyboardButton("🏛️ 5 دقائق (35 مشهداً)", callback_data="dur_5"),
        InlineKeyboardButton("👑 10 دقائق (65 مشهداً)", callback_data="dur_10")
    )
    return markup

@bot.message_handler(commands=['start', 'status'])
def handle_welcome(message):
    if not is_authorized(message):
        bot.reply_to(message, "🔒 هذا الاستوديو الشخصي خاص بزكريا فقط.")
        return

    USER_SESSION[message.chat.id] = {"step": "awaiting_topic"}
    msg = (
        "أهلاً بك يا زكريا في **الاستوديو السينمائي الخارق (Level 6 Ultra)**! 🎬👑\n\n"
        f"{get_quota_dashboard()}\n\n"
        "✍️ **الخطوة الأولى:**\n"
        "ما هو موضوع الفيلم الوثائقي أو القصة التي تريد صناعتها الآن؟"
    )
    bot.reply_to(message, msg)

@bot.callback_query_handler(func=lambda call: call.data.startswith("dur_"))
def on_duration_selected(call):
    chat_id = call.message.chat.id
    session = USER_SESSION.get(chat_id)
    if not session or "topic" not in session:
        bot.answer_callback_query(call.id, "أرسل موضوع الفيلم أولاً!")
        return

    mins = float(call.data.replace("dur_", ""))
    bot.answer_callback_query(call.id, f"تم اعتماد المدة: {mins} دقيقة")
    USER_SESSION[chat_id]["step"] = "producing"
    run_level6_production(chat_id, session["topic"], mins, call.message)

@bot.message_handler(func=lambda message: True)
def handle_user_inputs(message):
    if not is_authorized(message):
        bot.reply_to(message, "🔒 هذا البوت خاص بصاحبه فقط.")
        return

    chat_id = message.chat.id
    text = (message.text or "").strip()
    if not text or text.startswith('/'):
        return

    session = USER_SESSION.get(chat_id, {"step": "awaiting_topic"})

    if session.get("step") == "awaiting_duration" and "topic" in session:
        nums = re.findall(r"[\d\.]+", text)
        if nums:
            val = float(nums[0])
            mins = val / 60.0 if ("ثان" in text or val > 20) else val
            mins = max(0.4, min(mins, 20.0))
            USER_SESSION[chat_id]["step"] = "producing"
            run_level6_production(chat_id, session["topic"], mins, message)
            return

    topic = clean_arabic(text)
    USER_SESSION[chat_id] = {"step": "awaiting_duration", "topic": topic}

    reply = (
        f"✅ **تم اعتماد الموضوع:** ({topic})\n\n"
        f"{get_quota_dashboard()}\n\n"
        "⏱️ **الخطوة الثانية: كم تريد مدة الفيديو؟**\n"
        "اختر من الأزرار بالأسفل أو اكتب المدة التي تريدها في رسالة (مثلاً: `3 دقائق` أو `45 ثانية`):"
    )
    bot.reply_to(message, reply, reply_markup=get_duration_buttons())

def run_level6_production(chat_id, topic, duration_minutes, trigger_msg):
    target_sec = int(duration_minutes * 60)
    num_scenes = max(4, min(int(round(target_sec / 7.5)), 65))

    status_msg = bot.send_message(
        chat_id,
        f"🚀 **انطلق خط إنتاج المستوى السادس (Level 6 Ultra)!**\n"
        f"📌 الموضوع: {topic}\n"
        f"⏱️ المدة المحددة: {duration_minutes:.1f} دقيقة ({num_scenes} مشهداً متلاحقاً)\n\n"
        f"1️⃣ جاري كتابة القصة وتوزيع أدوار الشخصيات..."
    )

    work_dir = os.path.abspath(f"ultra_{chat_id}_{int(time.time())}")
    os.makedirs(work_dir, exist_ok=True)
    clips = []

    try:
        scenes = generate_storyboard(topic, num_scenes)
        wiki_pool = fetch_wikimedia_real_photos(topic)

        for i, scene in enumerate(scenes):
            try:
                bot.edit_message_text(
                    f"🎬 **إنتاج المستوى السادس:** ({topic})\n"
                    f"⏳ المشهد الجاري: `{i+1}` من `{num_scenes}`\n"
                    f"🎙️ المتحدث: `{scene['character']}`\n"
                    f"📝 النص: _{scene['text'][:85]}..._",
                    chat_id=chat_id,
                    message_id=status_msg.message_id
                )
            except Exception:
                pass

            aud_path = os.path.join(work_dir, f"aud_{i}.mp3")
            srt_path = os.path.join(work_dir, f"subs_{i}.srt")
            clip_path = os.path.join(work_dir, f"clip_{i}.mp4")

            dur = generate_scene_audio_and_srt(scene["text"], scene["character"], aud_path, srt_path)
            visual = fetch_scene_visual(scene, i, topic, wiki_pool, work_dir)
            render_level6_scene(visual, aud_path, srt_path, clip_path, dur, i, work_dir)
            clips.append(clip_path)

        bot.edit_message_text(
            "🔄 اكتملت المشاهد! جاري الآن دمج الموسيقى التصويرية المحيطية وتصدير النسخة النهائية... ⏳🎥",
            chat_id=chat_id,
            message_id=status_msg.message_id
        )

        list_file = os.path.join(work_dir, "concat_list.txt")
        with open(list_file, "w", encoding="utf-8") as lf:
            for c in clips:
                lf.write(f"file '{os.path.basename(c)}'\n")

        merged_mp4 = os.path.join(work_dir, "merged.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", "concat_list.txt", "-c", "copy", "merged.mp4"
        ], cwd=work_dir, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

        # توليد موسيقى تصويرية سينمائية هادئة (Ambient Drone Pad) تنخفض تحت الكلام
        final_mp4 = os.path.join(work_dir, "final_level6.mp4")
        score_cmd = [
            "ffmpeg", "-y",
            "-i", "merged.mp4",
            "-f", "lavfi", "-i", "aevalsrc='0.025*sin(2*PI*110*t)+0.018*sin(2*PI*164.8*t)+0.012*sin(2*PI*220*t)':s=44100",
            "-filter_complex", "[1:a]lowpass=f=320[music];[0:a][music]amix=inputs=2:duration=first:weights=1 0.18[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "final_level6.mp4"
        ]
        try:
            subprocess.run(score_cmd, cwd=work_dir, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        except Exception:
            final_mp4 = merged_mp4

        QUOTA_STATS["videos_produced"] += 1
        caption = (
            f"👑 **تم إنتاج الفيلم بنظام (Level 6 Ultra) بنجاح!**\n"
            f"📌 الموضوع: {topic}\n"
            f"🎞️ المشاهد: {num_scenes} مشهداً (حركة نانو بنانا + صوت بشري متعدد + ترجمة + فيديوهات وصور مطابقة)\n\n"
            f"{get_quota_dashboard()}"
        )

        upload_final_movie(chat_id, final_mp4, caption, trigger_msg.message_id)

        try:
            bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        except Exception:
            pass

    except Exception as e:
        bot.edit_message_text(f"⚠️ حدث خطأ أثناء المعالجة: {str(e)[:200]}", chat_id=chat_id, message_id=status_msg.message_id)
    finally:
        USER_SESSION[chat_id] = {"step": "awaiting_topic"}
        shutil.rmtree(work_dir, ignore_errors=True)

if __name__ == "__main__":
    print("Zakaria Level 6 Ultra Cinema Studio is active...")
    while True:
        try:
            bot.remove_webhook()
            bot.infinity_polling(timeout=30, long_polling_timeout=20, skip_pending=True)
        except Exception as e:
            print(f"Polling restart: {e}")
            time.sleep(5)
