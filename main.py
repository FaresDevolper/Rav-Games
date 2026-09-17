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

# رابط مباشر لخط عربي يدعم الرسم في PIL بدون مشاكل
FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/amiri/Amiri-Bold.ttf"
CACHED_FONT_BYTES = None

def get_arabic_font(size):
    global CACHED_FONT_BYTES
    try:
        if CACHED_FONT_BYTES is None:
            res = requests.get(FONT_URL, timeout=10)
            if res.status_code == 200:
                CACHED_FONT_BYTES = res.content
        if CACHED_FONT_BYTES:
            return ImageFont.truetype(io.BytesIO(CACHED_FONT_BYTES), size)
    except Exception as e:
        print(f"Font download error: {e}")
    
    # محاولة استخدام الخط المحلي في نظام التشغيل إن وجد
    try:
        return ImageFont.truetype("arial.ttf", size)
    except IOError:
        return ImageFont.load_default()

# متغير لمعرفة الألعاب النشطة بكل قناة
active_games = {}  # {channel_id: {"game": "حيوان", "answers": [...]}}

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

# --- 3. معالجة النصوص ورسم البانر ---
def process_arabic_text(text):
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)

def generate_game_image(game_name, prompt_text):
    # إنشاء خلفية سوداء بالكامل (800x400)
    img_w, img_h = 800, 400
    img = Image.new("RGB", (img_w, img_h), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    # أحجام الخطوط
    font_main = get_arabic_font(48)
    font_header = get_arabic_font(30)

    # درجات لون البيج المطلوب
    main_banner_color = (212, 196, 151)   # بيج فاتح للمستطيل في المنتصف
    header_box_color = (150, 134, 93)     # بيج غامق للمربع أعلى اليمين
    text_color = (20, 20, 20)             # لون داكن جداً للنص ليظهر بوضوح فوق البيج

    # 1. رسم المستطيل الرئيسي في المنتصف (للمطلوب)
    main_rect = [180, 150, 620, 260]
    draw.rounded_rectangle(main_rect, radius=20, fill=main_banner_color)

    # 2. رسم مربع اسم اللعبة أعلى اليمين
    header_rect = [520, 100, 630, 160]
    draw.rounded_rectangle(header_rect, radius=15, fill=header_box_color)

    # تجهيز النص العربي
    arabic_game_name = process_arabic_text(game_name)
    arabic_prompt = process_arabic_text(prompt_text)

    # 3. كتابة اسم اللعبة داخل المربع الأيمن العلوي
    draw.text((575, 130), arabic_game_name, fill=(255, 255, 255), font=font_header, anchor="mm")

    # 4. كتابة المطلوب في المنتصف
    draw.text((400, 205), arabic_prompt, fill=text_color, font=font_main, anchor="mm")

    # حفظ الصورة في الذاكرة
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
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

    # --- أمر قائمة الألعاب ---
    if text in ["ألعاب", "العاب", "-ألعاب", "-العاب"]:
        games_list = "🎮 ** قائمة الألعاب المتوفرة :**\n"
        for g in GAMES_DATA.keys():
            games_list += f"• `{g}`\n"
        games_list += "\nلتشغيل أي لعبة ، اكتب اسم اللعبة مباشرة في الروم (مثال: `حيوان` أو `جماد`) .\nلإيقاف أي لعبة جارية، اكتب `إيقاف`."
        await message.channel.send(games_list)
        return

    # --- أمر إيقاف اللعبة ---
    if text in ["إيقاف", "ايقاف", "وقف"]:
        if channel_id in active_games:
            del active_games[channel_id]
            await message.channel.send(" تم إيقاف اللعبة الحالية بنجاح.")
        else:
            await message.channel.send(" لا توجد لعبة شغالّة حالياً في هذه الروم.")
        return

    # --- التحقق من الأجوبة ---
    if channel_id in active_games:
        game_info = active_games[channel_id]
        if text in game_info["answers"]:
            del active_games[channel_id]
            await message.channel.send(f"• {message.author.mention} ☝🏻 أجاب الإجابة الصحيحة")
            return

    # --- بدء الألعاب ---
    clean_command = text.lstrip("-")
    if clean_command in GAMES_DATA:
        if channel_id in active_games:
            await message.channel.send(" هناك لعبة جارية بالفعل في هذه الروم أكملها أو اكتب **إيقاف** لإنهائها .")
            return

        item = random.choice(GAMES_DATA[clean_command])
        prompt_text = item["prompt"]
        valid_answers = item["answers"]

        active_games[channel_id] = {
            "game": clean_command,
            "answers": valid_answers
        }

        async with message.channel.typing():
            loop = asyncio.get_event_loop()
            img_bytes = await loop.run_in_executor(None, generate_game_image, clean_command, prompt_text)
            file = discord.File(fp=img_bytes, filename="game.png")
            await message.channel.send(file=file)

    await bot.process_commands(message)

# --- 5. التشغيل ---
keep_alive()
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
