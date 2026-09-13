import discord
from discord.ext import commands, tasks
import requests
import random
import sqlite3
import os
import threading
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta

# --- SERVEUR WEB (FLASK) ---
app = Flask(__name__)
CORS(app)

@app.route('/')
def keep_alive():
    return "Mon bot Pokémon est bien en ligne !"

# --- DICTIONNAIRE DE TRADUCTION ---
TRADUCTION_POKEMON = {
    "dracaufeu": "charizard", "reptincel": "charmeleon", "salameche": "charmander",
    "florizarre": "venusaur", "herbizarre": "ivysaur", "bulbizarre": "bulbasaur",
    "tortank": "blastoise", "carabaffe": "wartortle", "carapuce": "squirtle",
    "pikachu": "pikachu", "dracolosse": "dragonite", "dracaucor": "dragonair",
    "minidraco": "dratini", "mewtwo": "mewtwo", "mew": "mew",
}

def get_api_name(nom_francais):
    return TRADUCTION_POKEMON.get(nom_francais.lower().strip(), nom_francais.lower().strip())

# --- BASE DE DONNÉES ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'pokemon_bot.db')

conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS pokedex (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        pokemon_name TEXT,
        is_shiny INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        xp INTEGER DEFAULT 0
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        money INTEGER DEFAULT 100,
        last_daily TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT
    )
''')
conn.commit()

# Vérification et ajout des colonnes d'inventaire, histoire et badges
nouvelles_colonnes = [
    ("pokeball", "INTEGER DEFAULT 5"), ("superball", "INTEGER DEFAULT 0"),
    ("hyperball", "INTEGER DEFAULT 0"), ("masterball", "INTEGER DEFAULT 0"),
    ("potion", "INTEGER DEFAULT 0"), ("rappel", "INTEGER DEFAULT 0"),
    ("bonbon", "INTEGER DEFAULT 0"),
    ("bio", "TEXT DEFAULT 'Aucune histoire écrite pour l''instant...'"),
    ("badges", "TEXT DEFAULT '🏮 Novice du Sanctuaire'")
]
cursor.execute("PRAGMA table_info(users)")
colonnes_existantes = [col[1] for col in cursor.fetchall()]
for col_nom, col_type in nouvelles_colonnes:
    if col_nom not in colonnes_existantes:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {col_nom} {col_type}")
conn.commit()

# --- CONFIGURATION DISCORD ---
intents = discord.Intents.default()
intents.message_content = True
discord_bot = commands.Bot(command_prefix="!", intents=intents)

pokemon_sauvage = None
derniere_capture_anim = None

def get_or_create_user(user_id):
    u_id = str(user_id)
    cursor.execute("SELECT pokeball, superball, hyperball, masterball, potion, rappel, bonbon, money, last_daily, bio, badges FROM users WHERE user_id = ?", (u_id,))
    data = cursor.fetchone()
    if not data:
        cursor.execute("INSERT INTO users (user_id, pokeball, superball, hyperball, masterball, potion, rappel, bonbon, money, last_daily, bio, badges) VALUES (?, 5, 0, 0, 0, 0, 0, 0, 100, NULL, 'Aucune histoire écrite pour l''instant...', '🏮 Novice du Sanctuaire')", (u_id,))
        conn.commit()
        return {"pokeball": 5, "superball": 0, "hyperball": 0, "masterball": 0, "potion": 0, "rappel": 0, "bonbon": 0, "money": 100, "last_daily": None, "bio": "Aucune histoire écrite pour l'instant...", "badges": "🏮 Novice du Sanctuaire"}
    return {"pokeball": data[0], "superball": data[1], "hyperball": data[2], "masterball": data[3], "potion": data[4], "rappel": data[5], "bonbon": data[6], "money": data[7], "last_daily": data[8], "bio": data[9], "badges": data[10]}

def get_spawn_channel_id():
    cursor.execute("SELECT value FROM config WHERE key = 'spawn_channel_id'")
    data = cursor.fetchone()
    return int(data[0]) if data and data[0] else None

def get_spawn_interval():
    cursor.execute("SELECT value FROM config WHERE key = 'spawn_interval_minutes'")
    data = cursor.fetchone()
    return float(data[0]) if data and data[0] else 2.0

# --- VUE INTERACTIVE POUR LA CAPTURE PAR BOUTONS ---
class CaptureView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Pokéball", style=discord.ButtonStyle.danger, emoji="🔴")
    async def btn_pokeball(self, interaction: discord.Interaction, button: discord.ui.Button):
        await tenter_capture(interaction, "pokeball")

    @discord.ui.button(label="Superball", style=discord.ButtonStyle.primary, emoji="🔵")
    async def btn_superball(self, interaction: discord.Interaction, button: discord.ui.Button):
        await tenter_capture(interaction, "superball")

    @discord.ui.button(label="Hyperball", style=discord.ButtonStyle.secondary, emoji="🟣")
    async def btn_hyperball(self, interaction: discord.Interaction, button: discord.ui.Button):
        await tenter_capture(interaction, "hyperball")

    @discord.ui.button(label="Masterball", style=discord.ButtonStyle.success, emoji="🟡")
    async def btn_masterball(self, interaction: discord.Interaction, button: discord.ui.Button):
        await tenter_capture(interaction, "masterball")

async def tenter_capture(interaction: discord.Interaction, ball: str):
    global pokemon_sauvage, derniere_capture_anim
    
    # Évite l'erreur des 3 secondes de Discord
    await interaction.response.defer(ephemeral=True)

    if pokemon_sauvage is None:
        await interaction.followup.send("Ce Pokémon a déjà disparu ou a été capturé !", ephemeral=True)
        return

    user_data = get_or_create_user(str(interaction.user.id))
    taux_et_noms = {"pokeball": (70, "Pokéball"), "superball": (85, "Superball"), "hyperball": (95, "Hyperball"), "masterball": (100, "Masterball")}

    if user_data[ball] <= 0:
        await interaction.followup.send(f"Tu n'as plus de {taux_et_noms[ball][1]} dans ton inventaire !", ephemeral=True)
        return

    derniere_capture_anim = ball
    cursor.execute(f"UPDATE users SET {ball} = {ball} - 1 WHERE user_id = ?", (str(interaction.user.id),))
    
    if random.randint(1, 100) <= taux_et_noms[ball][0]:
        poke, shiny = pokemon_sauvage["name"], pokemon_sauvage["is_shiny"]
        pokemon_sauvage = None
        cursor.execute("INSERT INTO pokedex (user_id, pokemon_name, is_shiny, level, xp) VALUES (?, ?, ?, 1, 0)", (str(interaction.user.id), poke, 1 if shiny else 0))
        cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (200 if shiny else 50, str(interaction.user.id)))
        
        # Attribution automatique de badges selon les exploits
        cursor.execute("SELECT COUNT(*) FROM pokedex WHERE user_id = ?", (str(interaction.user.id),))
        total_captures = cursor.fetchone()[0]
        
        current_badges = user_data["badges"]
        if shiny and "🌸 Chasseur de Shiny" not in current_badges:
            current_badges += " | 🌸 Chasseur de Shiny"
        if total_captures >= 10 and "⛩️ Gardien des Esprits" not in current_badges:
            current_badges += " | ⛩️ Gardien des Esprits"
            
        cursor.execute("UPDATE users SET badges = ? WHERE user_id = ?", (current_badges, str(interaction.user.id)))
        conn.commit()
        await interaction.followup.send(f"🌸 **{interaction.user.display_name}** a capturé avec succès **{poke}** {'✨' in shiny and '✨' or (shiny and '✨' or '')} !")
    else:
        conn.commit()
        await interaction.followup.send(f"💨 {interaction.user.mention} a raté sa capture ! L'esprit s'est échappé...", ephemeral=True)

async def apparaitre_pokemon(channel):
    global pokemon_sauvage
    pokemon_id = random.randint(1, 1025)
    response = requests.get(f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}")
    
    if response.status_code == 200:
        data = response.json()
        name = data['name'].capitalize()
        is_shiny = random.randint(1, 50) == 1
        height = data['height'] / 10.0
        weight = data['weight'] / 10.0
        types = " / ".join([t['type']['name'].capitalize() for t in data['types']])
        image_url = data['sprites']['other']['official-artwork']['front_shiny' if is_shiny else 'front_default'] or data['sprites']['front_default']

        if is_shiny:
            titre = "🌸✨ ─── [ ⛩️ SANCTUAIRE SAKURA (SHINY) ⛩️ ] ─── ✨🌸"
            description = f"Un esprit divin rare est apparu !\n🌸 **{name} Shiny** ✨\n📏 {height}m | ⚖️ {weight}kg | 🔮 {types}\n\n*Clique sur un bouton ci-dessous pour lancer une Ball !*"
            couleur = 0xFFB7C5
        else:
            titre = "🌸 ─── [ ⛩️ JARDIN DES SAKURAS ⛩️ ] ─── 🌸"
            description = f"Un esprit sauvage émerge des cerisiers...\n**{name}**\n📏 {height}m | ⚖️ {weight}kg | 🔮 {types}\n\n*Clique sur un bouton ci-dessous pour tenter la capture !*"
            couleur = 0xFFC0CB

        pokemon_sauvage = {"name": name, "is_shiny": is_shiny, "image_url": image_url}
        embed = discord.Embed(title=titre, description=description, color=couleur)
        embed.set_image(url=image_url)
        embed.set_footer(text="🏮 Voie des Esprits • Utilise les boutons !")
        
        view = CaptureView()
        await channel.send(embed=embed, view=view)

@tasks.loop(minutes=2.0)
async def boucle_spawn():
    channel_id = get_spawn_channel_id()
    if channel_id:
        channel = discord_bot.get_channel(channel_id)
        if channel:
            await apparaitre_pokemon(channel)

@boucle_spawn.before_loop
async def avant_boucle_spawn():
    await discord_bot.wait_until_ready()
    boucle_spawn.change_interval(minutes=get_spawn_interval())

@discord_bot.event
async def on_ready():
    print(f"Bot connecté en tant que {discord_bot.user.name} 🌸")
    if not boucle_spawn.is_running():
        boucle_spawn.start()

# --- COMMANDES ADMIN ---
@discord_bot.command()
@commands.has_permissions(administrator=True)
async def setchannel(ctx, channel: discord.TextChannel = None):
    target = channel or ctx.channel
    cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('spawn_channel_id', ?)", (str(target.id),))
    conn.commit()
    await ctx.send(f"🌸 Salon de spawn défini sur {target.mention} !")

@discord_bot.command(name="pop")
@commands.has_permissions(administrator=True)
async def pop_cmd(ctx):
    await apparaitre_pokemon(ctx.channel)
    await ctx.send("🌸 [ADMIN] Apparition forcée !")

# --- COMMANDES JOUEURS & NOUVELLES FONCTIONNALITÉS ---

@discord_bot.command()
async def profil(ctx, member: discord.Member = None):
    target = member or ctx.author
    u_data = get_or_create_user(str(target.id))
    cursor.execute("SELECT COUNT(*), SUM(level) FROM pokedex WHERE user_id = ?", (str(target.id),))
    res = cursor.fetchone()
    nb_pokes, total_lvl = res[0] or 0, res[1] or 0

    embed = discord.Embed(title=f"⛩️ Profil de {target.display_name} ⛩️", color=0xFFB7C5)
    embed.add_field(name="💰 Argent", value=f"{u_data['money']}$", inline=True)
    embed.add_field(name="📖 Esprits", value=f"{nb_pokes} (Niveau cumulé: {total_lvl})", inline=True)
    embed.add_field(name="🏆 Badges du Clan", value=u_data['badges'], inline=False)
    embed.add_field(name="📜 Histoire du Personnage", value=u_data['bio'], inline=False)
    embed.add_field(name="🎒 Inventaire", value=f"🔴 x{u_data['pokeball']} | 🔵 x{u_data['superball']} | 🟣 x{u_data['hyperball']} | 🟡 x{u_data['masterball']}\n🍬 Bonbons: {u_data['bonbon']} | 🧪 Potions: {u_data['potion']}", inline=False)
    await ctx.send(embed=embed)

@discord_bot.command()
async def histoire(ctx, *, texte: str = None):
    """Permet de définir ou modifier l'histoire de son personnage"""
    u_id = str(ctx.author.id)
    get_or_create_user(u_id)
    
    if not texte:
        u_data = get_or_create_user(u_id)
        embed = discord.Embed(title=f"📜 Histoire de {ctx.author.display_name}", description=u_data['bio'], color=0xFFB7C5)
        embed.set_footer(text="Pour modifier ton histoire, tape : !histoire <ton texte>")
        await ctx.send(embed=embed)
        return

    if len(texte) > 500:
        await ctx.send("🌸 Ton histoire est trop longue ! Maximum 500 caractères.")
        return

    cursor.execute("UPDATE users SET bio = ? WHERE user_id = ?", (texte, u_id))
    conn.commit()
    await ctx.send(f"🌸 {ctx.author.mention}, l'histoire de ton personnage a été gravée dans les registres du clan !")

# --- SYSTÈME DE PAGINATION POUR LE POKÉDEX (ILLIMITÉ) ---
class PokedexPaginator(discord.ui.View):
    def __init__(self, pokemons, member_name):
        super().__init__(timeout=180)
        self.pokemons = pokemons
        self.member_name = member_name
        self.current_page = 0
        self.items_per_page = 10
        self.max_pages = (len(pokemons) - 1) // self.items_per_page
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.max_pages

    def create_embed(self):
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        page_items = self.pokemons[start:end]

        embed = discord.Embed(
            title=f"🌸 Clan de {self.member_name} (Page {self.current_page + 1}/{self.max_pages + 1})",
            description="Voici tous les esprits capturés par le dresseur :",
            color=0xFFC0CB
        )

        description_lines = []
        for pid, name, shiny, lvl, xp in page_items:
            shiny_emoji = "✨" if shiny else ""
            description_lines.append(f"• **ID {pid}** | **Niv.{lvl}** - {name} {shiny_emoji} *(XP: {xp}/{lvl * 100})*")

        embed.add_field(name="📜 Liste des Esprits", value="\n".join(description_lines), inline=False)
        embed.set_footer(text=f"Total d'esprits : {len(self.pokemons)}")
        return embed

    @discord.ui.button(label="◀️ Précédent", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Suivant ▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.max_pages:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

@discord_bot.command()
async def inv(ctx, member: discord.Member = None):
    target = member or ctx.author
    cursor.execute("SELECT id, pokemon_name, is_shiny, level, xp FROM pokedex WHERE user_id = ? ORDER BY id DESC", (str(target.id),))
    pokemons = cursor.fetchall()
    
    if not pokemons:
        await ctx.send(f"🌸 {target.mention} n'a aucun esprit dans son clan !")
        return
        
    view = PokedexPaginator(pokemons, target.display_name)
    await ctx.send(embed=view.create_embed(), view=view)

@discord_bot.command()
async def shop(ctx):
    embed = discord.Embed(title="⛩️ Boutique ⛩️", description="Utilise `!buy <article> [quantité]`", color=0xFFB7C5)
    embed.add_field(name="Articles", value="pokeball (100$) | superball (300$) | hyperball (600$) | masterball (2500$)\nbonbon (150$) | potion (100$)", inline=False)
    await ctx.send(embed=embed)

@discord_bot.command()
async def buy(ctx, article: str, quantite: int = 1):
    item = article.lower()
    prix = {"pokeball": 100, "superball": 300, "hyperball": 600, "masterball": 2500, "bonbon": 150, "potion": 100}
    if item not in prix:
        await ctx.send("Article inconnu !")
        return
    total = prix[item] * max(1, quantite)
    u = get_or_create_user(str(ctx.author.id))
    if u["money"] < total:
        await ctx.send(f"Fonds insuffisants ({total}$ requis).")
        return
    cursor.execute(f"UPDATE users SET money = money - ?, {item} = {item} + ? WHERE user_id = ?", (total, quantite, str(ctx.author.id)))
    conn.commit()
    await ctx.send(f"Achat réussi de {quantite}x {item} !")

@discord_bot.command()
async def use(ctx, objet: str, pokemon_id: int):
    obj = objet.lower()
    u_id = str(ctx.author.id)
    u = get_or_create_user(u_id)
    
    if obj == "bonbon":
        if u["bonbon"] <= 0:
            await ctx.send("Tu n'as pas de bonbon !")
            return
        cursor.execute("SELECT level, xp FROM pokedex WHERE id = ? AND user_id = ?", (pokemon_id, u_id))
        poke = cursor.fetchone()
        if not poke:
            await ctx.send("Cet esprit ne t'appartient pas.")
            return
        lvl, xp = poke
        xp += 50
        if xp >= lvl * 100:
            lvl += 1
            xp = 0
            msg = f"🍬 Bonbon utilisé ! Ton esprit monte au **niveau {lvl}** !"
        else:
            msg = f"🍬 Bonbon utilisé ! +50 XP."
        cursor.execute("UPDATE pokedex SET level = ?, xp = ? WHERE id = ?", (lvl, xp, pokemon_id))
        cursor.execute("UPDATE users SET bonbon = bonbon - 1 WHERE user_id = ?", (u_id,))
        conn.commit()
        await ctx.send(msg)
    else:
        await ctx.send("Objet non utilisable de cette façon.")

@discord_bot.command()
async def feed(ctx, pokemon_id: int):
    """Raccourci pour utiliser un bonbon"""
    ctx.invoke(use, objet="bonbon", pokemon_id=pokemon_id)

@discord_bot.command()
async def duel(ctx, opponent: discord.Member, mise: int = 50):
    if opponent == ctx.author or opponent.bot:
        keys = ["Tu ne peux pas te battre contre toi-même !"]
        await ctx.send(keys[0])
        return
    
    u1 = get_or_create_user(str(ctx.author.id))
    u2 = get_or_create_user(str(opponent.id))
    
    if u1["money"] < mise or u2["money"] < mise:
        await ctx.send("L'un des joueurs n'a pas assez d'argent pour cette mise !")
        return

    cursor.execute("SELECT SUM(level) FROM pokedex WHERE user_id = ?", (str(ctx.author.id),))
    score1 = (cursor.fetchone()[0] or 1) + random.randint(1, 20)
    cursor.execute("SELECT SUM(level) FROM pokedex WHERE user_id = ?", (str(opponent.id),))
    score2 = (cursor.fetchone()[0] or 1) + random.randint(1, 20)

    if score1 > score2:
        cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (mise, str(ctx.author.id)))
        cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (mise, str(opponent.id)))
        
        c_badges = u1["badges"]
        if "⚔️ Maître des Duels" not in c_badges:
            cursor.execute("UPDATE users SET badges = ? WHERE user_id = ?", (c_badges + " | ⚔️ Maître des Duels", str(ctx.author.id)))
            
        conn.commit()
        await ctx.send(f"⚔️ Duel remporté par {ctx.author.mention} face à {opponent.mention} ! Il remporte {mise}$ !")
    else:
        cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (mise, str(ctx.author.id)))
        cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (mise, str(opponent.id)))
        conn.commit()
        await ctx.send(f"⚔️ Victoire de {opponent.mention} face à {ctx.author.mention} ! Il remporte {mise}$ !")

@discord_bot.command()
async def trade(ctx, member: discord.Member, mon_poke_id: int, son_poke_id: int):
    # Échange simplifié entre deux joueurs
    await ctx.send(f"🤝 Système d'échange en cours de validation entre {ctx.author.mention} et {member.mention}...")

@discord_bot.command()
async def daily(ctx):
    u_id = str(ctx.author.id)
    u_data = get_or_create_user(u_id)
    now = datetime.now()
    if u_data["last_daily"]:
        if now - datetime.fromisoformat(u_data["last_daily"]) < timedelta(hours=24):
            await ctx.send("Offrande déjà récupérée aujourd'hui !")
            return
    cursor.execute("UPDATE users SET money = money + 150, pokeball = pokeball + 3, bonbon = bonbon + 1, last_daily = ? WHERE user_id = ?", (now.isoformat(), u_id))
    conn.commit()
    await ctx.send("🌸 Récompense journalière : 150$, 3 Pokéballs et 1 Bonbon !")

@discord_bot.command()
async def top(ctx):
    cursor.execute("SELECT user_id, money FROM users ORDER BY money DESC LIMIT 5")
    top_data = cursor.fetchall()
    desc = "\n".join([f"<@{u[0]}> — {u[1]}$" for u in top_data])
    embed = discord.Embed(title="⛩️ Classement des Richesses ⛩️", description=desc or "Aucun", color=0xFFB7C5)
    await ctx.send(embed=embed)

# Routes Flask
@app.route('/current-pokemon')
def current_pokemon():
    global pokemon_sauvage, derniere_capture_anim
    anim = bool(derniere_capture_anim)
    derniere_capture_anim = None
    return jsonify({**(pokemon_sauvage or {"name": None}), "anim_capture": anim})

def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False, use_reloader=False)

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    discord_bot.run(os.getenv('DISCORD_TOKEN'))
