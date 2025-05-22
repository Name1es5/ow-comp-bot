import nextcord
from nextcord.ext import commands
from nextcord import Interaction
import sqlite3
from dotenv import load_dotenv
import os
import datetime
from collections import Counter

load_dotenv()

intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# DB setup
conn = sqlite3.connect("matches.db")
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS matches (
    user_id INTEGER,
    hero TEXT,
    role TEXT,
    map TEXT,
    rank TEXT,
    result TEXT,
    timestamp TEXT
)
''')
conn.commit()

# Constants
SEASON_1_START = datetime.datetime(2022, 10, 4)
SEASON_DURATION_WEEKS = 9

def get_current_season():
    now = datetime.datetime.utcnow()
    delta = now - SEASON_1_START
    return delta.days // (SEASON_DURATION_WEEKS * 7) + 1

# Record match
@bot.slash_command(name="record", description="Record a match result manually.")
async def record(
    interaction: Interaction,
    role: str,
    hero: str,
    map: str,
    rank: str,
    modifier: int,
    result: str
):
    rank_full = f"{rank} {modifier}"
    timestamp = datetime.datetime.utcnow().isoformat()

    with sqlite3.connect("matches.db") as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO matches (user_id, hero, role, map, rank, result, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            interaction.user.id, hero, role, map, rank_full, result, timestamp
        ))
        conn.commit()

    await interaction.response.send_message("✅ Match recorded!", ephemeral=True)

# View matches
@bot.slash_command(name="result", description="View your match history.")
async def result(interaction: Interaction):
    user_id = interaction.user.id
    season = get_current_season()
    season_start = SEASON_1_START + datetime.timedelta(weeks=SEASON_DURATION_WEEKS * (season - 1))

    with sqlite3.connect("matches.db") as conn:
        c = conn.cursor()
        c.execute('''
            SELECT hero, role, map, rank, result, timestamp FROM matches
            WHERE user_id = ? AND timestamp >= ? ORDER BY rowid DESC
        ''', (user_id, season_start.isoformat()))
        rows = c.fetchall()

    if not rows:
        await interaction.response.send_message("No matches recorded this season.", ephemeral=True)
        return

    embed = nextcord.Embed(
        title="📊 Your Matches",
        description=f"**Season {season}** — {len(rows)} matches\nMost recent shown first.",
        color=0x00ff99
    )

    losing_streak = 0
    for _, _, _, _, result_val, _ in rows:
        if result_val.lower() == "loss":
            losing_streak += 1
        else:
            break
    if losing_streak >= 3:
        embed.description += "\n💡 Tip: You've lost 3 games in a row. Take a break!"

    total = len(rows)
    for i, (hero, role, map_, rank, result_val, ts) in enumerate(rows):
        match_num = total - i
        try:
            dt = datetime.datetime.fromisoformat(ts)
            formatted = f"{dt.month}/{dt.day}/{dt.year % 100:02} {dt.strftime('%I:%M %p')}"
        except:
            formatted = "Unknown"

        embed.add_field(
            name=f"{match_num}. {map_} [{result_val}]",
            value=f"**Role:** {role}, **Rank:** {rank}, **Time:** {formatted}\n**Heroes:** {hero}",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

# Top heroes
@bot.slash_command(name="top_heroes", description="Your top 3 most played heroes.")
async def top_heroes(interaction: Interaction):
    with sqlite3.connect("matches.db") as conn:
        c = conn.cursor()
        c.execute("SELECT hero FROM matches WHERE user_id = ?", (interaction.user.id,))
        all_heroes = [h.strip() for row in c.fetchall() for h in row[0].split(",")]

    if not all_heroes:
        await interaction.response.send_message("No data recorded.", ephemeral=True)
        return

    counter = Counter(all_heroes).most_common(3)
    total = sum(dict(counter).values())

    embed = nextcord.Embed(title="🏆 Top 3 Most Played Heroes", color=0x00ff99)
    for hero, count in counter:
        percent = (count / total) * 100
        embed.add_field(name=hero, value=f"{count} games ({percent:.1f}%)", inline=False)

    await interaction.response.send_message(embed=embed)

# Help
@bot.slash_command(name="help", description="Show all commands.")
async def help_cmd(interaction: Interaction):
    embed = nextcord.Embed(title="📖 Bot Commands", color=0x00ff99)
    embed.add_field(name="/record", value="Record a match result.", inline=False)
    embed.add_field(name="/result", value="Show your recorded matches.", inline=False)
    embed.add_field(name="/top_heroes", value="Your top 3 played heroes.", inline=False)
    embed.add_field(name="/clear", value="Clear your match history.", inline=False)
    embed.add_field(name="/delete_last", value="Delete most recent match.", inline=False)
    embed.add_field(name="/ping", value="Bot health check.", inline=False)
    embed.add_field(name="/help", value="Show this help message.", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

# Ping
@bot.slash_command(name="ping", description="Check if bot is responsive.")
async def ping(interaction: Interaction):
    await interaction.response.send_message("🏓 Pong!")

# Run the bot
bot.run(os.getenv("BOT_TOKEN"))
