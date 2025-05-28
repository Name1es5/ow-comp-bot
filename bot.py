import nextcord
from nextcord.ext import commands
from nextcord import Interaction, SlashOption
from nextcord.ui import View, Button
from nextcord import Embed, ButtonStyle
import os
import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from collections import Counter

# Load local .env only if not running in Railway
if os.getenv("RAILWAY_ENVIRONMENT") is None:
    from dotenv import load_dotenv
    load_dotenv()

# Intents configuration
intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- PostgreSQL Connection ---
def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set.")
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

# --- Initialize DB ---
def init_db():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute('''
                    CREATE TABLE IF NOT EXISTS matches (
                        user_id BIGINT,
                        hero TEXT,
                        role TEXT,
                        gamemode TEXT,
                        map TEXT,
                        rank TEXT,
                        result TEXT,
                        timestamp TEXT
                    );
                ''')
                conn.commit()
        print("Database initialized successfully.")
    except Exception as e:
        print("Failed to initialize database:", e)
        raise

# --- Constants ---
SEASON_1_START = datetime.datetime(2022, 10, 4)
SEASON_DURATION_WEEKS = 9

ROLE_HEROES = {
    "Tank": ["Doomfist", "D.Va", "Hazard", "Ramattra", "Reinhardt", "Roadhog", "Sigma", "Winston", "Zarya"],
    "DPS": ["Ashe", "Bastion", "Cassidy", "Echo", "Freja", "Genji", "Hanzo", "Junkrat", "Mei", "Pharah", "Reaper",
            "Sojourn", "Soldier: 76", "Sombra", "Symmetra", "Torbj\u00f6rn", "Tracer", "Venture", "Widowmaker"],
    "Support": ["Ana", "Baptiste", "Brigitte", "Illari", "Kiriko", "Lifeweaver", "Lucio", "Mercy", "Moira", "Zenyatta"]
}

GAMEMODE_MAPS = {
    "Control": ["Antarctic Peninsula", "Busan", "Ilios", "Lijiang Tower", "Nepal", "Oasis", "Samoa"],
    "Escort": ["Circuit Royal", "Dorado", "Havana", "Junkertown", "Rialto", "Route 66", "Shambali Monastery", "Watchpoint: Gibraltar"],
    "Push": ["Colosseo", "Esperan\u00e7a", "New Queen Street", "Runasapi"],
    "Hybrid": ["Blizzard World", "Eichenwalde", "Hollywood", "King's Row", "Midtown", "Numbani", "Para\u00edso"],
    "Flashpoint": ["New Junk City", "Suravasa"]
}

ALL_HEROES = sum(ROLE_HEROES.values(), [])
ALL_MAPS = [m for maps in GAMEMODE_MAPS.values() for m in maps]
RANK_TIERS = ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master", "Grandmaster", "Champion"]
VALID_RESULTS = ["Win", "Loss"]

# --- UI View for Settings ---
class SettingsView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Change Timezone", custom_id="change_timezone", style=ButtonStyle.primary))
        self.add_item(Button(label="Export Data", custom_id="export_data", style=ButtonStyle.success))
        self.add_item(Button(label="GitHub", url="https://github.com/your-repo", style=ButtonStyle.link))

# --- Slash Command: Record a Match ---
@bot.slash_command(name="record", description="Record a match")
async def record(
    interaction: Interaction,
    role: str = SlashOption(name="role", description="Enter role", required=True, autocomplete=True),
    gamemode: str = SlashOption(name="gamemode", description="Enter gamemode", required=True, autocomplete=True),
    hero: str = SlashOption(name="hero", description="Enter hero", required=True, autocomplete=True),
    map: str = SlashOption(name="map", description="Enter map", required=True, autocomplete=True),
    rank: str = SlashOption(name="rank", description="Enter rank", required=True, autocomplete=True),
    modifier: int = SlashOption(name="modifier", description="Rank modifier (1-5)", required=True),
    result: str = SlashOption(name="result", description="Win or Loss", required=True, autocomplete=True)
):
    rank_full = f"{rank} {modifier}"
    timestamp = datetime.datetime.utcnow().isoformat()

    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute('''
                INSERT INTO matches (user_id, hero, role, gamemode, map, rank, result, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (interaction.user.id, hero, role, gamemode, map, rank_full, result, timestamp))
            conn.commit()

    await interaction.response.send_message("Match recorded!", ephemeral=True)

@record.on_autocomplete("role")
async def autocomplete_role(interaction: Interaction, value: str):
    await interaction.response.send_autocomplete([r for r in ROLE_HEROES if value.lower() in r.lower()][:25])

@record.on_autocomplete("gamemode")
async def autocomplete_gamemode(interaction: Interaction, value: str):
    await interaction.response.send_autocomplete([g for g in GAMEMODE_MAPS if value.lower() in g.lower()][:25])

@record.on_autocomplete("hero")
async def autocomplete_hero(interaction: Interaction, value: str):
    await interaction.response.send_autocomplete([h for h in ALL_HEROES if value.lower() in h.lower()][:25])

@record.on_autocomplete("map")
async def autocomplete_map(interaction: Interaction, value: str):
    await interaction.response.send_autocomplete([m for m in ALL_MAPS if value.lower() in m.lower()][:25])

@record.on_autocomplete("rank")
async def autocomplete_rank(interaction: Interaction, value: str):
    await interaction.response.send_autocomplete([r for r in RANK_TIERS if value.lower() in r.lower()][:25])

@record.on_autocomplete("result")
async def autocomplete_result(interaction: Interaction, value: str):
    await interaction.response.send_autocomplete([r for r in VALID_RESULTS if value.lower() in r.lower()][:25])

# --- Slash Command: Show Results ---
@bot.slash_command(name="result", description="Show your recorded matches for the current season")
async def result(interaction: Interaction):
    user_id = interaction.user.id
    days_since_start = (datetime.datetime.utcnow() - SEASON_1_START).days
    season_number = (days_since_start // (SEASON_DURATION_WEEKS * 7)) + 1
    season_start = SEASON_1_START + datetime.timedelta(weeks=(season_number - 1) * SEASON_DURATION_WEEKS)

    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute('''
                SELECT hero, role, map, rank, result, timestamp FROM matches
                WHERE user_id = %s AND timestamp >= %s
                ORDER BY timestamp ASC
            ''', (user_id, season_start.isoformat()))
            rows = c.fetchall()

    if not rows:
        await interaction.response.send_message("No matches recorded this season.")
        return

    embed = Embed(
        title="Your Matches",
        description=f"**Season {season_number}** — {len(rows)} match{'es' if len(rows) != 1 else ''}\nOldest match shown first.",
        color=0x00ff99
    )

    for i, row in enumerate(rows):
        dt = datetime.datetime.fromisoformat(row['timestamp'])
        formatted = f"{dt.month}/{dt.day}/{dt.year % 100:02} {dt.strftime('%I:%M %p')}"
        emoji = "" if row['result'].lower() == "win" else ""
        match_number = i + 1
        embed.add_field(
            name=f"{emoji} {match_number}. {row['map']} [{row['result']}]",
            value=f"**Role:** {row['role']}, **Rank:** {row['rank']}, **Time:** {formatted}\n**Heroes:** {row['hero']}",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

# --- Slash Command: Help ---
@bot.slash_command(name="help", description="Show available commands and usage")
async def help_command(interaction: Interaction):
    embed = Embed(
        title="Bot Commands",
        description="See available slash commands:",
        color=0x3498db
    )

    embed.add_field(
        name="/record",
        value="Record a match with details like hero, role, map, etc.",
        inline=False
    )

    embed.add_field(
        name="/result",
        value="Show your recorded matches for the current season.",
        inline=False
    )

    embed.add_field(
        name="/help",
        value="Display this help message.",
        inline=False
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- Event: Bot Ready ---
@bot.event
async def on_ready():
    if not hasattr(bot, "synced"):
        await bot.sync_application_commands()
        bot.synced = True
    init_db()
    print(f"Bot online as {bot.user}")

# --- Run Bot ---
bot.run(os.getenv("BOT_TOKEN"))
