import nextcord
from nextcord.ext import commands
from nextcord import Interaction, SlashOption
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os
import datetime
import csv
import tempfile
from collections import Counter
from nextcord.ui import View, Button
from nextcord import Embed, ButtonStyle

load_dotenv()
intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- PostgreSQL Connection ---
def get_db_connection():
    return psycopg2.connect(
        os.getenv("DATABASE_URL"),
        cursor_factory=RealDictCursor
    )

# --- Create table if not exists ---
def init_db():
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

# --- Constants ---
SEASON_1_START = datetime.datetime(2022, 10, 4)
SEASON_DURATION_WEEKS = 9

ROLE_HEROES = { ... }  # same as before
GAMEMODE_MAPS = { ... }  # same as before
ALL_HEROES = sum(ROLE_HEROES.values(), [])
ALL_MAPS = [m for maps in GAMEMODE_MAPS.values() for m in maps]
RANK_TIERS = ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master", "Grandmaster", "Champion"]
VALID_RESULTS = ["Win", "Loss"]

class SettingsView(View): ...  # unchanged

@bot.slash_command(name="settings", description="Configure your personal preferences")
async def settings(interaction: Interaction): ...

@bot.listen("on_interaction")
async def on_button_click(interaction: Interaction):
    if interaction.type != nextcord.InteractionType.component:
        return

    custom_id = interaction.data.get("custom_id")
    if custom_id == "export_data":
        user_id = interaction.user.id
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute('''
                    SELECT hero, role, gamemode, map, rank, result, timestamp FROM matches
                    WHERE user_id = %s
                    ORDER BY timestamp DESC
                ''', (user_id,))
                rows = c.fetchall()

        if not rows:
            await interaction.response.send_message("You have no recorded matches to export.", ephemeral=True)
            return

        with tempfile.NamedTemporaryFile(mode="w", newline="", delete=False, suffix=".csv") as tmp_file:
            writer = csv.writer(tmp_file)
            writer.writerow(["Hero", "Role", "Gamemode", "Map", "Rank", "Result", "Timestamp"])
            for row in rows:
                writer.writerow(row.values())
            temp_file_path = tmp_file.name

        file_to_send = nextcord.File(temp_file_path, filename="match_history.csv")
        await interaction.response.send_message("Here is your exported match history:", file=file_to_send, ephemeral=True)

# Replace all other SQLite blocks with equivalent get_db_connection() + %s queries.
# For example, in /record, /result, /top_heroes, /clear, /delete_last

# Finally:
@bot.event
async def on_ready():
    if not hasattr(bot, "synced"):
        await bot.sync_application_commands()
        bot.synced = True
    init_db()
    print(f"✅ Bot online as {bot.user}")

bot.run(os.getenv("BOT_TOKEN"))
