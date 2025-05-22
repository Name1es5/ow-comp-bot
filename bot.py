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

intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- PostgreSQL Connection ---
def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    print("DATABASE_URL =", db_url)  # ← This goes BEFORE raise

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

class SettingsView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Change Timezone", custom_id="change_timezone", style=ButtonStyle.primary))
        self.add_item(Button(label="Export Data", custom_id="export_data", style=ButtonStyle.success))
        self.add_item(Button(label="GitHub", url="https://github.com/your-repo", style=ButtonStyle.link))

@bot.slash_command(name="record", description="Record a match")
async def record(
    interaction: Interaction,
    role: str = SlashOption(name="role", description="Enter role (Tank, DPS, Support)", required=True),
    gamemode: str = SlashOption(name="gamemode", description="Enter gamemode", required=True,
        choices=list(GAMEMODE_MAPS.keys())),
    hero: str = SlashOption(name="hero", description="Enter hero name", required=True),
    map: str = SlashOption(name="map", description="Enter map name", required=True),
    rank: str = SlashOption(name="rank", description="Enter rank tier", required=True),
    modifier: int = SlashOption(name="modifier", description="Rank modifier (1-5)", required=True),
    result: str = SlashOption(name="result", description="Match result (Win/Loss)", required=True)
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

# --- Autocompletes ---
@record.on_autocomplete("role")
async def autocomplete_role(interaction: Interaction, input: str):
    return [r for r in ROLE_HEROES if input.lower() in r.lower()]

@record.on_autocomplete("hero")
async def autocomplete_hero(interaction: Interaction, input: str):
    role = None
    for option in interaction.data.get("options", []):
        if option["name"] == "role":
            role = option.get("value")
    hero_pool = ROLE_HEROES.get(role, ALL_HEROES)
    return [h for h in hero_pool if input.lower() in h.lower()][:25]

@record.on_autocomplete("gamemode")
async def autocomplete_gamemode(interaction: Interaction, input: str):
    return [g for g in GAMEMODE_MAPS if input.lower() in g.lower()][:25]

@record.on_autocomplete("map")
async def autocomplete_map(interaction: Interaction, input: str):
    gamemode = None
    for option in interaction.data.get("options", []):
        if option["name"] == "gamemode":
            gamemode = option.get("value")
    map_pool = GAMEMODE_MAPS.get(gamemode, ALL_MAPS)
    return [m for m in map_pool if input.lower() in m.lower()][:25]

@record.on_autocomplete("rank")
async def autocomplete_rank(interaction: Interaction, input: str):
    return [r for r in RANK_TIERS if input.lower() in r.lower()]

@record.on_autocomplete("modifier")
async def autocomplete_modifier(interaction: Interaction, input: str):
    return [str(i) for i in range(1, 6) if input in str(i)]

@record.on_autocomplete("result")
async def autocomplete_result(interaction: Interaction, input: str):
    return [r for r in VALID_RESULTS if input.lower() in r.lower()]

# --- Other Commands ---
@bot.slash_command(name="result", description="Show your recorded matches for the current season")
async def result(interaction: Interaction):
    user_id = interaction.user.id
    season_start = SEASON_1_START + datetime.timedelta(weeks=SEASON_DURATION_WEEKS * ((datetime.datetime.utcnow() - SEASON_1_START).days // (SEASON_DURATION_WEEKS * 7)))

    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute('''
                SELECT hero, role, map, rank, result, timestamp FROM matches
                WHERE user_id = %s AND timestamp >= %s
                ORDER BY timestamp DESC
            ''', (user_id, season_start.isoformat()))
            rows = c.fetchall()

    if not rows:
        await interaction.response.send_message("No matches recorded this season.", ephemeral=True)
        return

    embed = Embed(
        title="Your Matches",
        description=f"**Season** — {len(rows)} match{'es' if len(rows) != 1 else ''}\nMost recent shown first.",
        color=0x00ff99
    )

    for i, row in enumerate(rows):
        dt = datetime.datetime.fromisoformat(row['timestamp'])
        formatted = f"{dt.month}/{dt.day}/{dt.year % 100:02} {dt.strftime('%I:%M %p')}"
        embed.add_field(
            name=f"{i + 1}. {row['map']} [{row['result']}]",
            value=f"**Role:** {row['role']}, **Rank:** {row['rank']}, **Time:** {formatted}\n**Heroes:** {row['hero']}",
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.slash_command(name="top_heroes", description="Show your top 3 most played heroes")
async def top_heroes(interaction: Interaction):
    user_id = interaction.user.id
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT hero FROM matches WHERE user_id = %s", (user_id,))
            all_heroes = [row['hero'] for row in c.fetchall()]

    if not all_heroes:
        await interaction.response.send_message("No matches recorded.", ephemeral=True)
        return

    counter = Counter(all_heroes).most_common(3)
    total = sum(dict(counter).values())
    embed = Embed(title="Top 3 Most Played Heroes", color=0x00ff99)
    for hero, count in counter:
        percent = (count / total) * 100
        embed.add_field(name=hero, value=f"{count} games ({percent:.1f}%)", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.slash_command(name="clear", description="Delete all your recorded matches")
async def clear(interaction: Interaction):
    user_id = interaction.user.id
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("DELETE FROM matches WHERE user_id = %s", (user_id,))
            conn.commit()
    await interaction.response.send_message("Your match history has been cleared.", ephemeral=True)

@bot.slash_command(name="delete_last", description="Delete your most recent match")
async def delete_last(interaction: Interaction):
    user_id = interaction.user.id
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT timestamp FROM matches WHERE user_id = %s ORDER BY timestamp DESC LIMIT 1", (user_id,))
            row = c.fetchone()
            if row:
                c.execute("DELETE FROM matches WHERE user_id = %s AND timestamp = %s", (user_id, row['timestamp']))
                conn.commit()
                await interaction.response.send_message("Last match deleted.", ephemeral=True)
            else:
                await interaction.response.send_message("No matches to delete.", ephemeral=True)

@bot.event
async def on_ready():
    if not hasattr(bot, "synced"):
        await bot.sync_application_commands()
        bot.synced = True
    init_db()
    print(f"Bot online as {bot.user}")

bot.run(os.getenv("BOT_TOKEN"))
