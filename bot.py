import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
TZ = ZoneInfo("America/Los_Angeles")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from environment")

if TOKEN.startswith("Bot "):
    raise RuntimeError("DISCORD_TOKEN should not start with 'Bot '")

THURSDAY_POST_HOUR = 9
SATURDAY_CHECK_HOUR = 9

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

current_prompt_message_id = None
current_prompt_sunday_text = None


def upcoming_sunday(now: datetime) -> datetime:
    days_ahead = (6 - now.weekday()) % 7
    return now + timedelta(days=days_ahead)


@bot.event
async def on_ready():
    print(f"Using token preview: {TOKEN[:8]}...")
    print(f"Logged in as {bot.user} ({bot.user.id})")
    if not thursday_poster.is_running():
        thursday_poster.start()
    if not saturday_checker.is_running():
        saturday_checker.start()


@tasks.loop(minutes=1)
async def thursday_poster():
    global current_prompt_message_id, current_prompt_sunday_text

    now = datetime.now(TZ)

    if now.weekday() != 3:  # Thursday
        return
    if now.hour != THURSDAY_POST_HOUR or now.minute != 0:
        return

    guild = bot.get_guild(GUILD_ID) or await bot.fetch_guild(GUILD_ID)
    channel = guild.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)

    sunday = upcoming_sunday(now)
    try:
        sunday_text = sunday.strftime("%B %-d")
    except ValueError:
        sunday_text = sunday.strftime("%B %d").replace(" 0", " ")

    msg = await channel.send(
        f"Are you going to make this Sunday’s Event ({sunday_text})?\n"
        f"React with 👍 if you can host or attend."
    )
    await msg.add_reaction("👍")

    current_prompt_message_id = msg.id
    current_prompt_sunday_text = sunday_text
    print(f"Posted weekly prompt for {sunday_text}: {msg.id}")


@tasks.loop(minutes=1)
async def saturday_checker():
    global current_prompt_message_id, current_prompt_sunday_text

    now = datetime.now(TZ)

    if now.weekday() != 5:  # Saturday
        return
    if now.hour != SATURDAY_CHECK_HOUR or now.minute != 0:
        return
    if not current_prompt_message_id:
        return

    guild = bot.get_guild(GUILD_ID) or await bot.fetch_guild(GUILD_ID)
    channel = guild.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)

    try:
        message = await channel.fetch_message(current_prompt_message_id)
    except discord.NotFound:
        print("Prompt message not found.")
        current_prompt_message_id = None
        current_prompt_sunday_text = None
        return

    thumbs_up_count = 0
    for reaction in message.reactions:
        if str(reaction.emoji) == "👍":
            thumbs_up_count = max(reaction.count - 1, 0)
            break

    if thumbs_up_count == 0:
        await channel.send(
            f"@everyone Nobody has given a thumbs up for Sunday’s Event "
            f"({current_prompt_sunday_text}). Please find a host.",
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )
        print("Posted escalation ping.")
    else:
        print(f"Found {thumbs_up_count} thumbs up reaction(s); no ping needed.")

    current_prompt_message_id = None
    current_prompt_sunday_text = None

@bot.command()
async def testprompt(ctx):
    now = datetime.now(TZ)
    sunday = upcoming_sunday(now)
    try:
        sunday_text = sunday.strftime("%B %-d")
    except ValueError:
        sunday_text = sunday.strftime("%B %d").replace(" 0", " ")

    msg = await ctx.send(
        f"Are you going to make this Sunday’s Event ({sunday_text})?\n"
        f"React with 👍 if you can host or attend."
    )
    await msg.add_reaction("👍")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id == CHANNEL_ID and bot.user in message.mentions:
        await message.reply(
            "I'm up and running. I post the Sunday host check-in on Thursdays at 9:00 AM "
            "and I escalate on Saturdays at 9:00 AM if nobody reacts with 👍."
        )

    await bot.process_commands(message)


@thursday_poster.before_loop
@saturday_checker.before_loop
async def before_loops():
    await bot.wait_until_ready()


bot.run(TOKEN)
