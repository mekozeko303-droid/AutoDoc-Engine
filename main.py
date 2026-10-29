import os
import json
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

# 2. محرك الذكاء الاصطناعي (مع الاكتشاف التلقائي للموديلات)
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
        'gemini-2.0-flash',
        'gemini-2.0-flash-lite',
        'gemini-2.5-flash',
        'gemini-2.5-flash-lite',
        'gemini-flash-latest'
    ]
    models_to_try = [m for m in priority if m in available_models] + [m for m in available_models if m not in priority]
    if not models_to_try:
        models_to_try = priority

    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}]
    }

    for model_name in models_to_try[:6]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
        try:
            res = requests.post(url, json=payload, timeout=25)
            if res.status_code == 200:
                return res.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception:
            continue
    return None

# 3. توليد السيناريو الوثائقي بصيغة منظمة
def generate_script(topic):
    prompt = f"""
أنت كاتب أفلام وثائقية محترف. اكتب سيناريو فيديو وثائقي قصير ومشوق من 3 مشاهد حول الموضوع التالي: "{topic}".
يجب أن ترد بصيغة JSON فقط بدون أي كلام إضافي، بهذا الشكل الدقيق:
[
  {{
    "narration": "نص التعليق الصوتي للمشهد الأول باللغة العربية الفصحى المشوقة (جملتين)",
    "image_prompt": "Detailed cinematic documentary photography of [describe scene 1 in English], realistic, 8k, vertical"
  }},
  {{
    "narration": "نص التعليق الصوتي للمشهد الثاني باللغة العربية الفصحى (جملتين)",
    "image_prompt": "Detailed cinematic documentary photography of [describe scene 2 in English], realistic, 8k, vertical"
  }},
  {{
    "narration": "نص التعليق الصوتي للمشهد الثالث والخاتمة باللغة العربية الفصحى (جملتين)",
    "image_prompt": "Detailed cinematic documentary photography of [describe scene 3 in English], realistic, 8k, vertical"
  }}
]
"""
    raw = call_gemini(prompt)
    if not raw:
        return None
    try:
        clean = raw.strip()
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        start = clean.find('[')
        end = clean.rfind(']') + 1
        return json.loads(clean[start:end])
    except Exception:
        return None

# 4. توليد الصور بالذكاء الاصطناعي (مع بديل احتياطي مضاد للانهيار)
def create_scene_image(prompt_en, output_path):
    try:
        encoded = urllib.parse.quote(prompt_en)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=720&height=1280&nologo=true&seed={int(time.time())}"
        res = requests.get(url, timeout=25)
        if res.status_code == 200 and len(res.content) > 1000:
            with open(output_path, 'wb') as f:
                f.write(res.content)
            return
    except Exception:
        pass
    
    # صورة سينمائية احتياطية في حال بطء سيرفر الصور
    img = Image.new('RGB', (720, 1280), color=(18, 24, 38))
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 680, 1240], outline=(212, 175, 55), width=4)
    img.save(output_path)

# 5. أمر البداية /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "صديقي"
    
    # تسجيل المستخدم في الذاكرة Supabase
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
        f"أهلاً بك يا {first_name} في مصنع الوثائقيات الآلي! 🎬🚀\n\n"
        "✅ العقل (Gemini): متصل وجاهز\n"
        "✅ الذاكرة (Supabase): متصلة وجاهزة\n"
        "✅ محرك المونتاج (FFmpeg): جاهز للإنتاج\n\n"
        "💡 **لصناعة أول فيديو لك الآن:**\n"
        "فقط اكتب لي في رسالة عادية موضوع الفيديو الوثائقي الذي تريده (مثلاً: *تاريخ قلعة القاهرة في تعز* أو *أسرار الفضاء*) وسأقوم بكتابة السيناريو، توليد الصور، تسجيل الصوت، ومونتاج الفيديو وإرساله لك فوراً!"
    )
    bot.reply_to(message, welcome_msg)

# 6. استلام الموضوع وصناعة الفيديو الكامل
@bot.message_handler(func=lambda message: True)
def make_documentary(message):
    topic = message.text.strip()
    if topic.startswith('/'):
        return

    chat_id = message.chat.id
    status_msg = bot.reply_to(message, f"⏳ تم استلام الفكرة: ({topic})\n\n1️⃣ جاري كتابة السيناريو الوثائقي عبر الذكاء الاصطناعي...")

    scenes = generate_script(topic)
    if not scenes or not isinstance(scenes, list):
        bot.edit_message_text("⚠️ تعذر توليد السيناريو حالياً، يرجى إرسال الموضوع مرة أخرى.", chat_id=chat_id, message_id=status_msg.message_id)
        return

    # عرض السيناريو للمستخدم
    script_preview = "\n\n".join([f"🔹 **المشهد {i+1}:** {s.get('narration', '')}" for i, s in enumerate(scenes)])
    bot.edit_message_text(
        f"✅ **تم كتابة السيناريو بنجاح:**\n\n{script_preview}\n\n2️⃣ جاري الآن توليد الصور، تسجيل التعليق الصوتي، ومونتاج الفيديو... (انتظر دقيقة واحدة) 🎬⏳",
        chat_id=chat_id,
        message_id=status_msg.message_id
    )

    work_dir = f"video_{chat_id}_{int(time.time())}"
    os.makedirs(work_dir, exist_ok=True)
    segment_files = []

    try:
        for i, scene in enumerate(scenes):
            narration = scene.get('narration', 'مشهد وثائقي.')
            img_prompt = scene.get('image_prompt', f"Documentary scene about {topic}")

            audio_path = os.path.join(work_dir, f"audio_{i}.mp3")
            img_path = os.path.join(work_dir, f"img_{i}.jpg")
            seg_path = os.path.join(work_dir, f"seg_{i}.mp4")

            # توليد الصوت العربي
            tts = gTTS(text=narration, lang='ar')
            tts.save(audio_path)

            # توليد الصورة
            create_scene_image(img_prompt, img_path)

            # دمج المشهد بـ FFmpeg
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", img_path,
                "-i", audio_path,
                "-c:v", "libx264", "-tune", "stillimage",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
                "-shortest", seg_path
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            segment_files.append(seg_path)

        # تجميع كل المشاهد في فيديو واحد
        concat_file = os.path.join(work_dir, "list.txt")
        with open(concat_file, "w") as f:
            for seg in segment_files:
                f.write(f"file '{os.path.abspath(seg)}'\n")

        final_video = os.path.join(work_dir, "final_doc.mp4")
        concat_cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_file, "-c", "copy", final_video
        ]
        subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # إرسال الفيديو النهائي إلى تيليجرام
        with open(final_video, "rb") as video_file:
            bot.send_video(
                chat_id,
                video_file,
                caption=f"🎉 **تم إنتاج الفيلم الوثائقي بنجاح!**\n📌 الموضوع: {topic}\n\n📝 **النص الكامل:**\n{script_preview}",
                reply_to_message_id=message.message_id
            )

        bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"⚠️ حدث خطأ أثناء المونتاج: {e}", chat_id=chat_id, message_id=status_msg.message_id)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

if __name__ == "__main__":
    print("AutoDoc Full Factory is running...")
    bot.infinity_polling(skip_pending=True)
