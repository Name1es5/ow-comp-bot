import nextcord
from nextcord.ext import commands
from nextcord import Interaction, SlashOption
import sqlite3
from dotenv import load_dotenv
import os
import datetime
from collections import Counter

load_dotenv()
intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Database Setup ---
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

# --- Constants ---
SEASON_1_START = datetime.datetime(2022, 10, 4)
SEASON_DURATION_WEEKS = 9

def get_current_season():
    now = datetime.datetime.utcnow()
    delta = now - SEASON_1_START
    return delta.days // (SEASON_DURATION_WEEKS * 7) + 1

ROLE_HEROES = {
    "Tank": ["Doomfist", "D.Va", "Ramattra", "Reinhardt", "Roadhog", "Sigma", "Winston", "Zarya"],
    "DPS": ["Ashe", "Bastion", "Cassidy", "Echo", "Freja", "Genji", "Hanzo", "Junkrat", "Mei", "Pharah", "Reaper",
            "Sojourn", "Soldier: 76", "Sombra", "Symmetra", "Torbjörn", "Tracer", "Venture", "Widowmaker"],
    "Support": ["Ana", "Baptiste", "Brigitte", "Illari", "Kiriko", "Lifeweaver", "Lucio", "Mercy", "Moira", "Zenyatta"]
}

GAMEMODE_MAPS = {
    "Control": ["Antarctic Peninsula", "Busan", "Ilios", "Lijiang Tower", "Nepal", "Oasis", "Samoa"],
    "Escort": ["Circuit Royal", "Dorado", "Havana", "Junkertown", "Rialto", "Route 66", "Shambali Monastery", "Watchpoint: Gibraltar"],
    "Push": ["Colosseo", "Esperança", "New Queen Street", "Runasapi"],
    "Hybrid": ["Blizzard World", "Eichenwalde", "Hollywood", "King's Row", "Midtown", "Numbani", "Paraíso"],
    "Flashpoint": ["New Junk City", "Suravasa"]
}

ALL_HEROES = sum(ROLE_HEROES.values(), [])
ALL_MAPS = [m for maps in GAMEMODE_MAPS.values() for m in maps]
RANK_TIERS = ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master", "Grandmaster", "Champion"]
VALID_RESULTS = ["Win", "Loss"]

# --- Slash Commands ---

@bot.slash_command(name="ping", description="Check if the bot is alive")
async def ping(interaction: Interaction):
    await interaction.response.send_message("🏓 Pong!", ephemeral=True)

@bot.slash_command(name="help", description="List all available commands")
async def help_command(interaction: Interaction):
    embed = nextcord.Embed(title="📘 Commands", color=0x00ff99)
    embed.add_field(name="/record", value="Record a new match", inline=False)
    embed.add_field(name="/result", value="View your match history for this season", inline=False)
    embed.add_field(name="/top_heroes", value="Show your top 3 most played heroes", inline=False)
    embed.add_field(name="/clear", value="Delete all recorded matches", inline=False)
    embed.add_field(name="/delete_last", value="Delete your most recent match", inline=False)
    embed.add_field(name="/ping", value="Check if the bot is responsive", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.slash_command(name="record", description="Record a match")
async def record(
    interaction: Interaction,
    role: str = SlashOption(name="role", description="Enter role (Tank, DPS, Support)", required=True),
    hero: str = SlashOption(name="hero", description="Enter hero name", required=True),
    map: str = SlashOption(name="map", description="Enter map name", required=True),
    rank: str = SlashOption(name="rank", description="Enter rank tier", required=True),
    modifier: int = SlashOption(name="modifier", description="Rank modifier (1-5)", required=True),
    result: str = SlashOption(name="result", description="Match result (Win/Loss)", required=True)
):
    rank_full = f"{rank} {modifier}"
    timestamp = datetime.datetime.utcnow().isoformat()

    with sqlite3.connect("matches.db") as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO matches (user_id, hero, role, map, rank, result, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (interaction.user.id, hero, role, map, rank_full, result, timestamp))
        conn.commit()

    await interaction.response.send_message("✅ Match recorded!", ephemeral=True)

@record.on_autocomplete("role")
async def autocomplete_role(interaction: Interaction, input: str):
    return [r for r in ROLE_HEROES if input.lower() in r.lower()]
    
@record.on_autocomplete("hero")
async def autocomplete_hero(interaction: Interaction, input: str):
    role = None
    options = interaction.data.get("options", [])

    # Handle both nested and flat command structures
    for option in options:
        if option["name"] == "role":
            role = option.get("value")
        elif option["name"] == "hero" and "options" in option:
            for sub in option["options"]:
                if sub["name"] == "role":
                    role = sub.get("value")

    hero_pool = ROLE_HEROES.get(role, ALL_HEROES)
    return [h for h in hero_pool if input.lower() in h.lower()][:25]


@record.on_autocomplete("map")
async def autocomplete_map(interaction: Interaction, input: str):
    return [m for m in ALL_MAPS if input.lower() in m.lower()][:25]

@record.on_autocomplete("rank")
async def autocomplete_rank(interaction: Interaction, input: str):
    return [r for r in RANK_TIERS if input.lower() in r.lower()]

@record.on_autocomplete("result")
async def autocomplete_result(interaction: Interaction, input: str):
    return [r for r in VALID_RESULTS if input.lower() in r.lower()]

@bot.slash_command(name="result", description="Show your recorded matches for the current season")
async def result(interaction: Interaction):
    user_id = interaction.user.id
    season = get_current_season()
    season_start = SEASON_1_START + datetime.timedelta(weeks=SEASON_DURATION_WEEKS * (season - 1))

    with sqlite3.connect("matches.db") as conn:
        c = conn.cursor()
        c.execute('''
            SELECT hero, role, map, rank, result, timestamp FROM matches
            WHERE user_id = ? AND timestamp >= ?
            ORDER BY rowid DESC
        ''', (user_id, season_start.isoformat()))
        rows = c.fetchall()

    if not rows:
        await interaction.response.send_message("No matches recorded this season.", ephemeral=True)
        return

    embed = nextcord.Embed(
        title="📊 Your Matches",
        description=f"**Season {season}** — {len(rows)} match{'es' if len(rows) != 1 else ''}\nMost recent shown first.",
        color=0x00ff99
    )

    losing_streak = 0
    for _, _, _, _, result_val, _ in rows:
        if result_val.lower() == "loss":
            losing_streak += 1
        else:
            break
    if losing_streak >= 3:
        embed.description = "💡 **Tip:** You've lost 3 games in a row — maybe take a break or drink some water!\n\n" + embed.description

    total = len(rows)
    for i, (hero, role, map_, rank, result_val, ts) in enumerate(rows):
        match_num = total - i
        try:
            dt = datetime.datetime.fromisoformat(ts)
            formatted = f"{dt.month}/{dt.day}/{dt.year % 100:02} {dt.strftime('%I:%M %p')}"
        except:
            formatted = "Unknown"
emoji = "✅" if result_val.lower() == "win" else "❌"
embed.add_field(
    name=f"{emoji} {match_num}. {map_} [{result_val}]",
    value=f"**Role:** {role}, **Rank:** {rank}, **Time:** {formatted}\n**Heroes:** {hero}",
    inline=False
)

        )

    await interaction.response.send_message(embed=embed)

@bot.slash_command(name="top_heroes", description="Show your top 3 most played heroes")
async def top_heroes(interaction: Interaction):
    user_id = interaction.user.id
    with sqlite3.connect("matches.db") as conn:
        c = conn.cursor()
        c.execute("SELECT hero FROM matches WHERE user_id = ?", (user_id,))
        all_heroes = [h.strip() for row in c.fetchall() for h in row[0].split(",")]

    if not all_heroes:
        await interaction.response.send_message("No matches recorded.", ephemeral=True)
        return

    counter = Counter(all_heroes).most_common(3)
    total = sum(dict(counter).values())

    embed = nextcord.Embed(title="🏆 Top 3 Most Played Heroes", color=0x00ff99)
    for hero, count in counter:
        percent = (count / total) * 100
        embed.add_field(name=hero, value=f"{count} games ({percent:.1f}%)", inline=False)

    await interaction.response.send_message(embed=embed)

@bot.slash_command(name="clear", description="Delete all your recorded matches")
async def clear(interaction: Interaction):
    user_id = interaction.user.id
    with sqlite3.connect("matches.db") as conn:
        c = conn.cursor()
        c.execute("DELETE FROM matches WHERE user_id = ?", (user_id,))
        conn.commit()

    await interaction.response.send_message("🗑️ Your match history has been cleared.", ephemeral=True)

@bot.slash_command(name="delete_last", description="Delete your most recent match")
async def delete_last(interaction: Interaction):
    user_id = interaction.user.id
    with sqlite3.connect("matches.db") as conn:
        c = conn.cursor()
        c.execute("SELECT rowid FROM matches WHERE user_id = ? ORDER BY rowid DESC LIMIT 1", (user_id,))
        row = c.fetchone()
        if row:
            c.execute("DELETE FROM matches WHERE rowid = ?", (row[0],))
            conn.commit()
            await interaction.response.send_message("🗑️ Last match deleted.", ephemeral=True)
        else:
            await interaction.response.send_message("No matches to delete.", ephemeral=True)

@bot.event
async def on_ready():
    if not hasattr(bot, "synced"):
        await bot.sync_application_commands()
        bot.synced = True
    print(f"✅ Bot online as {bot.user}")

# --- Start the bot ---
bot.run(os.getenv("BOT_TOKEN"))
