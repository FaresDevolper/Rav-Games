import asyncio
import io
import os
import random
import threading
import json
import discord
from discord.ext import commands
from flask import Flask
import requests
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper

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

# --- 2. إدارة ملف النقاط (points.json) ---
POINTS_FILE = "points.json"

def load_points():
    if os.path.exists(POINTS_FILE):
        try:
            with open(POINTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading points file: {e}")
            return {}
    return {}

def save_points(points_data):
    try:
        with open(POINTS_FILE, "w", encoding="utf-8") as f:
            json.dump(points_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving points file: {e}")

user_points = load_points()

def add_user_points(user_id, points_to_add):
    uid = str(user_id)
    user_points[uid] = user_points.get(uid, 0) + points_to_add
    save_points(user_points)
    return user_points[uid]

def get_user_points(user_id):
    return user_points.get(str(user_id), 0)

# --- 3. إعدادات البوت والـ Intents ---
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="-", intents=intents)

FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/amiri/Amiri-Bold.ttf"
CACHED_FONT_BYTES = None

# رابط صورتك الخاصة لخلفية قائمة التوب
BACKGROUND_IMAGE_URL = "https://cdn.discordapp.com/attachments/1339684080224174141/1550204035762622606/IMG_9161.jpg?ex=6aad7b83&is=6aac2a03&hm=77cbcc8bd991e297cced7c2c21d9696c5d090f882b20b98e4d8e620ecc25bce3"

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
    
    try:
        return ImageFont.truetype("arial.ttf", size)
    except IOError:
        return ImageFont.load_default()

active_games = {} # {channel_id: {"game": "...", "answers": [...], "task": Task}}

# --- 4. قاعدة البيانات الضخمة للألعاب ---
GAMES_DATA = {
    "حيوان": [
        {"prompt": "بحرف أ", "answers": ["أسد", "أرنب", "أفعى", "أبو بريص", "أربد"]},
        {"prompt": "بحرف ب", "answers": ["بطة", "بقرة", "باندا", "بومة", "بطريق"]},
        {"prompt": "بحرف ت", "answers": ["تمساح", "تنين", "تونة", "تيس"]},
        {"prompt": "بحرف ث", "answers": ["ثعلب", "ثور", "ثعبان"]},
        {"prompt": "بحرف ج", "answers": ["جمل", "جاموس", "جرو"]},
        {"prompt": "بحرف ح", "answers": ["حصان", "حمار", "حوت", "حشرة", "حجل"]},
        {"prompt": "بحرف خ", "answers": ["خروف", "خفاش", "خنزير"]},
        {"prompt": "بحرف د", "answers": ["دب", "دلفين", "دجاجة", "ديدان", "دبور"]},
        {"prompt": "بحرف ذ", "answers": ["ذئب", "ذباب", "ذيبة"]},
        {"prompt": "بحرف ر", "answers": ["رنة", "راكون", "روبيان"]},
        {"prompt": "بحرف ز", "answers": ["زرافة", "زنبور"]},
        {"prompt": "بحرف س", "answers": ["سمكة", "سنجاب", "سلحفاة", "سردين", "سرطان"]},
        {"prompt": "بحرف ش", "answers": ["شادي", "شبل", "شوان"]},
        {"prompt": "بحرف ص", "answers": ["صقر", "صرصور", "صنور"]},
        {"prompt": "بحرف ض", "answers": ["ضبع", "ضفدع"]},
        {"prompt": "بحرف ط", "answers": ["طاووس", "طائر", "طنان"]},
        {"prompt": "بحرف ظ", "answers": ["ظبي"]},
        {"prompt": "بحرف ع", "answers": ["عصفور", "العنكبوت", "عقاب", "عجل", "عقرب"]},
        {"prompt": "بحرف غ", "answers": ["غزال", "غراب", "غوريلا"]},
        {"prompt": "بحرف ف", "answers": ["فهد", "فيل", "فأر", "فلامنجو", "فراشة"]},
        {"prompt": "بحرف ق", "answers": ["قرد", "قطة", "قنفذ", "قرش", "قاطور"]},
        {"prompt": "بحرف ك", "answers": ["كلب", "كانغرو", "كوالا"]},
        {"prompt": "بحرف ل", "answers": ["لاما", "لقلق", "ليمور"]},
        {"prompt": "بحرف م", "answers": ["ماعز", "مهار", "مدرع"]},
        {"prompt": "بحرف ن", "answers": ["نمر", "نسر", "نحلة", "نملة", "نورس"]},
        {"prompt": "بحرف هـ", "answers": ["هدهد", "هامستر"]},
        {"prompt": "بحرف و", "answers": ["واوي", "وحش القرن", "ورل"]},
        {"prompt": "بحرف ي", "answers": ["يمامة", "يعسوب"]}
    ],
    "جماد": [
        {"prompt": "بحرف أ", "answers": ["أبريق", "أريكة", "أنبوب", "أبواب"]},
        {"prompt": "بحرف ب", "answers": ["باب", "برميل", "بلاط", "بطارية", "بساط"]},
        {"prompt": "بحرف ت", "answers": ["تلفاز", "تلفون", "تاج", "تمثال"]},
        {"prompt": "بحرف ث", "answers": ["ثلاجة", "ثوب", "ثريا"]},
        {"prompt": "بحرف ج", "answers": ["جدار", "جرس", "جزمة", "جسر"]},
        {"prompt": "بحرف ح", "answers": ["حبل", "حقيبة", "حائط", "حجر", "حاسوب"]},
        {"prompt": "بحرف خ", "answers": ["خزانة", "خاتم", "خيمة", "خاطوف"]},
        {"prompt": "بحرف د", "answers": ["دفتر", "دولاب", "دباب", "دبوس"]},
        {"prompt": "بحرف ذ", "answers": ["ذاكرة", "ذهب"]},
        {"prompt": "بحرف ر", "answers": ["رف", "رخام", "راديو", "رسالة"]},
        {"prompt": "بحرف ز", "answers": ["زجاج", "زر", "زولية", "زهري"]},
        {"prompt": "بحرف س", "answers": ["ساعة", "سرير", "سيارة", "سلسلة", "سطل"]},
        {"prompt": "بحرف ش", "answers": ["شباك", "شاحن", "شاشة", "شوكة", "شارع"]},
        {"prompt": "بحرف ص", "answers": ["صحن", "صندوق", "صنارة", "صخرة"]},
        {"prompt": "بحرف ض", "answers": ["ضباب", "ضمادة"]},
        {"prompt": "بحرف ط", "answers": ["طاولة", "طائرة", "طربوش", "طوب", "طبق"]},
        {"prompt": "بحرف ظ", "answers": ["ظرف"]},
        {"prompt": "بحرف ع", "answers": ["علم", "عجلة", "عطر", "عكاز"]},
        {"prompt": "بحرف غ", "answers": ["غسالة", "غلاف", "غبار"]},
        {"prompt": "بحرف ف", "answers": ["فانوس", "فرن", "فراش", "فنجان", "فأس"]},
        {"prompt": "بحرف ق", "answers": ["قلم", "قفل", "قميص", "قارب", "قبعة"]},
        {"prompt": "بحرف ك", "answers": ["كرسي", "كتاب", "كأس", "كمبيوتر", "كرة"]},
        {"prompt": "بحرف ل", "answers": ["لمبة", "لوحة", "لبس"]},
        {"prompt": "بحرف م", "answers": ["طاولة", "مفتاح", "مرآة", "مقص", "مكتب", "ملعقة"]},
        {"prompt": "بحرف ن", "answers": ["نافذة", "نظارة", "نفق", "نجم"]},
        {"prompt": "بحرف هـ", "answers": ["هاتف", "هدية", "هيكل"]},
        {"prompt": "بحرف و", "answers": ["ورقة", "وسادة", "وعاء"]},
        {"prompt": "بحرف ي", "answers": ["ياخت", "ياقة"]}
    ],
    "بلاد": [
        {"prompt": "بحرف أ", "answers": ["أمريكا", "ألمانيا", "أرجنتين", "أستراليا", "أذربيجان", "ألبانيا"]},
        {"prompt": "بحرف ب", "answers": ["البحرين", "برازيل", "بلجيكا", "بولندا", "بلغاريا", "بنغلاديش"]},
        {"prompt": "بحرف ت", "answers": ["تونس", "تركيا", "تايلاند", "تشيك"]},
        {"prompt": "بحرف ج", "answers": ["الجزائر", "جيبوتي", "جورجيا", "جامايكا"]},
        {"prompt": "بحرف ح", "answers": ["حائل"]},
        {"prompt": "بحرف خ", "answers": ["خرطوم"]},
        {"prompt": "بحرف د", "answers": ["الدنمارك", "دبي", "الدوحة"]},
        {"prompt": "بحرف ر", "answers": ["روسيا", "رومانيا", "رواندا"]},
        {"prompt": "بحرف ز", "answers": ["زيمبابوي", "زامبيا"]},
        {"prompt": "بحرف س", "answers": ["السعودية", "سوريا", "السودان", "سويسرا", "السويد", "سنغافورة"]},
        {"prompt": "بحرف ش", "answers": ["شيلي", "شيشان"]},
        {"prompt": "بحرف ص", "answers": ["الصين", "الصومال", "صربيا"]},
        {"prompt": "بحرف ع", "answers": ["عمان", "العراق"]},
        {"prompt": "بحرف غ", "answers": ["غانا", "غينيا"]},
        {"prompt": "بحرف ف", "answers": ["فرنسا", "فلسطين", "فنلندا", "فيتنام", "الفلبين"]},
        {"prompt": "بحرف ق", "answers": ["قطر", "قبرص"]},
        {"prompt": "بحرف ك", "answers": ["الكويت", "كندا", "كولومبيا", "كرواتيا", "كينيا"]},
        {"prompt": "بحرف ل", "answers": ["لبنان", "ليبيا", "لندن"]},
        {"prompt": "بحرف م", "answers": ["مصر", "المغرب", "ماليزيا", "المكسيك", "ميتشغان"]},
        {"prompt": "بحرف ن", "answers": ["النيجر", "نيجيريا", "النرويج", "نيوزيلندا", "نمسا"]},
        {"prompt": "بحرف هـ", "answers": ["الهند", "هولندا", "هنغاريا"]},
        {"prompt": "بحرف و", "answers": ["واشنطن", "ويلز"]},
        {"prompt": "بحرف ي", "answers": ["اليمن", "اليابان", "اليونان"]}
    ],
    "اسم": [
        {"prompt": "بحرف أ", "answers": ["أحمد", "أميرة", "أيمن", "أنس", "أروى", "إبراهيم"]},
        {"prompt": "بحرف ب", "answers": ["بدر", "باسم", "بسمة", "بندر", "بشرى"]},
        {"prompt": "بحرف ت", "answers": ["تركي", "تيم", "تالا", "تهاني"]},
        {"prompt": "بحرف ث", "answers": ["ثامر", "ثريا", "ثابت"]},
        {"prompt": "بحرف ج", "answers": ["جاسم", "جمال", "جنى", "جواهر", "جهاد"]},
        {"prompt": "بحرف ح", "answers": ["حسن", "حسين", "حنين", "حصة", "حامد"]},
        {"prompt": "بحرف خ", "answers": ["خالد", "خديجة", "خلود", "خليل"]},
        {"prompt": "بحرف د", "answers": ["دانا", "داوود", "دلال", "ديمة"]},
        {"prompt": "بحرف ر", "answers": ["راشد", "ريم", "رائد", "رانيا", "رحمة"]},
        {"prompt": "بحرف ز", "answers": ["زياد", "زينب", "زهراء", "زيد"]},
        {"prompt": "بحرف س", "answers": ["سعد", "سارة", "سلطان", "سلمان", "سحر", "سامي"]},
        {"prompt": "بحرف ش", "answers": ["شهد", "شوق", "شريف", "شهم"]},
        {"prompt": "بحرف ص", "answers": ["صالح", "صفاء", "صباح", "صديق"]},
        {"prompt": "بحرف ط", "answers": ["طارق", "طلال", "طيبة"]},
        {"prompt": "بحرف ع", "answers": ["علي", "عمر", "عائشة", "عبدالله", "عبير", "عثمان"]},
        {"prompt": "بحرف غ", "answers": ["غادة", "غسان", "غزل"]},
        {"prompt": "بحرف ف", "answers": ["فارس", "فاطمة", "فيصل", "فهد", "فريدة"]},
        {"prompt": "بحرف ق", "answers": ["قاسم", "قصي", "قمر"]},
        {"prompt": "بحرف ك", "answers": ["خالد", "كارم", "كريمة", "كوثر"]},
        {"prompt": "بحرف ل", "answers": ["لطيفة", "لمى", "ليان", "لقمان"]},
        {"prompt": "بحرف م", "answers": ["محمد", "مريم", "محمود", "ملاك", "ماجد", "منيرة"]},
        {"prompt": "بحرف ن", "answers": ["نورة", "ناصر", "نجود", "نايف", "ندى"]},
        {"prompt": "بحرف هـ", "answers": ["هند", "هشام", "هدى", "هاني", "هيا"]},
        {"prompt": "بحرف و", "answers": ["وليد", "وفاء", "وسام", "وداد"]},
        {"prompt": "بحرف ي", "answers": ["يوسف", "يافا", "يزيد", "ياسمين", "يحيى"]}
    ],
    "مفرد": [
        {"prompt": "رياح", "answers": ["ريح"]},
        {"prompt": "بيوت", "answers": ["بيت"]},
        {"prompt": "شجر", "answers": ["شجرة"]},
        {"prompt": "كتب", "answers": ["كتاب"]},
        {"prompt": "أقلام", "answers": ["قلم"]},
        {"prompt": "رجال", "answers": ["رجل"]},
        {"prompt": "نساء", "answers": ["امرأة"]},
        {"prompt": "سيارات", "answers": ["سيارة"]},
        {"prompt": "أيام", "answers": ["يوم"]},
        {"prompt": "نجوم", "answers": ["نجم"]},
        {"prompt": "بحار", "answers": ["بحر"]},
        {"prompt": "جبال", "answers": ["جبل"]},
        {"prompt": "أنهار", "answers": ["نهر"]},
        {"prompt": "مدن", "answers": ["مدينة"]},
        {"prompt": "دول", "answers": ["دولة"]},
        {"prompt": "أطفال", "answers": ["طفل"]},
        {"prompt": "أبواب", "answers": ["باب"]},
        {"prompt": "مفاتيح", "answers": ["مفتاح"]},
        {"prompt": "قلوب", "answers": ["قلب"]},
        {"prompt": "عيون", "answers": ["عين"]},
        {"prompt": "أيدي", "answers": ["يد"]},
        {"prompt": "ساعات", "answers": ["ساعة"]},
        {"prompt": "أسماء", "answers": ["اسم"]},
        {"prompt": "أحلام", "answers": ["حلم"]},
        {"prompt": "قصص", "answers": ["قصة"]},
        {"prompt": "صور", "answers": ["صورة"]},
        {"prompt": "أواني", "answers": ["إناء"]},
        {"prompt": "سحب", "answers": ["سحابة"]},
        {"prompt": "أمطار", "answers": ["مطر"]},
        {"prompt": "أوراق", "answers": ["ورقة"]},
        {"prompt": "أشجار", "answers": ["شجرة"]},
        {"prompt": "أفكار", "answers": ["فكرة"]},
        {"prompt": "علوم", "answers": ["علم"]},
        {"prompt": "أعمال", "answers": ["عمل"]},
        {"prompt": "ألعاب", "answers": ["لعبة"]}
    ],
    "اسرع": [
        {"prompt": "حاسوب", "answers": ["حاسوب"]},
        {"prompt": "برمجة", "answers": ["برمجة"]},
        {"prompt": "سيرفر", "answers": ["سيرفر"]},
        {"prompt": "تطوير", "answers": ["تطوير"]},
        {"prompt": "سعودية", "answers": ["سعودية"]},
        {"prompt": "الرياض", "answers": ["الرياض"]},
        {"prompt": "دسكورد", "answers": ["دسكورد"]},
        {"prompt": "لاعبين", "answers": ["لاعبين"]},
        {"prompt": "سرعة", "answers": ["سرعة"]},
        {"prompt": "تحدي", "answers": ["تحدي"]},
        {"prompt": "بطولة", "answers": ["بطولة"]},
        {"prompt": "مكافأة", "answers": ["مكافأة"]},
        {"prompt": "انتصار", "answers": ["انتصار"]},
        {"prompt": "مستقبل", "answers": ["مستقبل"]},
        {"prompt": "تقنية", "answers": ["تقنية"]},
        {"prompt": "شاشة", "answers": ["شاشة"]},
        {"prompt": "لوحة", "answers": ["لوحة"]},
        {"prompt": "سماعة", "answers": ["سماعة"]},
        {"prompt": "ماوس", "answers": ["ماوس"]},
        {"prompt": "كيبل", "answers": ["كيبل"]},
        {"prompt": "إنترنت", "answers": ["إنترنت"]},
        {"prompt": "معالج", "answers": ["معالج"]},
        {"prompt": "كرت", "answers": ["كرت"]},
        {"prompt": "ذاكرة", "answers": ["ذاكرة"]},
        {"prompt": "تخزين", "answers": ["تخزين"]},
        {"prompt": "صوت", "answers": ["صوت"]},
        {"prompt": "صورة", "answers": ["صورة"]},
        {"prompt": "مقطع", "answers": ["مقطع"]},
        {"prompt": "روم", "answers": ["روم"]},
        {"prompt": "أدمن", "answers": ["أدمن"]},
        {"prompt": "شات", "answers": ["شات"]},
        {"prompt": "مجتمع", "answers": ["مجتمع"]},
        {"prompt": "فعالية", "answers": ["فعالية"]},
        {"prompt": "حماس", "answers": ["حماس"]},
        {"prompt": "نصر", "answers": ["نصر"]}
    ]
}

# --- 5. معالجة النصوص ورسم صور الألعاب والتوب ---
def process_arabic_text(text):
    return arabic_reshaper.reshape(text)

def generate_game_image(game_name, prompt_text):
    img_w, img_h = 800, 400
    img = Image.new("RGB", (img_w, img_h), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_main = get_arabic_font(48)
    font_header = get_arabic_font(30)

    main_banner_color = (212, 196, 151)
    header_box_color = (150, 134, 93)
    text_color = (20, 20, 20)

    main_rect = [180, 150, 620, 260]
    draw.rounded_rectangle(main_rect, radius=20, fill=main_banner_color)

    header_rect = [520, 100, 630, 160]
    draw.rounded_rectangle(header_rect, radius=15, fill=header_box_color)

    arabic_game_name = process_arabic_text(game_name)
    arabic_prompt = process_arabic_text(prompt_text)

    draw.text((575, 130), arabic_game_name, fill=(255, 255, 255), font=font_header, anchor="mm")
    draw.text((400, 205), arabic_prompt, fill=text_color, font=font_main, anchor="mm")

    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr

def generate_top_image(top_users_data):
    try:
        res = requests.get(BACKGROUND_IMAGE_URL, timeout=10)
        img = Image.open(io.BytesIO(res.content)).convert("RGBA")
    except Exception as e:
        print(f"Error loading top background image: {e}")
        img = Image.new("RGBA", (800, 600), (20, 20, 30, 255))

    img = img.resize((800, 600))
    
    # خلفية شفافة لسهولة قراءة الأسماء
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    draw_overlay.rectangle([70, 80, 730, 530], fill=(0, 0, 0, 160))
    img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)
    font_title = get_arabic_font(40)
    font_list = get_arabic_font(26)

    title_text = process_arabic_text("🏆 قائمة المتصدرين")
    draw.text((400, 110), title_text, fill=(255, 215, 0), font=font_title, anchor="mm")

    start_y = 170
    for idx, (name, pts) in enumerate(top_users_data, start=1):
        display_str = f"#{idx}  |  {pts} نقطة  -  {name}"
        arabic_str = process_arabic_text(display_str)
        
        color = (255, 215, 0) if idx == 1 else (220, 220, 220) if idx == 2 else (205, 127, 50) if idx == 3 else (255, 255, 255)
        draw.text((400, start_y), arabic_str, fill=color, font=font_list, anchor="mm")
        start_y += 35

    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr

# --- 6. دالة مؤقت الـ 7 ثوانٍ ---
async def game_timer(channel, channel_id):
    await asyncio.sleep(7)
    if channel_id in active_games:
        del active_games[channel_id]
        await channel.send("⏱️ **انتهى الوقت!** لم يقم أحد بالإجابة الصحيحة.")

# --- 7. الأحداث والأوامر ---
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    channel_id = message.channel.id
    text = message.content.strip()

    # --- أمر عرض قائمة الألعاب ---
    if text in ["ألعاب", "العاب", "-ألعاب", "-العاب"]:
        games_list = "🎮 **قائمة الألعاب المتوفرة:**\n"
        for g in GAMES_DATA.keys():
            games_list += f"• `{g}`\n"
        games_list += "\nلتشغيل أي لعبة، اكتب اسم اللعبة مباشرة في الروم (مثال: `حيوان` أو `جماد`).\nلديك **7 ثوانٍ** فقط للإجابة.\nلمعرفة نقاطك اكتب `نقاطي`.\nلعرض التوب اكتب `top` أو `توب`.\nلإيقاف أي لعبة جارية، اكتب `إيقاف`."
        await message.channel.send(games_list)
        return

    # --- أمر نقاطي ---
    if text in ["نقاطي", "-نقاطي"]:
        pts = get_user_points(message.author.id)
        await message.channel.send(f"🏆 {message.author.mention} نقاطك هي: **{pts}** نقطة.")
        return

    # --- أمر التوب بالصورة الديناميكية ---
    if text.lower() in ["top", "توب", "توب نقاط", "توب النقاط", "-top", "-توب"]:
        if not user_points:
            await message.channel.send("⚠️ لا توجد أي نقاط مسجلة حتى الآن!")
            return

        sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)

        top_data = []
        for uid, pts in sorted_users[:10]:
            member = message.guild.get_member(int(uid))
            name = member.display_name if member else f"عضو ({uid[:4]})"
            top_data.append((name, pts))

        async with message.channel.typing():
            loop = asyncio.get_event_loop()
            img_bytes = await loop.run_in_executor(None, generate_top_image, top_data)
            file = discord.File(fp=img_bytes, filename="top.png")
            await message.channel.send(file=file)
        return

    # --- أمر روليت ---
    if text in ["روليت", "-روليت"]:
        await message.channel.send("قريباً.")
        return

    # --- أمر إيقاف اللعبة ---
    if text in ["إيقاف", "ايقاف", "-إيقاف"]:
        if channel_id in active_games:
            task = active_games[channel_id].get("task")
            if task and not task.done():
                task.cancel()
            del active_games[channel_id]
            await message.channel.send("🛑 تم إيقاف اللعبة الحالية.")
        else:
            await message.channel.send("⚠️ لا توجد لعبة شغالّة حالياً في هذه الروم.")
        return

    # --- التحقق من الأجوبة وإضافة النقاط ---
    if channel_id in active_games:
        game_info = active_games[channel_id]
        if text in game_info["answers"]:
            task = game_info.get("task")
            if task and not task.done():
                task.cancel()
            del active_games[channel_id]

            earned_points = random.randint(10, 30)
            total_pts = add_user_points(message.author.id, earned_points)

            await message.channel.send(
                f"• {message.author.mention} ☝🏻 إجابتك صحيحة!\n"
                f"⭐ حصلت على **{earned_points}** نقطة! (إجمالي نقاطك: **{total_pts}** نقطة)"
            )
            return

    # --- بدء الألعاب الكلاسيكية ---
    clean_command = text.lstrip("-")
    if clean_command in GAMES_DATA:
        if channel_id in active_games:
            await message.channel.send("⚠️ هناك لعبة جارية بالفعل في هذه الروم أكملها أو اكتب **إيقاف** لإنهائها.")
            return

        item = random.choice(GAMES_DATA[clean_command])
        prompt_text = item["prompt"]
        valid_answers = item["answers"]

        timer_task = asyncio.create_task(game_timer(message.channel, channel_id))

        active_games[channel_id] = {
            "game": clean_command,
            "answers": valid_answers,
            "task": timer_task
        }

        async with message.channel.typing():
            loop = asyncio.get_event_loop()
            img_bytes = await loop.run_in_executor(None, generate_game_image, clean_command, prompt_text)
            file = discord.File(fp=img_bytes, filename="game.png")
            await message.channel.send(file=file)

    await bot.process_commands(message)

# --- 8. التشغيل ---
keep_alive()
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
