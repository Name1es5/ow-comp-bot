import nextcord
from nextcord.ext import commands
from nextcord import Interaction
from nextcord.ui import Select, View
import sqlite3
from dotenv import load_dotenv
import os
import datetime
from collections import Counter

load_dotenv()

intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- DB Setup ---
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
ROLE_HEROES = {
    "Tank": ["Doomfist", "D.Va", "Ramattra", "Reinhardt", "Roadhog", "Sigma", "Winston", "Zarya"],
    "DPS": ["Ashe", "Bastion", "Cassidy", "Echo", "Freja", "Genji", "Hanzo", "Junkrat", "Mei", "Pharah", "Reaper", "Sojourn", "Soldier: 76", "Sombra", "Symmetra", "Torbjörn", "Tracer", "Venture", "Widowmaker"],
    "Support": ["Ana", "Baptiste", "Brigitte", "Illari", "Kiriko", "Lifeweaver", "Lucio", "Mercy", "Moira", "Zenyatta"]
}
GAMEMODE_MAPS = {
    "Control": [
        "Antarctic Peninsula",
        "Busan",
        "Ilios",
        "Lijiang Tower",
        "Nepal",
        "Oasis",
        "Samoa"
    ],
    "Escort": [
        "Circuit Royal",
        "Dorado",
        "Havana",
        "Junkertown",
        "Rialto",
        "Route 66",
        "Shambali Monastery",
        "Watchpoint: Gibraltar"
    ],
    "Push": [
        "Colosseo",
        "Esperança",
        "New Queen Street",
        "Runasapi"
    ],
    "Hybrid": [
        "Blizzard World",
        "Eichenwalde",
        "Hollywood",
        "King's Row",
        "Midtown",
        "Numbani",
        "Paraíso"
    ],
    "Flashpoint": [
        "New Junk City",
        "Suravasa"
    ]
}

RANK_TIERS = ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master", "Grandmaster", "Champion"]

CURRENT_SEASON = 16  # Update this manually when a new season starts


# --- UI Dropdowns ---
class RoleSelect(Select):
    def __init__(self):
        options = [nextcord.SelectOption(label=role) for role in ROLE_HEROES]
        super().__init__(placeholder="Select your role", min_values=1, max_values=1, options=options)
    async def callback(self, interaction: Interaction):
        role = self.values[0]
        await interaction.response.send_message("Now pick one or more heroes:", view=HeroView(role), ephemeral=True)

class HeroSelect(Select):
    def __init__(self, role):
        options = [nextcord.SelectOption(label=h) for h in ROLE_HEROES[role]]
        super().__init__(placeholder="Select heroes", min_values=1, max_values=len(options), options=options)
        self.role = role
    async def callback(self, interaction: Interaction):
        await interaction.response.send_message("Select game mode:", view=GamemodeView(self.role, self.values), ephemeral=True)

class GamemodeSelect(Select):
    def __init__(self, role, heroes):
        options = [nextcord.SelectOption(label=m) for m in GAMEMODE_MAPS]
        super().__init__(placeholder="Select game mode", min_values=1, max_values=1, options=options)
        self.role = role
        self.heroes = heroes
    async def callback(self, interaction: Interaction):
        await interaction.response.send_message("Select map:", view=MapView(self.role, self.heroes, self.values[0]), ephemeral=True)

class MapSelect(Select):
    def __init__(self, role, heroes, mode):
        options = [nextcord.SelectOption(label=m) for m in GAMEMODE_MAPS[mode]]
        super().__init__(placeholder="Select map", min_values=1, max_values=1, options=options)
        self.role = role
        self.heroes = heroes
        self.mode = mode
    async def callback(self, interaction: Interaction):
        await interaction.response.send_message("Select result:", view=ResultView(self.role, self.heroes, self.values[0]), ephemeral=True)

class ResultSelect(Select):
    def __init__(self, role, heroes, map_):
        options = [nextcord.SelectOption(label="Win"), nextcord.SelectOption(label="Loss")]
        super().__init__(placeholder="Select result", min_values=1, max_values=1, options=options)
        self.role = role
        self.heroes = heroes
        self.map_ = map_
    async def callback(self, interaction: Interaction):
        await interaction.response.send_message("Select your rank:", view=RankView(self.role, self.heroes, self.map_, self.values[0]), ephemeral=True)

class RankSelect(Select):
    def __init__(self, role, heroes, map_, result):
        options = [nextcord.SelectOption(label=r) for r in RANK_TIERS]
        super().__init__(placeholder="Select rank", min_values=1, max_values=1, options=options)
        self.role = role
        self.heroes = heroes
        self.map_ = map_
        self.result = result
    async def callback(self, interaction: Interaction):
        await interaction.response.send_message("Select rank modifier:", view=ModifierView(self.role, self.heroes, self.map_, self.result, self.values[0]), ephemeral=True)

class ModifierSelect(Select):
    def __init__(self, role, heroes, map_, result, rank):
        options = [nextcord.SelectOption(label=str(i)) for i in range(1, 6)]
        super().__init__(placeholder="Select modifier", min_values=1, max_values=1, options=options)
        self.role = role
        self.heroes = heroes
        self.map_ = map_
        self.result = result
        self.rank = rank
    async def callback(self, interaction: Interaction):
        rank_full = f"{self.rank} {self.values[0]}"
        joined_heroes = ", ".join(self.heroes)
        timestamp = datetime.datetime.now().isoformat()
        user_id = interaction.user.id

        with sqlite3.connect("matches.db") as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO matches (user_id, hero, role, map, rank, result, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, joined_heroes, self.role, self.map_, rank_full, self.result, timestamp)
            )
            conn.commit()

        await interaction.response.send_message("✅ Match recorded!", ephemeral=True)

# --- Views ---
class RoleView(View):
    def __init__(self):
        super().__init__()
        self.add_item(RoleSelect())

class HeroView(View):
    def __init__(self, r):
        super().__init__()
        self.add_item(HeroSelect(r))

class GamemodeView(View):
    def __init__(self, r, h):
        super().__init__()
        self.add_item(GamemodeSelect(r, h))

class MapView(View):
    def __init__(self, r, h, m):
        super().__init__()
        self.add_item(MapSelect(r, h, m))

class ResultView(View):
    def __init__(self, r, h, m):
        super().__init__()
        self.add_item(ResultSelect(r, h, m))

class RankView(View):
    def __init__(self, r, h, m, res):
        super().__init__()
        self.add_item(RankSelect(r, h, m, res))

class ModifierView(View):
    def __init__(self, r, h, m, res, rank):
        super().__init__()
        self.add_item(ModifierSelect(r, h, m, res, rank))

# --- Slash Commands ---

# --- Ping bot ---
@bot.slash_command(name="ping", description="Check if the bot is alive")
async def ping(interaction: Interaction):
    await interaction.response.send_message("🏓 Pong!")

# --- Record match ---
@bot.slash_command(name="record", description="Start match recording")
async def record(interaction: Interaction):
    await interaction.response.send_message("Choose your role:", view=RoleView(), ephemeral=True)


# --- Result table ---
@bot.slash_command(name="result", description="Show your recorded matches")
async def result(interaction: Interaction):
    user_id = interaction.user.id
    with sqlite3.connect("matches.db") as conn:
        c = conn.cursor()
        c.execute(
            "SELECT hero, role, map, rank, result, timestamp FROM matches WHERE user_id = ? ORDER BY rowid DESC",
            (user_id,)
        )
        rows = c.fetchall()

    if not rows:
        await interaction.response.send_message("No matches recorded.", ephemeral=True)
        return

    embed = nextcord.Embed(
        title="📊 Your Matches",
        description=f"**Season {CURRENT_SEASON}**\nMost recent match shown first.",
        color=0x00ff99
    )

    for i, (hero, role, map_, rank, result, ts) in enumerate(rows, start=1):
        try:
            dt = datetime.datetime.fromisoformat(ts)
            time_fmt = f"{dt.month}/{dt.day}/{dt.year % 100:02} {dt.strftime('%I:%M %p')}"
        except:
            time_fmt = "N/A"

        embed.add_field(
            name=f"{i}. {map_} [{result}]",
            value=f"**Role:** {role}\n**Rank:** {rank}\n**Time:** {time_fmt}\n**Heroes:** {hero}",
            inline=False
        )

    await interaction.response.send_message(embed=embed)





# --- Top Heroes played ---
@bot.slash_command(name="top_heroes", description="Show your top 3 most played heroes")
async def top_heroes(interaction: Interaction):
    user_id = interaction.user.id
    with sqlite3.connect("matches.db") as conn:
        c = conn.cursor()
        c.execute("SELECT hero FROM matches WHERE user_id = ?", (user_id,))
        all_heroes = [hero.strip() for row in c.fetchall() for hero in row[0].split(",")]

    if not all_heroes:
        await interaction.response.send_message("No matches recorded.", ephemeral=True)
        return

    counter = Counter(all_heroes).most_common(3)
    total = sum(dict(counter).values())

    embed = nextcord.Embed(title="Top 3 Most Played Heroes", color=0x00ff99)
    for hero, count in counter:
        percent = (count / total) * 100
        embed.add_field(name=hero, value=f"{count} games ({percent:.1f}%)", inline=False)

    await interaction.response.send_message(embed=embed)


# --- Clear table ---
@bot.slash_command(name="clear", description="Delete all your recorded matches")
async def clear(interaction: Interaction):
    with sqlite3.connect("matches.db") as conn:
        c = conn.cursor()
        c.execute("DELETE FROM matches WHERE user_id = ?", (interaction.user.id,))
        conn.commit()
    await interaction.response.send_message("🗑️ Match history cleared.", ephemeral=True)


# --- Delete last match ---
@bot.slash_command(name="delete_last", description="Delete your most recently recorded match")
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
    print(f"✅ Bot is online as {bot.user}")
    
# --- See all commands ---
@bot.slash_command(name="help", description="List all available commands and their descriptions")
async def help_command(interaction: Interaction):
    embed = nextcord.Embed(
        title="OW Comp Bot Commands",
        description="Here are the available commands:",
        color=0x00ff99
    )

    embed.add_field(name="/record", value="Start match recording.", inline=False)
    embed.add_field(name="/result", value="Show your recorded matches.", inline=False)
    embed.add_field(name="/top", value="Show your top 3 most played heroes.", inline=False)
    embed.add_field(name="/clear", value="Delete all your recorded matches.", inline=False)
    embed.add_field(name="/delete_last", value="Delete your most recently recorded match.", inline=False)
    embed.add_field(name="/ping", value="Check if the bot is alive.", inline=False)
    embed.add_field(name="/help", value="Show this help message.", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# --- Start Bot ---
bot.run(os.getenv("BOT_TOKEN"))
