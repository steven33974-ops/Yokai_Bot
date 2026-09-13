import discord
from discord.ext import commands, tasks
import requests
import random
import sqlite3
import os
import asyncio
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

# --- TABLES POUR LES CLANS, ÉQUIPES & QUÊTES ---
cursor.execute('''
    CREATE TABLE IF NOT EXISTS equipes (
        user_id TEXT PRIMARY KEY,
        yokai1 TEXT,
        yokai2 TEXT,
        yokai3 TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS clans (
        nom_clan TEXT PRIMARY KEY,
        leader TEXT,
        niveau_village INTEGER DEFAULT 1,
        points_village INTEGER DEFAULT 0
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS clan_membres (
        user_id TEXT PRIMARY KEY,
        nom_clan TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS quetes (
        user_id TEXT,
        type_quete TEXT,
        objectif INTEGER,
        progression INTEGER DEFAULT 0,
        terminee INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, type_quete)
    )
''')

conn.commit()

# Vérification et ajout des colonnes d'inventaire, histoire, badges et habitation
nouvelles_colonnes = [
    ("pokeball", "INTEGER DEFAULT 5"), ("superball", "INTEGER DEFAULT 0"),
    ("hyperball", "INTEGER DEFAULT 0"), ("masterball", "INTEGER DEFAULT 0"),
    ("potion", "INTEGER DEFAULT 0"), ("rappel", "INTEGER DEFAULT 0"),
    ("bonbon", "INTEGER DEFAULT 0"),
    ("bio", "TEXT DEFAULT 'Aucune histoire écrite pour l''instant...'"),
    ("badges", "TEXT DEFAULT '🏮 Novice du Sanctuaire'"),
    ("niv_habitation", "INTEGER DEFAULT 1"),
    ("evo_habitation", "INTEGER DEFAULT 0"),
    ("titre_habitation", "TEXT DEFAULT 'Chambre d''apprenti'")
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
    cursor.execute("SELECT pokeball, superball, hyperball, masterball, potion, rappel, bonbon, money, last_daily, bio, badges, niv_habitation, evo_habitation, titre_habitation FROM users WHERE user_id = ?", (u_id,))
    data = cursor.fetchone()
    if not data:
        cursor.execute("INSERT INTO users (user_id, pokeball, superball, hyperball, masterball, potion, rappel, bonbon, money, last_daily, bio, badges, niv_habitation, evo_habitation, titre_habitation) VALUES (?, 5, 0, 0, 0, 0, 0, 0, 100, NULL, 'Aucune histoire écrite pour l''instant...', '🏮 Novice du Sanctuaire', 1, 0, 'Chambre d''apprenti')", (u_id,))
        conn.commit()
        return {"pokeball": 5, "superball": 0, "hyperball": 0, "masterball": 0, "potion": 0, "rappel": 0, "bonbon": 0, "money": 100, "last_daily": None, "bio": "Aucune histoire écrite pour l'instant...", "badges": "🏮 Novice du Sanctuaire", "niv_habitation": 1, "evo_habitation": 0, "titre_habitation": "Chambre d'apprenti"}
    return {
        "pokeball": data[0], "superball": data[1], "hyperball": data[2], "masterball": data[3], 
        "potion": data[4], "rappel": data[5], "bonbon": data[6], "money": data[7], 
        "last_daily": data[8], "bio": data[9], "badges": data[10],
        "niv_habitation": data[11], "evo_habitation": data[12], "titre_habitation": data[13]
    }

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
        super().__init__(timeout=30)

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
    await interaction.response.defer(ephemeral=True)

    if pokemon_sauvage is None:
        await interaction.followup.send("Ce Pokémon a déjà disparu ou a été capturé !", ephemeral=True)
        return

    user_id_str = str(interaction.user.id)
    user_data = get_or_create_user(user_id_str)
    taux_et_noms = {"pokeball": (70, "Pokéball"), "superball": (85, "Superball"), "hyperball": (95, "Hyperball"), "masterball": (100, "Masterball")}

    if user_data[ball] <= 0:
        await interaction.followup.send(f"Tu n'as plus de {taux_et_noms[ball][1]} dans ton inventaire !", ephemeral=True)
        return

    derniere_capture_anim = ball
    cursor.execute(f"UPDATE users SET {ball} = {ball} - 1 WHERE user_id = ?", (user_id_str,))
    
    if random.randint(1, 100) <= taux_et_noms[ball][0]:
        poke, shiny = pokemon_sauvage["name"], pokemon_sauvage["is_shiny"]
        pokemon_sauvage = None
        cursor.execute("INSERT INTO pokedex (user_id, pokemon_name, is_shiny, level, xp) VALUES (?, ?, ?, 1, 0)", (user_id_str, poke, 1 if shiny else 0))
        cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (200 if shiny else 50, user_id_str))
        
        # Progression de la quête 'capture'
        cursor.execute("UPDATE quetes SET progression = MIN(objectif, progression + 1), terminee = CASE WHEN progression + 1 >= objectif THEN 1 ELSE 0 END WHERE user_id = ? AND type_quete = 'capture' AND terminee = 0", (user_id_str,))

        cursor.execute("SELECT COUNT(*) FROM pokedex WHERE user_id = ?", (user_id_str,))
        total_captures = cursor.fetchone()[0]
        
        current_badges = user_data["badges"]
        if shiny and "🌸 Chasseur de Shiny" not in current_badges:
            current_badges += " | 🌸 Chasseur de Shiny"
        if total_captures >= 10 and "⛩️ Gardien des Esprits" not in current_badges:
            current_badges += " | ⛩️ Gardien des Esprits"
            
        cursor.execute("UPDATE users SET badges = ? WHERE user_id = ?", (current_badges, user_id_str))
        conn.commit()
        await interaction.followup.send(f"🌸 **{interaction.user.display_name}** a capturé avec succès **{poke}** {'✨' if shiny else ''} !")
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
        embed.set_footer(text="🏮 Voie des Esprits • Tu as 30 secondes pour le capturer !")
        
        view = CaptureView()
        message = await channel.send(embed=embed, view=view)

        await asyncio.sleep(30)

        if pokemon_sauvage and pokemon_sauvage["name"] == name:
            pokemon_sauvage = None
            for item in view.children:
                item.disabled = True
            embed.description = f"💨 L'esprit **{name}** a pris peur et s'est enfui dans la brume..."
            embed.set_footer(text="⏰ Temps écoulé !")
            try:
                await message.edit(embed=embed, view=view)
            except:
                pass

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
async def adminhelp(ctx):
    embed = discord.Embed(title="⛩️ Grimoire Administrateur ⛩️", color=0xFFB7C5)
    embed.add_field(name="Configuration", value="`!setchannel` - Définit le salon de spawn\n`!settime <min>` - Règle l'intervalle de temps\n`!pop` - Force l'apparition d'un esprit", inline=False)
    embed.add_field(name="Gestion Joueurs", value="`!addmoney @user <montant>`\n`!removemoney @user <montant>`\n`!givepokemon @user <nom> [True]`\n`!resetplayer @user`", inline=False)
    await ctx.send(embed=embed)

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def setchannel(ctx, channel: discord.TextChannel = None):
    target = channel or ctx.channel
    cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('spawn_channel_id', ?)", (str(target.id),))
    conn.commit()
    await ctx.send(f"🌸 Salon de spawn défini sur {target.mention} !")

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def settime(ctx, minutes: float):
    if minutes < 0.5:
        await ctx.send("🌸 L'intervalle doit être d'au moins 0.5 minutes (30 secondes).")
        return
    cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('spawn_interval_minutes', ?)", (str(minutes),))
    conn.commit()
    boucle_spawn.change_interval(minutes=minutes)
    await ctx.send(f"🌸 L'intervalle d'apparition des esprits a été réglé sur **{minutes} minutes** !")

@discord_bot.command(name="pop")
@commands.has_permissions(administrator=True)
async def pop_cmd(ctx):
    await apparaitre_pokemon(ctx.channel)
    await ctx.send("🌸 [ADMIN] Apparition forcée !")

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def addmoney(ctx, member: discord.Member, montant: int):
    get_or_create_user(str(member.id))
    cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (montant, str(member.id)))
    conn.commit()
    await ctx.send(f"🌸 {montant}$ ont été ajoutés au compte de {member.mention}.")

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def removemoney(ctx, member: discord.Member, montant: int):
    get_or_create_user(str(member.id))
    cursor.execute("UPDATE users SET money = MAX(0, money - ?) WHERE user_id = ?", (montant, str(member.id)))
    conn.commit()
    await ctx.send(f"🌸 {montant}$ ont été retirés du compte de {member.mention}.")

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def givepokemon(ctx, member: discord.Member, nom: str, shiny_flag: bool = False):
    get_or_create_user(str(member.id))
    poke_nom_api = get_api_name(nom)
    resp = requests.get(f"https://pokeapi.co/api/v2/pokemon/{poke_nom_api}")
    if resp.status_code != 200:
        await ctx.send("🌸 Esprit introuvable dans le grand registre !")
        return
    data = resp.json()
    vrai_nom = data['name'].capitalize()
    cursor.execute("INSERT INTO pokedex (user_id, pokemon_name, is_shiny, level, xp) VALUES (?, ?, ?, 1, 0)", (str(member.id), vrai_nom, 1 if shiny_flag else 0))
    conn.commit()
    await ctx.send(f"🌸 L'esprit **{vrai_nom}** {'✨' if shiny_flag else ''} a été confié au clan de {member.mention} !")

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def resetplayer(ctx, member: discord.Member):
    u_id = str(member.id)
    cursor.execute("DELETE FROM users WHERE user_id = ?", (u_id,))
    cursor.execute("DELETE FROM pokedex WHERE user_id = ?", (u_id,))
    cursor.execute("DELETE FROM equipes WHERE user_id = ?", (u_id,))
    cursor.execute("DELETE FROM clan_membres WHERE user_id = ?", (u_id,))
    cursor.execute("DELETE FROM quetes WHERE user_id = ?", (u_id,))
    conn.commit()
    await ctx.send(f"🌸 Le profil et le clan de {member.mention} ont été réinitialisés par les esprits.")

# --- COMMANDES JOUEURS ---

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
    embed.add_field(name="🏠 Habitation", value=f"Niv.{u_data['niv_habitation']} - {u_data['titre_habitation']}", inline=False)
    embed.add_field(name="🏆 Badges du Clan", value=u_data['badges'], inline=False)
    embed.add_field(name="📜 Histoire du Personnage", value=u_data['bio'], inline=False)
    embed.add_field(name="🎒 Inventaire", value=f"🔴 x{u_data['pokeball']} | 🔵 x{u_data['superball']} | 🟣 x{u_data['hyperball']} | 🟡 x{u_data['masterball']}\n🍬 Bonbons: {u_data['bonbon']} | 🧪 Potions: {u_data['potion']}", inline=False)
    await ctx.send(embed=embed)

@discord_bot.command()
async def histoire(ctx, *, texte: str = None):
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

# --- SYSTÈME DE PAGINATION POUR LE POKÉDEX ---
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

@discord_bot.command(name="inv")
async def inv_cmd(ctx, member: discord.Member = None):
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
    ctx.invoke(use, objet="bonbon", pokemon_id=pokemon_id)

@discord_bot.command()
async def duel(ctx, opponent: discord.Member, mise: int = 50):
    if opponent == ctx.author or opponent.bot:
        await ctx.send("Tu ne peux pas te battre contre toi-même !")
        return
    u1_id = str(ctx.author.id)
    u2_id = str(opponent.id)
    u1 = get_or_create_user(u1_id)
    u2 = get_or_create_user(u2_id)
    if u1["money"] < mise or u2["money"] < mise:
        await ctx.send("L'un des joueurs n'a pas assez d'argent pour cette mise !")
        return
    cursor.execute("SELECT SUM(level) FROM pokedex WHERE user_id = ?", (u1_id,))
    score1 = (cursor.fetchone()[0] or 1) + random.randint(1, 20)
    cursor.execute("SELECT SUM(level) FROM pokedex WHERE user_id = ?", (u2_id,))
    score2 = (cursor.fetchone()[0] or 1) + random.randint(1, 20)

    if score1 > score2:
        cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (mise, u1_id))
        cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (mise, u2_id))
        # Progression quête duel pour le gagnant
        cursor.execute("UPDATE quetes SET progression = MIN(objectif, progression + 1), terminee = 1 WHERE user_id = ? AND type_quete = 'duel' AND terminee = 0", (u1_id,))
        
        c_badges = u1["badges"]
        if "⚔️ Maître des Duels" not in c_badges:
            cursor.execute("UPDATE users SET badges = ? WHERE user_id = ?", (c_badges + " | ⚔️ Maître des Duels", u1_id))
        conn.commit()
        await ctx.send(f"⚔️ Duel remporté par {ctx.author.mention} face à {opponent.mention} ! Il remporte {mise}$ !")
    else:
        cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (mise, u1_id))
        cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (mise, u2_id))
        conn.commit()
        await ctx.send(f"⚔️ Victoire de {opponent.mention} face à {ctx.author.mention} ! Il remporte {mise}$ !")

@discord_bot.command()
async def trade(ctx, member: discord.Member, mon_poke_id: int, son_poke_id: int):
    await ctx.send(f"🤝 Système d'échange en cours de validation entre {ctx.author.mention} and {member.mention}...")

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


# =====================================================================
# --- SYSTÈME DE QUÊTES ---
# =====================================================================

@discord_bot.command(name="quetes")
async def quetes_cmd(ctx):
    user_id = str(ctx.author.id)
    get_or_create_user(user_id)
    
    cursor.execute("SELECT type_quete, objectif, progression, terminee FROM quetes WHERE user_id = ?", (user_id,))
    quetes = cursor.fetchall()
    
    if not quetes:
        cursor.execute("INSERT OR REPLACE INTO quetes (user_id, type_quete, objectif, progression, terminee) VALUES (?, 'capture', 3, 0, 0)", (user_id,))
        cursor.execute("INSERT OR REPLACE INTO quetes (user_id, type_quete, objectif, progression, terminee) VALUES (?, 'duel', 1, 0, 0)", (user_id,))
        cursor.execute("INSERT OR REPLACE INTO quetes (user_id, type_quete, objectif, progression, terminee) VALUES (?, 'investir', 1, 0, 0)", (user_id,))
        conn.commit()
        
        cursor.execute("SELECT type_quete, objectif, progression, terminee FROM quetes WHERE user_id = ?", (user_id,))
        quetes = cursor.fetchall()

    embed = discord.Embed(
        title=f"📜 Quêtes de {ctx.author.display_name}",
        description="Accomplis ces missions pour gagner des récompenses exclusives !",
        color=0xFFB7C5
    )
    
    noms_quetes = {
        "capture": "chasser 3 esprits sauvages",
        "duel": "participer à 1 duel",
        "investir": "investir dans le village du clan"
    }

    for q_type, obj, prog, term in quetes:
        statut = "✅ Terminée" if term else f"En cours ({prog}/{obj})"
        desc_mission = noms_quetes.get(q_type, q_type)
        embed.add_field(name=f"🎯 Mission : {desc_mission}", value=f"Statut : **{statut}**", inline=False)

    embed.set_footer(text="Tape !recompense pour réclamer ton dû une fois la quête finie !")
    await ctx.send(embed=embed)


@discord_bot.command(name="recompense")
async def recompense_cmd(ctx):
    user_id = str(ctx.author.id)
    cursor.execute("SELECT type_quete, progression, objectif, terminee FROM quetes WHERE user_id = ? AND terminee = 1", (user_id,))
    terminees = cursor.fetchall()
    
    if not terminees:
        await ctx.send("🌸 Tu n'as aucune quête terminée en attente de récompense ! Tape `!quetes` pour voir tes missions.")
        return
        
    cursor.execute("UPDATE users SET money = money + 300, bonbon = bonbon + 2 WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM quetes WHERE user_id = ? AND terminee = 1", (user_id,))
    conn.commit()
    
    await ctx.send(f"🎉 Félicitations {ctx.author.mention} ! Tu as récupéré tes récompenses de quêtes : **300$ et 2 Bonbons** !")


# =====================================================================
# --- ÉQUIPES, CLANS & HABITATION ---
# =====================================================================

@discord_bot.command(name="equipe")
async def equipe_cmd(ctx, action: str = "voir", *, noms: str = None):
    user_id = str(ctx.author.id)
    action = action.lower()

    if action == "creer":
        if noms:
            parties = [p.strip() for p in noms.split(",")]
            y1 = parties[0] if len(parties) > 0 else "Aucun"
            y2 = parties[1] if len(parties) > 1 else "Aucun"
            y3 = parties[2] if len(parties) > 2 else "Aucun"
            
            cursor.execute("INSERT OR REPLACE INTO equipes (user_id, yokai1, yokai2, yokai3) VALUES (?, ?, ?, ?)", (user_id, y1, y2, y3))
            conn.commit()
            
            embed = discord.Embed(title="⚔️ Équipe enregistrée !", description="Voici ta nouvelle équipe prête pour le combat :", color=discord.Color.blue())
            embed.add_field(name="Membres", value=f"1. {y1}\n2. {y2}\n3. {y3}", inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("🌸 Pour créer ton équipe, tape : `!equipe creer Nom1, Nom2, Nom3`")

    elif action == "voir":
        cursor.execute("SELECT yokai1, yokai2, yokai3 FROM equipes WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            await ctx.send("Tu n'as pas encore d'équipe enregistrée ! Tape `!equipe creer Nom1, Nom2, Nom3` pour la définir.")
            return
        embed = discord.Embed(title=f"🛡️ Équipe de {ctx.author.name}", color=discord.Color.green())
        embed.add_field(name="Composition", value=f"1. {row[0]}\n2. {row[1]}\n3. {row[2]}", inline=False)
        await ctx.send(embed=embed)


@discord_bot.command(name="habitation")
async def habitation_cmd(ctx, action: str = "voir"):
    user_id = str(ctx.author.id)
    u_data = get_or_create_user(user_id)
    action = action.lower()

    if action == "voir":
        embed = discord.Embed(
            title=f"⛩️ Demeure de {ctx.author.display_name} ⛩️",
            description="C'est ici que votre vie privée de dresseur prend tout son sens. Suivez l'évolution de votre demeure personnelle, témoin de votre standing et de votre prospérité au sein du clan !",
            color=0xFFB7C5
        )
        embed.add_field(name="🏠 Titre & Standing", value=f"**{u_data['titre_habitation']}** (Niveau {u_data['niv_habitation']})", inline=False)
        embed.add_field(name="📊 Points d'évolution", value=f"{u_data['evo_habitation']} pts", inline=True)
        embed.add_field(name="💰 Pièces disponibles", value=f"{u_data['money']}$", inline=True)
        embed.set_footer(text="Tape !habitation ameliorer pour transcender votre foyer.")
        await ctx.send(embed=embed)

    elif action == "ameliorer":
        niv = u_data['niv_habitation']
        cout = niv * 500  
        if u_data['money'] < cout:
            await ctx.send(f"🌸 Il vous faut au moins **{cout}$** pour transcender votre foyer vers un nouveau palier !")
            return
        
        nouveau_niv = niv + 1
        nouveau_titre = "Base secrète" if nouveau_niv == 2 else "Sanctuaire personnel" if nouveau_niv >= 3 else u_data['titre_habitation']
        
        cursor.execute("UPDATE users SET money = money - ?, niv_habitation = ?, titre_habitation = ? WHERE user_id = ?", (cout, nouveau_niv, nouveau_titre, user_id))
        conn.commit()
        
        embed = discord.Embed(
            title="✨ Transcendance du Foyer ✨",
            description=f"Votre foyer a évolué vers le niveau **{nouveau_niv}** !\nNouveau titre acquis : **{nouveau_titre}**.",
            color=0xFFC0CB
        )
        await ctx.send(embed=embed)


@discord_bot.command(name="clan")
async def clan_cmd(ctx, action: str = "infos", *, arg: str = None):
    user_id = str(ctx.author.id)
    action = action.lower()

    if action == "creer":
        if not arg:
            await ctx.send("Tu dois indiquer le nom du clan que tu veux créer ! Ex: `!clan creer <nom>`")
            return
        cursor.execute("SELECT nom_clan FROM clans WHERE nom_clan = ?", (arg,))
        if cursor.fetchone():
            await ctx.send("Ce clan existe déjà !")
            return
        cursor.execute("SELECT nom_clan FROM clan_membres WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            await ctx.send("Tu fais déjà partie d'un clan ! Quitte-le d'abord.")
            return

        cursor.execute("INSERT INTO clans (nom_clan, leader, niveau_village, points_village) VALUES (?, ?, 1, 0)", (arg, user_id))
        cursor.execute("INSERT OR REPLACE INTO clan_membres (user_id, nom_clan) VALUES (?, ?)", (user_id, arg))
        conn.commit()
        await ctx.send(f"🎉 Le clan **{arg}** a été créé avec succès ! Tu en es le leader.")

    elif action == "rejoindre":
        if not arg:
            await ctx.send("Tu dois indiquer le nom du clan à rejoindre !")
            return
        cursor.execute("SELECT nom_clan FROM clans WHERE nom_clan = ?", (arg,))
        if not cursor.fetchone():
            await ctx.send("Ce clan n'existe pas.")
            return
        cursor.execute("SELECT nom_clan FROM clan_membres WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            await ctx.send("Tu fais déjà partie d'un clan !")
            return

        cursor.execute("INSERT OR REPLACE INTO clan_membres (user_id, nom_clan) VALUES (?, ?)", (user_id, arg))
        conn.commit()
        await ctx.send(f"🤝 Tu as rejoint le clan **{arg}** avec succès !")

    elif action == "infos":
        cursor.execute("SELECT nom_clan FROM clan_membres WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        if not res:
            await ctx.send("Tu ne fais partie d'aucun clan pour le moment.")
            return
        nom_clan = res[0]
        cursor.execute("SELECT leader, niveau_village FROM clans WHERE nom_clan = ?", (nom_clan,))
        c_data = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) FROM clan_membres WHERE nom_clan = ?", (nom_clan,))
        nb_membres = cursor.fetchone()[0]

        embed = discord.Embed(title=f"🏰 Clan : {nom_clan}", color=discord.Color.gold())
        embed.add_field(name="Leader", value=f"<@{c_data[0]}>", inline=True)
        embed.add_field(name="Membres", value=str(nb_membres), inline=True)
        embed.add_field(name="Niveau du Village", value=str(c_data[1]), inline=True)
        await ctx.send(embed=embed)

    elif action == "investir":
        montant = int(arg) if arg and arg.isdigit() else 50
        cursor.execute("SELECT nom_clan FROM clan_membres WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        if not res:
            await ctx.send("❌ Tu dois appartenir à un clan pour investir !")
            return
        nom_clan = res[0]

        cursor.execute("SELECT niveau_village, points_village FROM clans WHERE nom_clan = ?", (nom_clan,))
        c_data = cursor.fetchone()
        niveau, points = c_data[0], c_data[1] + montant
        
        palier_requis = niveau * 500
        message_lvl_up = ""
        if points >= palier_requis:
            niveau += 1
            points = 0
            message_lvl_up = f"\n\n🎊 **INCROYABLE !** Le village du clan est passé au **Niveau {niveau}** !"

        cursor.execute("UPDATE clans SET niveau_village = ?, points_village = ? WHERE nom_clan = ?", (niveau, points, nom_clan))
        
        # Progression quête investir
        cursor.execute("UPDATE quetes SET progression = MIN(objectif, progression + 1), terminee = 1 WHERE user_id = ? AND type_quete = 'investir' AND terminee = 0", (user_id,))
        conn.commit()

        embed = discord.Embed(
            title="📈 Investissement réussi !",
            description=f"Tu as investi **{montant} points** dans le village de ton clan (**{nom_clan}**).{message_lvl_up}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    elif action == "village":
        cursor.execute("SELECT nom_clan FROM clan_membres WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        if not res:
            await ctx.send("❌ Tu ne fais partie d'aucun clan !")
            return
        nom_clan = res[0]

        cursor.execute("SELECT niveau_village, points_village FROM clans WHERE nom_clan = ?", (nom_clan,))
        c_data = cursor.fetchone()
        niveau, points = c_data[0], c_data[1]
        palier_requis = niveau * 500

        if niveau == 1:
            titre_village = "🏕️ Petit Campement de Nomades"
        elif niveau == 2:
            titre_village = "🏡 Village Rénové et Fortifié"
        else:
            titre_village = "🏰 Grande Forteresse Imprenable"

        embed = discord.Embed(
            title=f"Village du Clan : {nom_clan}",
            description=f"Statut actuel : **{titre_village}**\nProgression : **{points} / {palier_requis} pts**",
            color=discord.Color.purple()
        )
        await ctx.send(embed=embed)

# --- LANCEMENT DU BOT ---
discord_bot.run("TON_TOKEN_SECRET")
