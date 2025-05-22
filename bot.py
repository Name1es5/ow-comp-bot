import nextcord
from nextcord.ext import commands
from nextcord import Interaction
from nextcord.ui import Select, View
import sqlite3
from dotenv import load_dotenv
import os
import datetime

load_dotenv()

intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Create DB and Table ---
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

# --- Hero list per role ---
ROLE_HEROES = {
    "Tank": ["Doomfist", "D.Va", "Ramattra", "Reinhardt", "Roadhog", "Sigma", "Winston", "Zarya"],
    "DPS": [
        "Ashe", "Bastion", "Cassidy", "Echo", "Freja", "Genji", "Hanzo", "Junkrat", "Mei",
        "Pharah", "Reaper", "Sojourn", "Soldier: 76", "Sombra", "Symmetra",
        "Torbjörn", "Tracer", "Venture", "Widowmaker"
    ],
    "Support": [
        "Ana", "Baptiste", "Brigitte", "Illari", "Kiriko",
        "Lifeweaver", "Lucio", "Mercy", "Moira", "Zenyatta"
    ]
}

# --- Gamemodes & Maps ---
GAMEMODE_MAPS = {
    "Control": ["Antarctic Peninsula", "Busan", "Ilios", "Lijiang Tower", "Nepal", "Oasis", "Samoa"],
    "Escort": ["Circuit Royal", "Dorado", "Havana", "Junkertown", "Rialto", "Route 66", "Shambali Monastery", "Watchpoint: Gibraltar"],
    "Push": ["New Queen Street", "Colosseo", "Esperança", "Runasapi"],
    "Hybrid": ["Blizzard World", "Eichenwalde", "Hollywood", "King's Row", "Midtown", "Numbani", "Paraíso"],
    "Flashpoint": ["New Junk City", "Suravasa"]
}

# --- UI Dropdowns ---
class RoleSelect(Select):
    def __init__(self):
        options = [nextcord.SelectOption(label=role) for role in ROLE_HEROES]
        super().__init__(placeholder="Select your role", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        role = self.values[0]
        await interaction.response.send_message(
            f"You selected **{role}**. Now pick one or more heroes.",
            view=HeroView(role),
            ephemeral=True
        )

class HeroSelect(Select):
    def __init__(self, role):
        options = [nextcord.SelectOption(label=hero) for hero in ROLE_HEROES[role]]
        super().__init__(placeholder="Select hero(es)", min_values=1, max_values=len(options), options=options)
        self.role = role

    async def callback(self, interaction: Interaction):
        heroes = self.values  # list of selected heroes
        await interaction.response.send_message(
            f"Heroes selected: {', '.join(heroes)}\nNow select a game mode:",
            view=GamemodeView(self.role, heroes),
            ephemeral=True
        )

class GamemodeSelect(Select):
    def __init__(self, role, heroes):
        options = [nextcord.SelectOption(label=mode) for mode in GAMEMODE_MAPS]
        super().__init__(placeholder="Select game mode", min_values=1, max_values=1, options=options)
        self.role = role
        self.heroes = heroes

    async def callback(self, interaction: Interaction):
        mode = self.values[0]
        await interaction.response.send_message(
            f"Game mode: **{mode}**\nNow pick a map:",
            view=MapView(self.role, self.heroes, mode),
            ephemeral=True
        )

class MapSelect(Select):
    def __init__(self, role, heroes, mode):
        options = [nextcord.SelectOption(label=m) for m in GAMEMODE_MAPS[mode]]
        super().__init__(placeholder="Select map", min_values=1, max_values=1, options=options)
        self.role = role
        self.heroes = heroes
        self.mode = mode

    async def callback(self, interaction: Interaction):
        map_ = self.values[0]
        await interaction.response.send_message(
            f"Map: **{map_}**\nNow select result:",
            view=ResultView(self.role, self.heroes, map_),
            ephemeral=True
        )

class ResultSelect(Select):
    def __init__(self, role, heroes, map_):
        options = [nextcord.SelectOption(label="Win"), nextcord.SelectOption(label="Loss")]
        super().__init__(placeholder="Select result", min_values=1, max_values=1, options=options)
        self.role = role
        self.heroes = heroes
        self.map_ = map_

    async def callback(self, interaction: Interaction):

        result = self.values[0]
        await interaction.response.send_message("Now enter your **rank**:", ephemeral=True)

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", timeout=60.0, check=check)
            rank = msg.content.strip()
            user_id = interaction.user.id
            joined_heroes = ", ".join(self.heroes)
            timestamp = datetime.datetime.now().isoformat()  # generate fresh timestamp

            with sqlite3.connect("matches.db") as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO matches (user_id, hero, role, map, rank, result, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_id, joined_heroes, self.role, self.map_, rank, result, timestamp)
                )
                conn.commit()

            await interaction.followup.send(" Match recorded.", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(" Timed out or error occurred.", ephemeral=True)
            print(e)


# --- View Classes ---
class RoleView(View):
    def __init__(self):
        super().__init__()
        self.add_item(RoleSelect())

class HeroView(View):
    def __init__(self, role):
        super().__init__()
        self.add_item(HeroSelect(role))

class GamemodeView(View):
    def __init__(self, role, heroes):
        super().__init__()
        self.add_item(GamemodeSelect(role, heroes))

class MapView(View):
    def __init__(self, role, heroes, mode):
        super().__init__()
        self.add_item(MapSelect(role, heroes, mode))

class ResultView(View):
    def __init__(self, role, heroes, map_):
        super().__init__()
        self.add_item(ResultSelect(role, heroes, map_))

# --- Slash Commands ---

# --- Ping ---
@bot.slash_command(name="ping", description="Check if the bot is alive")
async def ping(interaction: Interaction):
    await interaction.response.send_message("🏓 Pong!", ephemeral=True)

# --- Record Match  ---
@bot.slash_command(name="record", description="Start match recording")
async def record(interaction: Interaction):
    await interaction.response.send_message("Choose your role:", view=RoleView(), ephemeral=True)

# --- Results ---
@bot.slash_command(name="result", description="Show your recorded matches")
async def result(interaction: Interaction):
    import datetime

    user_id = interaction.user.id
    with sqlite3.connect("matches.db") as conn:
        c = conn.cursor()
        c.execute("SELECT hero, role, map, rank, result, timestamp FROM matches WHERE user_id = ?", (user_id,))
        rows = c.fetchall()

    if not rows:
        await interaction.response.send_message("You have no recorded matches.", ephemeral=True)
        return

    embed = nextcord.Embed(
        title="Your Matches",
        description="Here are your most recent recorded matches:",
        color=0x00ff99
    )

    for hero, role, map_, rank, result, timestamp in rows:
        try:
            dt = datetime.datetime.fromisoformat(timestamp)
            formatted_time = dt.strftime("%b %d, %Y %I:%M %p")
        except:
            formatted_time = "Unknown"

        embed.add_field(
            name=f"{hero} ({role})",
            value=f"**Map:** {map_}\n**Rank:** {rank}\n**Result:** {result}\n**Submitted:** {formatted_time}",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

# --- Clear matches table ---
@bot.slash_command(name="clear", description="Delete all your recorded matches")
async def clear(interaction: Interaction):
    user_id = interaction.user.id
    with sqlite3.connect("matches.db") as conn:
        c = conn.cursor()
        c.execute("DELETE FROM matches WHERE user_id = ?", (user_id,))
        conn.commit()

    await interaction.response.send_message("🗑️ Your match history has been cleared.", ephemeral=True)

#--- Delete most recent match ---
@bot.slash_command(name="delete_last", description="Delete your most recently recorded match")
async def delete_last(interaction: Interaction):
    user_id = interaction.user.id

    with sqlite3.connect("matches.db") as conn:
        c = conn.cursor()
        # Select the most recent match by rowid (insert order)
        c.execute(
            "SELECT rowid, hero, map FROM matches WHERE user_id = ? ORDER BY rowid DESC LIMIT 1",
            (user_id,)
        )
        last_match = c.fetchone()

        if last_match is None:
            await interaction.response.send_message("❌ You have no recorded matches.", ephemeral=True)
            return

        rowid, hero, map_ = last_match
        c.execute("DELETE FROM matches WHERE rowid = ?", (rowid,))
        conn.commit()

    await interaction.response.send_message(
        f"🗑️ Deleted your last match: **{hero}** on **{map_}**", ephemeral=True
    )

@bot.event
async def on_ready():
    if not hasattr(bot, "synced"):
        await bot.sync_application_commands()
        bot.synced = True
    print(f"✅ Bot ready as {bot.user}")



# --- Run the bot ---
bot.run(os.getenv("BOT_TOKEN"))


