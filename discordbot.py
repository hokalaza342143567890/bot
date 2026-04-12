import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
from gtts import gTTS
import threading
import json
import random
# ====== Configuration for Tier List JSON file ======
TIER_LISTS_FILE = "tier_lists.json"

def load_tier_lists():
    global tier_lists
    try:
        with open(TIER_LISTS_FILE, "r", encoding="utf-8") as f:
            tier_lists = json.load(f)
    except Exception:
        tier_lists = {}

def save_tier_lists():
    with open(TIER_LISTS_FILE, "w", encoding="utf-8") as f:
        json.dump(tier_lists, f, ensure_ascii=False, indent=4)

# ====== Load English Dictionary ======
def load_english_dictionary():
    try:
        with open("english_words.txt", "r", encoding="utf-8") as f:
            # Filter out short words (3 chars or less) to exclude abbreviations/shortcuts
            return set(word.strip().lower() for word in f if word.strip() and len(word.strip()) >= 4)
    except Exception:
        # Default sample dictionary if file not found
        return {
            "apple","banana","cart","dogs","elephant","fish","grape","house",
            "iced","jungle","kite","lemon","monkey","notebook","orange","pencil",
            "queen","rabbit","strawberry","tiger","umbrella","violin","watermelon",
            "xylophone","yogurt","zebra","appetite","eggplant","tiny"
        }

english_dictionary = load_english_dictionary()

# ====== Initialize Bot and Global Variables ======
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)
volume_level = 2.0
deleted_messages = {}
ALLOWED_USERS = [861443399508164638, 1147476712867762316]

tier_lists = {}

# Globals for Word Chain
wordchain_games = {}
wordchain_used = {}
wordchain_last_user = {}

# Cooldown for /pp and /pl
last_pp_usage = 0
last_pl_usage = 0
ALLOWED_PP_ROLE_ID = 1330163237047763080

load_tier_lists()

# ====== Essential Commands (Slash) ======
@bot.tree.command(name="join", description="Join your current voice channel")
async def join_slash(interaction: discord.Interaction):
    if not interaction.user.voice:
        return await interaction.response.send_message(
            "You must join a voice channel first!", ephemeral=True
        )
    channel = interaction.user.voice.channel
    vc = interaction.guild.voice_client
    if vc and vc.is_connected():
        await vc.move_to(channel)
    else:
        await channel.connect()
    await interaction.response.send_message(f"✅ Joined **{channel.name}**.", ephemeral=True)

@bot.tree.command(name="leave", description="Leave the current voice channel")
async def leave_slash(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc or not vc.is_connected():
        return await interaction.response.send_message(
            "I'm not in a voice channel.", ephemeral=True
        )
    await vc.disconnect()
    await interaction.response.send_message("✅ Left the voice channel.", ephemeral=True)

@bot.tree.command(name="type", description="Make the bot send a message in this channel")
@app_commands.describe(message="Message to send")
async def type_slash(interaction: discord.Interaction, message: str):
    # Slash commands can't delete your message like prefix commands did.
    await interaction.response.defer(ephemeral=True)
    await interaction.channel.send(message)
    await interaction.followup.send("✅ Sent.", ephemeral=True)

@bot.tree.command(name="ping", description="Show bot latency")
async def ping_slash(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"Pong! {round(bot.latency * 1000)} ms", ephemeral=True
    )

# ====== Snipe Command (capture text + attachments) ======
deleted_messages = {}  # map channel_id -> (content, author, [attachment URLs])

@bot.event
async def on_message_delete(message):
    """Lưu tin nhắn bị xóa, bao gồm text và attachments."""
    author = str(message.author)
    content = message.content or ""
    attachments = [att.url for att in message.attachments]
    deleted_messages[message.channel.id] = (content, author, attachments)

@bot.tree.command(name="snipe", description="Show the most recently deleted message in this channel")
async def snipe_slash(interaction: discord.Interaction):
    """Hiển thị tin nhắn bị xóa cuối cùng của kênh, bao gồm ảnh và file."""
    data = deleted_messages.get(interaction.channel.id)
    if not data:
        return await interaction.response.send_message(
            "Không có tin nhắn nào bị xóa gần đây.", ephemeral=True
        )
    content, author, attachments = data

    embed = discord.Embed(
        title="📦 Sniped Message",
        description=content or "*Không có nội dung văn bản*",
        color=discord.Color.blurple()
    )
    embed.set_author(name=author)

    await interaction.response.send_message(embed=embed)
    for url in attachments:
        await interaction.channel.send(url)

# ====== Slash Command: say ======
@bot.tree.command(
    name="say",
    description="Convert text to speech and play in voice channel"
)
@app_commands.describe(text="Text to speak")
async def say_slash(interaction: discord.Interaction, text: str):
    if not interaction.user.voice:
        return await interaction.response.send_message(
            "You must join a voice channel!", ephemeral=True
        )
    if not interaction.guild.voice_client:
        await interaction.user.voice.channel.connect()
    tts = gTTS(text=text, lang="vi")
    tts.save("voice.mp3")
    ffmpeg_opts = {'options': f'-filter:a "volume={volume_level}"'}
    audio_source = discord.FFmpegPCMAudio("voice.mp3", **ffmpeg_opts)
    vc = interaction.guild.voice_client
    if not vc.is_playing():
        vc.play(audio_source, after=lambda e: os.remove("voice.mp3"))
        await interaction.response.send_message(f"🔊 Now playing: {text}")
    else:
        await interaction.response.send_message(
            "I'm already playing audio, please try again later.",
            ephemeral=True
        )

# ====== Tier List Slash Commands ======
@bot.tree.command(
    name="createtierlist",
    description="Create a new tier list"
)
@app_commands.describe(name="Tier list name")
async def createtierlist(interaction: discord.Interaction, name: str):
    if interaction.user.id not in ALLOWED_USERS:
        return await interaction.response.send_message(
            "You do not have permission!", ephemeral=True
        )
    if name in tier_lists:
        return await interaction.response.send_message(
            f"Tier list '{name}' already exists!", ephemeral=True
        )
    tier_lists[name] = {}
    save_tier_lists()
    await interaction.response.send_message(f"Tier list '{name}' created!")

@bot.tree.command(
    name="addtotierlist",
    description="Add items to an existing tier list"
)
@app_commands.describe(
    tier_list_name="Tier list name",
    tier="Tier (e.g. S, A, B)",
    required_item="Required item",
    optional_item2="Optional item 2",
    optional_item3="Optional item 3",
    optional_item4="Optional item 4",
    optional_item5="Optional item 5"
)
async def addtotierlist(
    interaction: discord.Interaction,
    tier_list_name: str,
    tier: str,
    required_item: str,
    optional_item2: str = None,
    optional_item3: str = None,
    optional_item4: str = None,
    optional_item5: str = None
):
    if interaction.user.id not in ALLOWED_USERS:
        return await interaction.response.send_message(
            "You do not have permission to add items!", ephemeral=True
        )
    if tier_list_name not in tier_lists:
        return await interaction.response.send_message(
            f"Tier list '{tier_list_name}' does not exist!", ephemeral=True
        )
    if tier not in tier_lists[tier_list_name]:
        tier_lists[tier_list_name][tier] = []
    tier_lists[tier_list_name][tier].append(required_item)
    for opt in [optional_item2, optional_item3, optional_item4, optional_item5]:
        if opt:
            tier_lists[tier_list_name][tier].append(opt)
    save_tier_lists()
    msg = f"Added to tier '{tier}' in '{tier_list_name}':\n- {required_item}"
    for x in [optional_item2, optional_item3, optional_item4, optional_item5]:
        if x:
            msg += f"\n- {x}"
    await interaction.response.send_message(msg)

@bot.tree.command(
    name="movetotierlist",
    description="Move an item to another tier"
)
@app_commands.describe(
    tier_list_name="Tier list name",
    from_tier="Current tier",
    to_tier="New tier",
    item="Item to move"
)
async def movetotierlist(
    interaction: discord.Interaction,
    tier_list_name: str,
    from_tier: str,
    to_tier: str,
    item: str
):
    if interaction.user.id not in ALLOWED_USERS:
        return await interaction.response.send_message(
            "You do not have permission!", ephemeral=True
        )
    if tier_list_name not in tier_lists:
        return await interaction.response.send_message(
            f"Tier list '{tier_list_name}' does not exist!", ephemeral=True
        )
    if from_tier not in tier_lists[tier_list_name]:
        return await interaction.response.send_message(
            f"Tier '{from_tier}' does not exist!", ephemeral=True
        )
    if item not in tier_lists[tier_list_name][from_tier]:
        return await interaction.response.send_message(
            f"Item '{item}' is not in tier '{from_tier}'!", ephemeral=True
        )
    tier_lists[tier_list_name][from_tier].remove(item)
    if to_tier not in tier_lists[tier_list_name]:
        tier_lists[tier_list_name][to_tier] = []
    tier_lists[tier_list_name][to_tier].append(item)
    save_tier_lists()
    await interaction.response.send_message(
        f"Moved '{item}' from '{from_tier}' to '{to_tier}'!"
    )

@bot.tree.command(
    name="removetotierlist",
    description="Remove an item from a tier"
)
@app_commands.describe(
    tier_list_name="Tier list name",
    tier="Tier containing the item",
    item="Item to remove"
)
async def removetotierlist(
    interaction: discord.Interaction,
    tier_list_name: str,
    tier: str,
    item: str
):
    if interaction.user.id not in ALLOWED_USERS:
        return await interaction.response.send_message(
            "You do not have permission!", ephemeral=True
        )
    if tier_list_name not in tier_lists:
        return await interaction.response.send_message(
            f"Tier list '{tier_list_name}' does not exist!", ephemeral=True
        )
    if tier not in tier_lists[tier_list_name]:
        return await interaction.response.send_message(
            f"Tier '{tier}' does not exist!", ephemeral=True
        )
    if item not in tier_lists[tier_list_name][tier]:
        return await interaction.response.send_message(
            f"Item '{item}' is not in tier '{tier}'!", ephemeral=True
        )
    tier_lists[tier_list_name][tier].remove(item)
    save_tier_lists()
    await interaction.response.send_message(
        f"Removed '{item}' from tier '{tier}'!"
    )

@bot.tree.command(name="showtierlist", description="tier list cua ecstasy cap nhat theo phong do scrim,league")
async def showtierlist(interaction: discord.Interaction):
    if not tier_lists:
        await interaction.response.send_message("Không có tier list nào.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📊 Tier Lists",
        description="Dưới đây là tất cả các tier và số lượng player trong mỗi tier:",
        color=discord.Color.blue()
    )

    total_players = 0
    # Assume one single tierlist in tier_lists; if you have multiple, remove the outer [0]
    list_name, tiers = next(iter(tier_lists.items()))
    list_total = sum(len(items) for items in tiers.values())
    embed.add_field(
        name=f"Tier List: {list_name}",
        value=f"Tổng player: {list_total}",
        inline=False
    )

    for tier_name, items in tiers.items():
        count = len(items)
        total_players += count
        # show “Empty” or bullet list
        if count == 0:
            value = "Empty"
        else:
            value = "\n".join(f"• {x}" for x in items)
        embed.add_field(
            name=f"Tier {tier_name} ({count} player{'s' if count != 1 else ''})",
            value=value,
            inline=False
        )

    embed.add_field(
        name="📈 Tổng cộng",
        value=f"Tổng số player qua tất cả tier lists: {total_players}",
        inline=False
    )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="reordertiers",
    description="Reorder tiers in your single tier list (comma-separated)"
)
@app_commands.describe(order="Comma-separated tiers in the new order, e.g. S,A,B,C,D,N")
async def reordertiers(interaction: discord.Interaction, order: str):
    # permission check
    if interaction.user.id not in ALLOWED_USERS:
        return await interaction.response.send_message(
            "Bạn không có quyền sử dụng lệnh này.", ephemeral=True
        )

    # ensure there's at least one tier list
    if not tier_lists:
        return await interaction.response.send_message("Không có tier list nào.", ephemeral=True)

    list_name, tiers = next(iter(tier_lists.items()))
    requested = [t.strip() for t in order.split(",") if t.strip()]
    missing = [t for t in requested if t not in tiers]
    if missing:
        return await interaction.response.send_message(
            f"Các tier sau không tồn tại: {', '.join(missing)}", ephemeral=True
        )

    # rebuild ordered dict
    new_tiers = {t: tiers[t] for t in requested}
    # append any tiers not mentioned at end in original order
    for t in tiers:
        if t not in new_tiers:
            new_tiers[t] = tiers[t]

    tier_lists[list_name] = new_tiers
    save_tier_lists()

    await interaction.response.send_message(
        f"Đã sắp xếp lại tiers thành: {', '.join(new_tiers.keys())}"
    )
# ====== Minigame: Word Chain ======
@bot.tree.command(
    name="wordchainstart",
    description="Start an English word chain game"
)
@app_commands.describe(initial_word="Initial word (optional)")
async def wordchainstart(interaction: discord.Interaction, initial_word: str = None):
    if interaction.channel.id in wordchain_games:
        return await interaction.response.send_message(
            "A game is already running!", ephemeral=True
        )
    if initial_word is None:
        initial_word = random.choice(list(english_dictionary))
    initial_word = initial_word.strip().lower()
    if initial_word not in english_dictionary:
        return await interaction.response.send_message(
            "The word is not in dictionary.", ephemeral=True
        )
    wordchain_games[interaction.channel.id] = initial_word
    wordchain_used[interaction.channel.id] = {initial_word}
    wordchain_last_user[interaction.channel.id] = None
    await interaction.response.send_message(
        f"Game started! Initial: **{initial_word}**. Next must start with **{initial_word[-1]}**"
    )

@bot.tree.command(
    name="wordchainstop",
    description="Stop the English word chain game"
)
async def wordchainstop(interaction: discord.Interaction):
    if interaction.channel.id not in wordchain_games:
        return await interaction.response.send_message(
            "No game running!", ephemeral=True
        )
    del wordchain_games[interaction.channel.id]
    del wordchain_used[interaction.channel.id]
    del wordchain_last_user[interaction.channel.id]
    await interaction.response.send_message("Game stopped.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.channel.id in wordchain_games:
        current = wordchain_games[message.channel.id]
        letter = current[-1]
        word = message.content.strip().lower()
        if " " in word:
            await message.channel.send("Enter a single word.")
        elif word not in english_dictionary:
            await message.channel.send("Not in dictionary.")
        elif not word.startswith(letter):
            await message.channel.send(f"Must start with **{letter}**.")
        elif word in wordchain_used[message.channel.id]:
            await message.channel.send(f"You already used **{word}**.")
        elif wordchain_last_user[message.channel.id] == message.author.id:
            await message.channel.send("Wait your turn!")
        else:
            wordchain_used[message.channel.id].add(word)
            wordchain_games[message.channel.id] = word
            wordchain_last_user[message.channel.id] = message.author.id
            await message.channel.send(
                f"Accepted: **{word}**. Next: **{word[-1]}**"
            )
    await bot.process_commands(message)

# ====== /pp and /pl Commands ======
PP_CHANNEL_ID = 1330163239455293463
PL_CHANNEL_ID = 1330163239455293464

@bot.tree.command(
    name="pp",
    description="Send 5 @everyone messages to PP channel"
)
async def pp_command(interaction: discord.Interaction):
    if not any(role.id == ALLOWED_PP_ROLE_ID for role in interaction.user.roles):
        return await interaction.response.send_message(
            "No permission!", ephemeral=True
        )
    await interaction.response.defer(ephemeral=True)
    ch = interaction.guild.get_channel(PP_CHANNEL_ID)
    if not ch:
        return await interaction.followup.send("Channel not found.", ephemeral=True)
    for _ in range(5):
        await ch.send("@everyone")
        await asyncio.sleep(2)
    await interaction.followup.send("Done!", ephemeral=True)

@bot.tree.command(
    name="pl",
    description="Send 5 @everyone messages to PL channel"
)
async def pl_command(interaction: discord.Interaction):
    if not any(role.id == ALLOWED_PP_ROLE_ID for role in interaction.user.roles):
        return await interaction.response.send_message(
            "No permission!", ephemeral=True
        )
    await interaction.response.defer(ephemeral=True)
    ch = interaction.guild.get_channel(PL_CHANNEL_ID)
    if not ch:
        return await interaction.followup.send("Channel not found.", ephemeral=True)
    for _ in range(5):
        await ch.send("@everyone")
        await asyncio.sleep(2)
    await interaction.followup.send("Done!", ephemeral=True)
# ====== Purge Commands ======

@bot.tree.command(name="purge", description="Delete a number of messages")
@app_commands.describe(number="How many messages to delete (1-100)")
async def purge_slash(interaction: discord.Interaction, number: app_commands.Range[int, 1, 100]):
    """Slash command to purge messages."""
    if not interaction.permissions.manage_messages:
        return await interaction.response.send_message("You need Manage Messages permission to use this.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=number)
    await interaction.followup.send(f"🗑️ Deleted {len(deleted)} messages.", ephemeral=True)

# ====== !cmds ======
@bot.tree.command(name="cmds", description="Show all available commands")
async def cmds_slash(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📜 Command List",
        description="Available commands",
        color=discord.Color.green()
    )
    slash_cmds = [
        "/join", "/leave", "/type", "/ping", "/snipe", "/purge", "/cmds",
        "/say", "/createtierlist", "/addtotierlist", "/movetotierlist",
        "/removetotierlist", "/showtierlist", "/reordertiers",
        "/wordchainstart", "/wordchainstop", "/pp", "/pl"
    ]
    embed.add_field(name="Slash Commands", value="\n".join(slash_cmds), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

def console_commands():
    import sys
    while True:
        try:
            command = input("Nhập lệnh: ").strip()
            if not command:
                continue

            cmd, _, rest = command.partition(" ")
            cmd = cmd.lower()

            if cmd == "stop":
                print("🛑 Dừng bot...")
                bot.loop.stop()
                os._exit(0)

            elif cmd == "restart":
                print("🔄 Khởi động lại bot...")
                os.execv(sys.executable, ['python'] + sys.argv)

            elif cmd == "say":
                # reuse your slash say logic but for console:
                text = rest
                # find a voice client in any guild
                vc = None
                for guild in bot.guilds:
                    if guild.voice_client:
                        vc = guild.voice_client
                        break
                if vc:
                    tts = gTTS(text=text, lang="vi")
                    tts.save("voice.mp3")
                    ffmpeg_opts = {'options': f'-filter:a "volume={volume_level}"'}
                    source = discord.FFmpegPCMAudio("voice.mp3", **ffmpeg_opts)
                    vc.play(source, after=lambda e: os.remove("voice.mp3"))
                    print(f"✅ Đã đọc: {text}")
                else:
                    print("⚠️ Bot chưa vào voice channel.")

            elif cmd == "type":
                # usage: type <channel_id> <message…> numbers=<count>
                if " numbers=" not in rest:
                    print("⚠️ Cách dùng: type <channel_id> <message> numbers=<count>")
                    continue

                before, _, numpart = rest.rpartition(" numbers=")
                try:
                    count = int(numpart)
                except:
                    print("⚠️ 'numbers' phải là số nguyên.")
                    continue

                cid_str, _, msg = before.partition(" ")
                try:
                    cid = int(cid_str)
                except:
                    print("⚠️ Channel ID không hợp lệ.")
                    continue

                ch = bot.get_channel(cid)
                if not ch:
                    print(f"⚠️ Không tìm thấy channel {cid}.")
                    continue

                for _ in range(count):
                    asyncio.run_coroutine_threadsafe(ch.send(msg), bot.loop)
                print(f"✅ Đã gửi {count} tin nhắn đến {cid}: {msg}")

            else:
                print("❌ Lệnh không hợp lệ.")

        except Exception as e:
            print(f"⚠️ Lỗi trong console_commands: {e}")

# start console thread _before_ running the bot
threading.Thread(target=console_commands, daemon=True).start()

@bot.event
async def on_ready():
    print(f"Bot đã đăng nhập: {bot.user}")

    # Force a full re-upload of all slash commands:
    synced = await bot.tree.sync()
    print(f"Đã đồng bộ {len(synced)} slash commands!")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN environment variable.")
bot.run(TOKEN)
