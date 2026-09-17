import asyncio
import io
import os
import random
import threading
import json
import math
import discord
from discord.ext import commands
from discord.ui import View, Button
from flask import Flask
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps
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

# --- 2. إدارة ملف النقاط وإحصائيات الروليت ---
POINTS_FILE = "points.json"
ROULETTE_STATS_FILE = "roulette_stats.json"

def load_json(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return {}
    return {}

def save_json(filepath, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving {filepath}: {e}")

user_points = load_json(POINTS_FILE)
roulette_stats = load_json(ROULETTE_STATS_FILE)

def add_user_points(user_id, points_to_add):
    uid = str(user_id)
    user_points[uid] = user_points.get(uid, 0) + points_to_add
    save_json(POINTS_FILE, user_points)
    return user_points[uid]

def get_user_points(user_id):
    return user_points.get(str(user_id), 0)

def update_roulette_stat(user_id, stat_type, amount=1):
    uid = str(user_id)
    if uid not in roulette_stats:
        roulette_stats[uid] = {"eliminated": 0, "eliminated_by": 0, "withdrawals": 0, "wins": 0}
    roulette_stats[uid][stat_type] = roulette_stats[uid].get(stat_type, 0) + amount
    save_json(ROULETTE_STATS_FILE, roulette_stats)

# --- 3. إعدادات البوت والـ Intents ---
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="-", intents=intents)

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
    try:
        return ImageFont.truetype("arial.ttf", size)
    except IOError:
        return ImageFont.load_default()

active_games = {} # {channel_id: {"type": "...", ...}}

# --- 4. رسم صور العجلة وبانرات اللعبة ---
def process_arabic_text(text):
    return arabic_reshaper.reshape(text)

def generate_wheel_image(members, chosen_member=None):
    size = 600
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    center = size // 2
    radius = 260
    n = len(members)
    if n == 0:
        return None

    colors = [(147, 51, 234), (126, 34, 206), (168, 85, 247), (192, 132, 252)]
    angle_per_slice = 360 / n
    font = get_arabic_font(22)

    chosen_index = 0
    if chosen_member and chosen_member in members:
        chosen_index = members.index(chosen_member)

    # حساب زاوية دوران تجعل السهم (عند الزاوية 0 يمين) يؤشر على القطاع المختار
    offset_angle = 360 - (chosen_index * angle_per_slice + angle_per_slice / 2)

    for i, m in enumerate(members):
        start_deg = i * angle_per_slice + offset_angle
        end_deg = (i + 1) * angle_per_slice + offset_angle
        color = colors[i % len(colors)]
        draw.pieslice([center - radius, center - radius, center + radius, center + radius],
                      start=start_deg, end=end_deg, fill=color, outline=(255, 255, 255), width=3)

        # كتابة اسم العضو
        mid_angle = math.radians((start_deg + end_deg) / 2)
        text_x = center + (radius * 0.65) * math.cos(mid_angle)
        text_y = center + (radius * 0.65) * math.sin(mid_angle)
        
        display_name = process_arabic_text(m.display_name[:12])
        draw.text((text_x, text_y), display_name, fill=(255, 255, 255), font=font, anchor="mm")

    # دائرة السنتر
    center_r = 80
    draw.ellipse([center - center_r, center - center_r, center + center_r, center + center_r], fill=(30, 27, 75), outline=(255, 255, 255), width=4)

    # السهم المؤشر على اليمين
    arrow = [(center + radius + 15, center), (center + radius - 15, center - 15), (center + radius - 15, center + 15)]
    draw.polygon(arrow, fill=(255, 255, 255))

    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr

def generate_banner_image(title_text):
    img = Image.new("RGBA", (700, 350), (20, 20, 25, 255))
    draw = ImageDraw.Draw(img)
    
    font = get_arabic_font(55)
    arabic_text = process_arabic_text(title_text)
    draw.text((350, 175), arabic_text, fill=(255, 255, 255), font=font, anchor="mm")
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr

# --- 5. واجهات الأزرار للروليت ---
class RouletteLobbyView(View):
    def __init__(self, game_data):
        super().__init__(timeout=20)
        self.game_data = game_data

    @discord.ui.button(label="انضمام", style=discord.ButtonStyle.success, emoji="📥")
    async def join_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user in self.game_data["players"]:
            await interaction.response.send_message("أنت انضممت بالفعل إلى اللعبة!", ephemeral=True)
            return
        
        self.game_data["players"].append(interaction.user)
        await interaction.response.send_message(f"✅ تم الانضمام إلى اللعبة {interaction.user.mention}")

    @discord.ui.button(label="انسحاب", style=discord.ButtonStyle.danger, emoji="📤")
    async def leave_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user not in self.game_data["players"]:
            await interaction.response.send_message("أنت لست منضماً للعبة أساساً!", ephemeral=True)
            return
        
        self.game_data["players"].remove(interaction.user)
        update_roulette_stat(interaction.user.id, "withdrawals")
        await interaction.response.send_message(f"🚪 تم انسحاب {interaction.user.mention} من اللعبة.")

    @discord.ui.button(label="إحصائيات", style=discord.ButtonStyle.secondary, emoji="📊")
    async def stats_button(self, interaction: discord.Interaction, button: Button):
        uid = str(interaction.user.id)
        stats = roulette_stats.get(uid, {"eliminated": 0, "eliminated_by": 0, "withdrawals": 0, "wins": 0})
        
        embed = discord.Embed(title="📊 الإحصائيات", color=discord.Color.purple())
        embed.add_field(name="تم طرد:", value=f"**{stats['eliminated']}**", inline=False)
        embed.add_field(name="تم طردك:", value=f"**{stats['eliminated_by']}**", inline=False)
        embed.add_field(name="تم الانسحاب:", value=f"**{stats['withdrawals']}**", inline=False)
        embed.add_field(name="الفوز:", value=f"**{stats['wins']}**", inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class EliminationView(View):
    def __init__(self, chosen_player, eligible_targets, game_data):
        super().__init__(timeout=15)
        self.chosen_player = chosen_player
        self.eligible_targets = eligible_targets
        self.game_data = game_data
        self.selected_target = None

        # إضافة أزرار للاعبين القابلين للطرد
        for idx, target in enumerate(eligible_targets[:10], start=1):
            btn = Button(label=f"{idx} - {target.display_name[:10]}", style=discord.ButtonStyle.secondary)
            btn.callback = self.make_target_callback(target)
            self.add_item(btn)

        # زر الطرد العشوائي
        random_btn = Button(label="عشوائي", style=discord.ButtonStyle.danger, emoji="🔀")
        random_btn.callback = self.random_callback
        self.add_item(random_btn)

    def make_target_callback(self, target):
        async def callback(interaction: discord.Interaction):
            if interaction.user != self.chosen_player:
                await interaction.response.send_message("ليس دورك في الطرد!", ephemeral=True)
                return
            self.selected_target = target
            self.stop()
            await interaction.response.send_message(f"تم اختيار طرد {target.mention}", ephemeral=True)
        return callback

    async def random_callback(self, interaction: discord.Interaction):
        if interaction.user != self.chosen_player:
            await interaction.response.send_message("ليس دورك في الطرد!", ephemeral=True)
            return
        self.selected_target = random.choice(self.eligible_targets)
        self.stop()
        await interaction.response.send_message(f"تم اختيار طرد عشوائي!", ephemeral=True)

# --- 6. الألعاب النصية الأصلية ---
GAMES_DATA = {
    "حيوان": [{"prompt": "بحرف أ", "answers": ["أسد", "أرنب", "أفعى"]}],
    "جماد": [{"prompt": "بحرف أ", "answers": ["أبريق", "أريكة", "أنبوب"]}],
    "بلاد": [{"prompt": "بحرف أ", "answers": ["أمريكا", "ألمانيا"]}],
    "اسم": [{"prompt": "بحرف أ", "answers": ["أحمد", "أميرة"]}],
    "مفرد": [{"prompt": "رياح", "answers": ["ريح"]}],
    "اسرع": [{"prompt": "حاسوب", "answers": ["حاسوب"]}]
}

async def game_timer(channel, channel_id):
    await asyncio.sleep(7)
    if channel_id in active_games and active_games[channel_id].get("type") == "classic":
        del active_games[channel_id]
        await channel.send("⏱️ **انتهى الوقت!** لم يقم أحد بالإجابة الصحيحة.")

# --- 7. منطق تشغيل لعبة الروليت ---
async def start_roulette_game(channel):
    channel_id = channel.id
    game_data = {"type": "roulette", "players": []}
    active_games[channel_id] = game_data

    # 1. إرسال صورة الروليت وبدء فترة التسجيل (20 ثانية)
    banner_bytes = generate_banner_image("روليت")
    file = discord.File(fp=banner_bytes, filename="roulette.png")
    view = RouletteLobbyView(game_data)
    
    lobby_msg = await channel.send(file=file, view=view)
    await asyncio.sleep(20)

    # إلغاء أزرار اللوبي
    for child in view.children:
        child.disabled = True
    await lobby_msg.edit(view=view)

    players = game_data["players"]
    if len(players) < 2:
        await channel.send("⚠️ **تم إلغاء اللعبة!** يتطلب بدء الروليت مشاركة شخصين على الأقل.")
        del active_games[channel_id]
        return

    await channel.send("⏳ **تم الانتهاء من تسجيل اللعبة، ستبدأ الجولة خلال ثواني...**")
    await asyncio.sleep(3)

    # 2. حلقة الجولات
    while len(players) > 1:
        if len(players) == 2:
            await channel.send("🔥 **الجولة القادمة هي الأخيرة! من تختاره العجلة يفوز باللعبة!** 🏆")
            await asyncio.sleep(2)

        # اختيار الشخص الذي وقع عليه السهم
        chosen_player = random.choice(players)

        # توليد صورة العجلة وإرسالها
        wheel_bytes = generate_wheel_image(players, chosen_player)
        wheel_file = discord.File(fp=wheel_bytes, filename="wheel.png")
        await channel.send(file=wheel_file)
        await asyncio.sleep(2)

        # إذا كانت الجولة الأخيرة (باقي شخصين) - الشخص المختار هو الفائز مباشر
        if len(players) == 2:
            winner = chosen_player
            players.remove(winner)
            
            # إضافة نقاط للفائز بين 1 و 5
            won_points = random.randint(1, 5)
            add_user_points(winner.id, won_points)
            update_roulette_stat(winner.id, "wins")

            # إرسال صورة وشعار الفائز
            banner_win = generate_banner_image("الفائز")
            win_file = discord.File(fp=banner_win, filename="winner.png")
            
            await channel.send(
                content=f"🏆 {winner.mention} @here\n🎉 **مبروك الفوز بالروليت!** وحصلت على **{won_points}** نقاط!",
                file=win_file
            )
            del active_games[channel_id]
            return

        # إذا كان باقي أكثر من شخصين - اختيار لاعب للطرد
        eligible_targets = [p for p in players if p != chosen_player]
        elim_view = EliminationView(chosen_player, eligible_targets, game_data)
        
        prompt_msg = await channel.send(
            f"⏳ {chosen_player.mention}، لديك **15 ثانية** لاختيار لاعب لطرده! 🎯",
            view=elim_view
        )

        # انتظار اختيار العضو خلال 15 ثانية
        await elim_view.wait()

        target_to_remove = elim_view.selected_target
        if not target_to_remove:
            # طرد عشوائي في حال انتهاء الوقت
            target_to_remove = random.choice(eligible_targets)

        # تحديث الإحصائيات وطرده من اللعبة
        players.remove(target_to_remove)
        update_roulette_stat(chosen_player.id, "eliminated")
        update_roulette_stat(target_to_remove.id, "eliminated_by")

        # تعطيل أزرار الاختيار
        for child in elim_view.children:
            child.disabled = True
        await prompt_msg.edit(view=elim_view)

        await channel.send(f"❌ تم طرد {target_to_remove.mention}! سوف تبدأ الجولة القادمة خلال ثواني... ⏳")
        await asyncio.sleep(3)

    del active_games[channel_id]

# --- 8. الأحداث والأوامر ---
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
        games_list = (
            "🎮 **قائمة الألعاب المتوفرة:**\n"
            "• `روليت`\n"
            "• `حيوان` | `جماد` | `بلاد` | `اسم` | `مفرد` | `اسرع`\n\n"
            "🎯 لمعرفة نقاطك اكتب `نقاطي`.\n"
            "🛑 لإيقاف أي لعبة جارية، اكتب `إيقاف`."
        )
        await message.channel.send(games_list)
        return

    # --- أمر نقاطي ---
    if text in ["نقاطي", "-نقاطي"]:
        pts = get_user_points(message.author.id)
        await message.channel.send(f"🏆 {message.author.mention} نقاطك هي: **{pts}** نقطة.")
        return

    # --- أمر إيقاف اللعبة ---
    if text in ["إيقاف", "ايقاف", "وقف"]:
        if channel_id in active_games:
            del active_games[channel_id]
            await message.channel.send("🛑 تم إيقاف اللعبة الحالية بنجاح.")
        else:
            await message.channel.send("⚠️ لا توجد لعبة شغالّة حالياً في هذه الروم.")
        return

    # --- بدء لعبة الروليت ---
    if text in ["روليت", "-روليت"]:
        if channel_id in active_games:
            await message.channel.send("⚠️ هناك لعبة جارية بالفعل في هذه الروم!")
            return
        asyncio.create_task(start_roulette_game(message.channel))
        return

    # --- الألعاب الكلاسيكية ---
    clean_command = text.lstrip("-")
    if clean_command in GAMES_DATA:
        if channel_id in active_games:
            await message.channel.send("⚠️ هناك لعبة جارية بالفعل في هذه الروم!")
            return

        item = random.choice(GAMES_DATA[clean_command])
        timer_task = asyncio.create_task(game_timer(message.channel, channel_id))

        active_games[channel_id] = {
            "type": "classic",
            "answers": item["answers"],
            "task": timer_task
        }

        async with message.channel.typing():
            img_bytes = generate_banner_image(clean_command)
            file = discord.File(fp=img_bytes, filename="game.png")
            await message.channel.send(file=file)
        return

    # --- التحقق من أجوبة الألعاب الكلاسيكية ---
    if channel_id in active_games and active_games[channel_id].get("type") == "classic":
        game_info = active_games[channel_id]
        if text in game_info["answers"]:
            task = game_info.get("task")
            if task and not task.done():
                task.cancel()
            del active_games[channel_id]

            earned_points = random.randint(10, 30)
            total_pts = add_user_points(message.author.id, earned_points)
            await message.channel.send(f"✨ {message.author.mention} إجابتك صحيحة!\n حصلت على **{earned_points}** نقطة ! (إجمالي نقاطك     : **{total_pts}**)")
            return

    await bot.process_commands(message)

# --- 9. التشغيل ---
keep_alive()
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
