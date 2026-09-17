import asyncio
import io
import os
import random
import threading
import discord
from discord.ext import commands
from flask import Flask
import requests
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

# --- 1. سيرفر Flask لضمان العمل المستمر ---
app = Flask('')

@app.route('/')
def home():
    return "Games Bot is Running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- 2. إعدادات البوت والـ Intents ---
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="-", intents=intents)

# رابط الصورة القالب
TEMPLATE_IMAGE_URL = "https://cdn.discordapp.com/attachments/1339684080224174141/1549947325726855228/IMG_9132.jpg?ex=6aac8c6f&is=6aab3aef&hm=bdcad42dbf991be28caf06f73ae1d32441d8855e10bc51c363c6d93b3f8d72fb&"

# متغیر لمعرفة الألعاب النشطة بكل قناة
active_games = {}  # {channel_id: {"game": "حيوان", "answer": "فهد", "task": task_obj}}

# قاعدة بيانات للألعاب والكلمات/الحروف
GAMES_DATA = {
    "حيوان": [
        {"prompt": "بحرف ف", "answers": ["فهد", "فيل", "فأر", "فلامنجو"]},
        {"prompt": "بحرف أ", "answers": ["أسد", "أرنب", "أفعى"]},
        {"prompt": "بحرف ق", "answers": ["قرد", "قطة", "قنفذ"]}
    ],
    "جماد": [
        {"prompt": "بحرف ص", "answers": ["صحن", "صندوق", "صنارة"]},
        {"prompt": "بحرف ك", "answers": ["كرسي", "كتاب", "كأس"]},
        {"prompt": "بحرف ط", "answers": ["طاولة", "طائرة", "طربوش"]}
    ],
    "بلاد": [
        {"prompt": "بحرف و", "answers": ["واشنطن", "ويلز"]},
        {"prompt": "بحرف س", "answers": ["سعودية", "سوريا", "سودان", "سويسرا"]},
        {"prompt": "بحرف م", "answers": ["مصر", "مغرب", "ماليزيا"]}
    ],
    "اسم": [
        {"prompt": "بحرف هـ", "answers": ["هدى", "هشام", "هند", "هاني"]},
        {"prompt": "بحرف م", "answers": ["مريم", "محمد", "محمود", "ملاك"]},
        {"prompt": "بحرف ف", "answers": ["فارس", "فاطمة", "فيصل"]}
    ],
    "مفرد": [
        {"prompt": "رياح", "answers": ["ريح"]},
        {"prompt": "بيوت", "answers": ["بيت"]},
        {"prompt": "شجر", "answers": ["شجرة"]},
        {"prompt": "كتب", "answers": ["كتاب"]}
    ],
    "اسرع": [
        {"prompt": "حاسوب", "answers": ["حاسوب"]},
        {"prompt": "برمجة", "answers": ["برمجة"]},
        {"prompt": "سيرفر", "answers": ["سيرفر"]}
    ]
}

# --- 3. دالة معالجة النصوص العربية وتشكيل الصورة ---
def process_arabic_text(text):
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)

def generate_game_image(game_name, prompt_text):
    # تحميل الصورة القالب
    response = requests.get(TEMPLATE_IMAGE_URL)
    img = Image.open(io.BytesIO(response.content)).convert("RGB")
    draw = ImageDraw.Draw(img)

    # اختيار خط افتراضي (أو تحميل خط عربي إذا توفر)
    try:
        font_main = ImageFont.truetype("arial.ttf", 45)
        font_header = ImageFont.truetype("arial.ttf", 30)
    except IOError:
        font_main = ImageFont.load_default()
        font_header = ImageFont.load_default()

    # تجهيز النصوص العربية
    arabic_game_name = process_arabic_text(game_name)
    arabic_prompt = process_arabic_text(prompt_text)

    # 1. كتابة اسم اللعبة في المربع الصغير (أعلى اليمين)
    # الإحداثيات تقريبية وتناسب مكان المربع الداكن في صورتك
    draw.text((820, 360), arabic_game_name, fill=(255, 255, 255), font=font_header, anchor="mm")

    # 2. كتابة المطلوب في المنتصف (المستطيل الفاتح)
    draw.text((500, 480), arabic_prompt, fill=(255, 255, 255), font=font_main, anchor="mm")

    # حفظ الصورة في الذاكرة لإرسالها للديسكورد
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_byte_arr.seek(0)
    return img_byte_arr

# --- 4. الأحداث والأوامر ---
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    channel_id = message.channel.id
    text = message.content.strip()

    # --- أمر إيقاف اللعبة ---
    if text in ["إيقاف", "ايقاف", "وقف"]:
        if channel_id in active_games:
            del active_games[channel_id]
            await message.channel.send(" تم إيقاف اللعبة الحالية بنجاح.")
        else:
            await message.channel.send(" لا توجد لعبة شغالّة حالياً في هذه الروم.")
        return

    # --- التحقق من الأجوبة أثناء اللعبة الشغالة ---
    if channel_id in active_games:
        game_info = active_games[channel_id]
        # إذا كانت الإجابة صحيحة
        if text in game_info["answers"]:
            del active_games[channel_id]
            await message.channel.send(f"• {message.author.mention} ☝🏻 أجاب الإجابة الصحيحة")
            return

    # --- بدء الألعاب (بدون بادئة أو مع البادئة -) ---
    clean_command = text.lstrip("-")
    if clean_command in GAMES_DATA:
        # إذا كانت هناك لعبة شغالة بالأصل
        if channel_id in active_games:
            await message.channel.send(" هناك لعبة جارية بالفعل في هذه الروم أكملها أو اكتب **إيقاف** لإنهائها.")
            return

        # اختيار سؤال عشوائي
        item = random.choice(GAMES_DATA[clean_command])
        prompt_text = item["prompt"]
        valid_answers = item["answers"]

        # حفظ بيانات اللعبة القائمة
        active_games[channel_id] = {
            "game": clean_command,
            "answers": valid_answers
        }

        # توليد وإرسال الصورة
        async with message.channel.typing():
            loop = asyncio.get_event_loop()
            img_bytes = await loop.run_in_executor(None, generate_game_image, clean_command, prompt_text)
            file = discord.File(fp=img_bytes, filename="game.jpg")
            await message.channel.send(file=file)

    await bot.process_commands(message)

# --- 5. التشغيل ---
keep_alive()
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
