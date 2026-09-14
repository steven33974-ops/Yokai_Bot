import discord
from discord.ext import commands, tasks
import requests
import random
import sqlite3
import os
import asyncio
import threading
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta

# --- SERVEUR WEB (FLASK) ---
app = Flask(__name__)
CORS(app)

@app.route('/')
def keep_alive():
    return "Mon bot Yōkai est bien en ligne !"

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

# --- LOGIQUE COMMUNE DE CAPTURE ---
async def executer_capture(user_id_str, user_display_name, ball, channel_or_interaction, is_interaction=True):
    global pokemon_sauvage
    if pokemon_sauvage is None:
        msg = "Ce Pokémon a déjà disparu ou a été capturé !"
        if is_interaction:
            await channel_or_interaction.followup.send(msg, ephemeral=True)
        else:
            await channel_or_interaction.send(msg)
        return

    user_data = get_or_create_user(user_id_str)
    taux_et_noms = {"pokeball": (70, "Pokéball"), "superball": (85, "Superball"), "hyperball": (95, "Hyperball"), "masterball": (100, "Masterball")}

    if ball not in taux_et_noms:
        msg = "Type de Ball inconnu !"
        if is_interaction: await channel_or_interaction.followup.send(msg, ephemeral=True)
        else: await channel_or_interaction.send(msg)
        return

    if user_data[ball] <= 0:
        msg = f"Tu n'as plus de {taux_et_noms[ball][1]} dans ton inventaire !"
        if is_interaction: await channel_or_interaction.followup.send(msg, ephemeral=True)
        else: await channel_or_interaction.send(msg)
        return

    cursor.execute(f"UPDATE users SET {ball} = {ball} - 1 WHERE user_id = ?", (user_id_str,))
    
    if random.randint(1, 100) <= taux_et_noms[ball][0]:
        poke, shiny = pokemon_sauvage["name"], pokemon_sauvage["is_shiny"]
        pokemon_sauvage = None
        cursor.execute("INSERT INTO pokedex (user_id, pokemon_name, is_shiny, level, xp) VALUES (?, ?, ?, 1, 0)", (user_id_str, poke, 1 if shiny else 0))
        cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (200 if shiny else 50, user_id_str))
        
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
        
        success_msg = f"🌸 **{user_display_name}** a capturé avec succès **{poke}** {'✨' if shiny else ''} !"
        if is_interaction: await channel_or_interaction.followup.send(success_msg)
        else: await channel_or_interaction.send(success_msg)
    else:
        conn.commit()
        fail_msg = f"💨 {user_display_name} a raté sa capture ! L'esprit s'est échappé..."
        if is_interaction: await channel_or_interaction.followup.send(fail_msg, ephemeral=True)
        else: await channel_or_interaction.send(fail_msg)

# --- VUE INTERACTIVE POUR LA CAPTURE ---
class CaptureView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(label="Pokéball", style=discord.ButtonStyle.danger, emoji="🔴")
    async def btn_pokeball(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await executer_capture(str(interaction.user.id), interaction.user.display_name, "pokeball", interaction, True)

    @discord.ui.button(label="Superball", style=discord.ButtonStyle.primary, emoji="🔵")
    async def btn_superball(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await executer_capture(str(interaction.user.id), interaction.user.display_name, "superball", interaction, True)

    @discord.ui.button(label="Hyperball", style=discord.ButtonStyle.secondary, emoji="🟣")
    async def btn_hyperball(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await executer_capture(str(interaction.user.id), interaction.user.display_name, "hyperball", interaction, True)

    @discord.ui.button(label="Masterball", style=discord.ButtonStyle.success, emoji="🟡")
    async def btn_masterball(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await executer_capture(str(interaction.user.id), interaction.user.display_name, "masterball", interaction, True)

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
            description = f"Un esprit divin rare est apparu !\n🌸 **{name} Shiny** ✨\n📏 {height}m | ⚖️ {weight}kg | 🔮 {types}\n\n*Utilise `!capture <ball>` ou clique sur les boutons !*"
            couleur = 0xFFB7C5
        else:
            titre = "🌸 ─── [ ⛩️ JARDIN DES SAKURAS ⛩️ ] ─── 🌸"
            description = f"Un esprit sauvage émerge des cerisiers...\n**{name}**\n📏 {height}m | ⚖️ {weight}kg | 🔮 {types}\n\n*Utilise `!capture <ball>` ou clique sur les boutons !*"
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
    embed.add_field(name="Configuration", value="`!setchannel` - Définit le salon de spawn\n`!settime <min>` - Règle l'intervalle\n`!pop` - Force l'apparition", inline=False)
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
        await ctx.send("🌸 L'intervalle doit être d'au moins 0.5 minutes.")
        return
    cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('spawn_interval_minutes', ?)", (str(minutes),))
    conn.commit()
    boucle_spawn.change_interval(minutes=minutes)
    await ctx.send(f"🌸 Intervalle réglé sur **{minutes} minutes** !")

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
    await ctx.send(f"🌸 {montant}$ ajoutés au compte de {member.mention}.")

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def removemoney(ctx, member: discord.Member, montant: int):
    get_or_create_user(str(member.id))
    cursor.execute("UPDATE users SET money = MAX(0, money - ?) WHERE user_id = ?", (montant, str(member.id)))
    conn.commit()
    await ctx.send(f"🌸 {montant}$ retirés du compte de {member.mention}.")

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def givepokemon(ctx, member: discord.Member, nom: str, shiny_flag: bool = False):
    get_or_create_user(str(member.id))
    poke_nom_api = get_api_name(nom)
    resp = requests.get(f"https://pokeapi.co/api/v2/pokemon/{poke_nom_api}")
    if resp.status_code != 200:
        await ctx.send("🌸 Esprit introuvable !")
        return
    data = resp.json()
    vrai_nom = data['name'].capitalize()
    cursor.execute("INSERT INTO pokedex (user_id, pokemon_name, is_shiny, level, xp) VALUES (?, ?, ?, 1, 0)", (str(member.id), vrai_nom, 1 if shiny_flag else 0))
    conn.commit()
    await ctx.send(f"🌸 L'esprit **{vrai_nom}** {'✨' if shiny_flag else ''} a été offert à {member.mention} !")

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
    await ctx.send(f"🌸 Le profil de {member.mention} a été réinitialisé.")

# --- COMMANDES JOUEURS ---

@discord_bot.command()
async def capture(ctx, ball: str = "pokeball"):
    await executer_capture(str(ctx.author.id), ctx.author.display_name, ball.lower(), ctx, False)

@discord_bot.command()
async def profil(ctx, member: discord.Member = None):
    target = member or ctx.author
    u_data = get_or_create_user(str(target.id))
    cursor.execute("SELECT COUNT(*), SUM(level) FROM pokedex WHERE user_id = ?", (str(target.id),))
    res = cursor.fetchone()
    nb_pokes, total_lvl = res[0] or 0, res[1] or 0

    niv = u_data['niv_habitation']
    if niv <= 1000:
        image_maison = "METTONS_UN_LIEN_ICI"
    elif niv <= 5000:
        image_maison = "METTONS_UN_LIEN_ICI"
    elif niv < 10000:
        image_maison = "METTONS_UN_LIEN_ICI"
    else:
        image_maison = "METTONS_UN_LIEN_ICI"

    embed = discord.Embed(title=f"⛩️ Profil de {target.display_name} ⛩️", color=0xFFB7C5)
    embed.add_field(name="💰 Argent", value=f"{u_data['money']}$", inline=True)
    embed.add_field(name="📖 Esprits", value=f"{nb_pokes} (Niveau cumulé: {total_lvl})", inline=True)
    embed.add_field(name="🏠 Habitation", value=f"Niv.{niv}/10000 - {u_data['titre_habitation']}", inline=False)
    embed.add_field(name="🏆 Badges", value=u_data['badges'], inline=False)
    embed.add_field(name="📜 Histoire", value=u_data['bio'], inline=False)
    embed.add_field(name="🎒 Inventaire", value=f"🔴 x{u_data['pokeball']} | 🔵 x{u_data['superball']} | 🟣 x{u_data['hyperball']} | 🟡 x{u_data['masterball']}\n🍬 Bonbons: {u_data['bonbon']} | 🧪 Potions: {u_data['potion']}", inline=False)
    
    if image_maison.startswith("http"):
        embed.set_thumbnail(url=image_maison)

    await ctx.send(embed=embed)

@discord_bot.command()
async def histoire(ctx, *, texte: str = None):
    u_id = str(ctx.author.id)
    get_or_create_user(u_id)
    if not texte:
        u_data = get_or_create_user(u_id)
        embed = discord.Embed(title=f"📜 Histoire de {ctx.author.display_name}", description=u_data['bio'], color=0xFFB7C5)
        await ctx.send(embed=embed)
        return
    if len(texte) > 500:
        await ctx.send("🌸 Maximum 500 caractères.")
        return
    cursor.execute("UPDATE users SET bio = ? WHERE user_id = ?", (texte, u_id))
    conn.commit()
    await ctx.send(f"🌸 {ctx.author.mention}, ton histoire a été enregistrée !")

# --- PAGINATION POKÉDEX ---
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
            color=0xFFC0CB
        )
        description_lines = []
        for pid, name, shiny, lvl, xp in page_items:
            shiny_emoji = "✨" if shiny else ""
            description_lines.append(f"• **ID {pid}** | **Niv.{lvl}** - {name} {shiny_emoji} *(XP: {xp}/{lvl * 100})*")

        embed.add_field(name="📜 Esprits", value="\n".join(description_lines), inline=False)
        return embed

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
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
        await ctx.send(f"🌸 {target.mention} n'a aucun esprit !")
        return
    view = PokedexPaginator(pokemons, target.display_name)
    await ctx.send(embed=view.create_embed(), view=view)

@discord_bot.command()
async def shop(ctx):
    embed = discord.Embed(title="⛩️ Boutique ⛩️", color=0xFFB7C5)
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

# --- COMMANDE AMELIORER HABITATION ---
@discord_bot.command(name="ameliorer_maison")
async def ameliorer_maison(ctx):
    u_id = str(ctx.author.id)
    u_data = get_or_create_user(u_id)
    niv_actuel = u_data["niv_habitation"]

    if niv_actuel >= 10000:
        await ctx.send("🌸 Ton habitation est déjà au niveau maximum (10 000) ! C'est le Palais Céleste ultime.")
        return

    cout = niv_actuel * 5000 

    if u_data["money"] < cout:
        await ctx.send(f"🌸 Fonds insuffisants ! Il te faut **{cout}$** pour améliorer ton habitation au niveau {niv_actuel + 1}.")
        return

    nouveau_niv = niv_actuel + 1
    
    if nouveau_niv <= 1000:
        titre = "Sanctuaire de Brume"
        image_maison = "METTONS_UN_LIEN_ICI"
    elif nouveau_niv <= 5000:
        titre = "Demeure des Esprits Majeurs"
        image_maison = "METTONS_UN_LIEN_ICI"
    elif nouveau_niv < 10000:
        titre = "Palais Impérial des Cerisiers Éternels"
        image_maison = "METTONS_UN_LIEN_ICI"
    else:
        titre = "Palais Céleste Absolu des Yōkai"
        image_maison = "METTONS_UN_LIEN_ICI"

    cursor.execute("UPDATE users SET money = money - ?, niv_habitation = ?, titre_habitation = ? WHERE user_id = ?", (cout, nouveau_niv, titre, u_id))
    conn.commit()

    embed = discord.Embed(
        title="🌸 Évolution de l'Habitation 🌸",
        description=f"Félicitations {ctx.author.mention} ! Ton habitation est passée au **niveau {nouveau_niv}** !\n\n🏮 **Nouveau titre :** {titre}",
        color=0xFFB7C5
    )
    if image_maison.startswith("http"):
        embed.set_image(url=image_maison)

    await ctx.send(embed=embed)

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
async def trade(ctx, member: discord.Member, mon_poke_id: int, son_poke_id: int):
    await ctx.send(f"🤝 Échange en cours entre {ctx.author.mention} et {member.mention}...")

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


# --- COMBATS & DUELS ---
@discord_bot.command()
async def duel(ctx, opponent: discord.Member, mise: int = 50):
    if opponent == ctx.author or opponent.bot:
        await ctx.send("Duel impossible contre toi-même !")
        return
    u1_id = str(ctx.author.id)
    u2_id = str(opponent.id)
    u1 = get_or_create_user(u1_id)
    u2 = get_or_create_user(u2_id)
    if u1["money"] < mise or u2["money"] < mise:
        await ctx.send("Fonds insuffisants pour la mise !")
        return
    cursor.execute("SELECT SUM(level) FROM pokedex WHERE user_id = ?", (u1_id,))
    score1 = (cursor.fetchone()[0] or 1) + random.randint(1, 20)
    cursor.execute("SELECT SUM(level) FROM pokedex WHERE user_id = ?", (u2_id,))
    score2 = (cursor.fetchone()[0] or 1) + random.randint(1, 20)

    if score1 > score2:
        cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (mise, u1_id))
        cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (mise, u2_id))
        cursor.execute("UPDATE quetes SET progression = MIN(objectif, progression + 1), terminee = 1 WHERE user_id = ? AND type_quete = 'duel' AND terminee = 0", (u1_id,))
        conn.commit()
        await ctx.send(f"⚔️ Victoire de {ctx.author.mention} face à {opponent.mention} ! Il remporte {mise}$ !")
    else:
        cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (mise, u1_id))
        cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (mise, u2_id))
        conn.commit()
        await ctx.send(f"⚔️ Victoire de {opponent.mention} face à {ctx.author.mention} ! Il remporte {mise}$ !")

@discord_bot.command(name="ia")
async def ia_cmd(ctx):
    u_id = str(ctx.author.id)
    get_or_create_user(u_id)
    cursor.execute("SELECT SUM(level) FROM pokedex WHERE user_id = ?", (u_id,))
    mon_score = (cursor.fetchone()[0] or 1) + random.randint(1, 15)
    ia_score = random.randint(5, 50)
    if mon_score >= ia_score:
        cursor.execute("UPDATE users SET money = money + 100 WHERE user_id = ?", (u_id,))
        conn.commit()
        await ctx.send(f"🌸 Victoire contre le dresseur virtuel ! Tu gagnes 100$.")
    else:
        await ctx.send(f"💥 Défaite face au dresseur virtuel de l'IA...")

@discord_bot.command(name="champion")
async def champion_cmd(ctx):
    u_id = str(ctx.author.id)
    get_or_create_user(u_id)
    cursor.execute("SELECT SUM(level) FROM pokedex WHERE user_id = ?", (u_id,))
    mon_score = (cursor.fetchone()[0] or 1) + random.randint(1, 30)
    boss_score = random.randint(30, 80)
    if mon_score >= boss_score:
        cursor.execute("UPDATE users SET money = money + 1000, bonbon = bonbon + 5 WHERE user_id = ?", (u_id,))
        conn.commit()
        await ctx.send(f"🏆 INCROYABLE ! {ctx.author.mention} a vaincu le Boss Mewtwo ! Récompense : 1000$ et 5 Bonbons !")
    else:
        await ctx.send(f"💥 Le Boss Mewtwo t'a écrasé sans pitié...")


# --- ÉQUIPES ---
class EquipeModal(discord.ui.Modal, title="Sceller son Équipe"):
    yokai1 = discord.ui.TextInput(label="1er Esprit", placeholder="Ex: Pikachu", required=True)
    yokai2 = discord.ui.TextInput(label="2ème Esprit", placeholder="Ex: Dracaufeu", required=False)
    yokai3 = discord.ui.TextInput(label="3ème Esprit", placeholder="Ex: Mewtwo", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        cursor.execute("INSERT OR REPLACE INTO equipes (user_id, yokai1, yokai2, yokai3) VALUES (?, ?, ?, ?)", 
                       (user_id, self.yokai1.value or "Aucun", self.yokai2.value or "Aucun", self.yokai3.value or "Aucun"))
        conn.commit()
        await interaction.response.send_message("🛡️ Équipe enregistrée avec succès !", ephemeral=True)

class EquipeView(discord.ui.View):
    @discord.ui.button(label="Modifier mon équipe", style=discord.ButtonStyle.primary)
    async def btn_eq(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EquipeModal())

@discord_bot.command(name="equipe")
async def equipe_cmd(ctx, action: str = "voir", member: discord.Member = None):
    action = action.lower()
    if action == "creer":
        await ctx.send("🛡️ Clique ci-dessous pour composer ton équipe :", view=EquipeView())
    else:
        target = member or ctx.author
        cursor.execute("SELECT yokai1, yokai2, yokai3 FROM equipes WHERE user_id = ?", (str(target.id),))
        row = cursor.fetchone()
        if not row:
            await ctx.send(f"🌸 Aucune équipe enregistrée. Tape `!equipe creer`.")
            return
        embed = discord.Embed(title=f"🛡️ Équipe de {target.display_name}", color=0xFFC0CB)
        embed.add_field(name="Membres", value=f"1. {row[0]}\n2. {row[1]}\n3. {row[2]}", inline=False)
        await ctx.send(embed=embed)


# --- CLANS & VILLAGE ---
@discord_bot.command()
async def clan(ctx, action: str = "infos", *, nom: str = None):
    u_id = str(ctx.author.id)
    action = action.lower()
    
    if action == "creer" and nom:
        cursor.execute("SELECT nom_clan FROM clan_membres WHERE user_id = ?", (u_id,))
        if cursor.fetchone():
            await ctx.send("Tu fais déjà partie d'un clan !")
            return
        cursor.execute("INSERT OR IGNORE INTO clans (nom_clan, leader) VALUES (?, ?)", (nom, u_id))
        cursor.execute("INSERT OR REPLACE INTO clan_membres (user_id, nom_clan) VALUES (?, ?)", (u_id, nom))
        conn.commit()
        await ctx.send(f"⛩️ Le clan **{nom}** a été fondé avec succès !")
        
    elif action == "rejoindre" and nom:
        cursor.execute("SELECT nom_clan FROM clans WHERE nom_clan = ?", (nom,))
        if not cursor.fetchone():
            await ctx.send("Ce clan n'existe pas.")
            return
        cursor.execute("INSERT OR REPLACE INTO clan_membres (user_id, nom_clan) VALUES (?, ?)", (u_id, nom))
        conn.commit()
        await ctx.send(f"⛩️ Tu as rejoint le clan **{nom}** !")
        
    elif action == "infos":
        cursor.execute("SELECT nom_clan FROM clan_membres WHERE user_id = ?", (u_id,))
        res = cursor.fetchone()
        if not res:
            await ctx.send("Tu n'as pas de clan. Utilise `!clan creer <nom>` ou `!clan rejoindre <nom>`.")
            return
        c_name = res[0]
        cursor.execute("SELECT leader, niveau_village, points_village FROM clans WHERE nom_clan = ?", (c_name,))
        leader, niv, pts = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) FROM clan_membres WHERE nom_clan = ?", (c_name,))
        nb_m = cursor.fetchone()[0]
        await ctx.send(f"⛩️ **Clan {c_name}**\n👑 Leader : <@{leader}>\n👥 Membres : {nb_m}\n🏡 Niveau Village : {niv} (Pts: {pts})")

@discord_bot.command(name="clan_investir")
async def clan_investir(ctx, montant: int):
    u_id = str(ctx.author.id)
    u = get_or_create_user(u_id)
    if u["money"] < montant:
        await ctx.send("Fonds insuffisants.")
        return
    cursor.execute("SELECT nom_clan FROM clan_membres WHERE user_id = ?", (u_id,))
    res = cursor.fetchone()
    if not res:
        await ctx.send("Tu dois être dans un clan.")
        return
    c_name = res[0]
    cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (montant, u_id))
    cursor.execute("UPDATE clans SET points_village = points_village + ? WHERE nom_clan = ?", (montant, c_name))
    conn.commit()
    await ctx.send(f"🌸 Investissement de {montant}$ réussi dans le clan {c_name} !")

# Lancement du Bot
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    discord_bot.run(TOKEN)
else:
    pass
