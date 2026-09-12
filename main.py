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

# --- SERVEUR WEB (FLASK) POUR MAINTENIR RENDER ACTIF ---
app = Flask(__name__)
CORS(app)

@app.route('/')
def keep_alive():
    return "Mon bot Pokémon est bien en ligne !"

# --- DICTIONNAIRE DE TRADUCTION FRANÇAIS -> ANGLAIS ---
# Permet de lier les noms français des Pokémon vers l'API officielle
TRADUCTION_POKEMON = {
    "dracaufeu": "charizard",
    "reptincel": "charmeleon",
    "salameche": "charmander",
    "florizarre": "venusaur",
    "herbizarre": "ivysaur",
    "bulbizarre": "bulbasaur",
    "tortank": "blastoise",
    "carabaffe": "wartortle",
    "carapuce": "squirtle",
    "pikachu": "pikachu",
    "dracolosse": "dragonite",
    "dracaucor": "dragonair",
    "minidraco": "dratini",
    "mewtwo": "mewtwo",
    "mew": "mew",
    # Ajoutez d'autres traductions si besoin au format "francais": "english"
}

def get_api_name(nom_francais):
    nom_clean = nom_francais.lower().strip()
    return TRADUCTION_POKEMON.get(nom_clean, nom_clean)

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
        is_shiny INTEGER DEFAULT 0
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

nouvelles_colonnes = [
    ("pokeball", "INTEGER DEFAULT 5"),
    ("superball", "INTEGER DEFAULT 0"),
    ("hyperball", "INTEGER DEFAULT 0"),
    ("masterball", "INTEGER DEFAULT 0"),
    ("potion", "INTEGER DEFAULT 0"),
    ("rappel", "INTEGER DEFAULT 0"),
    ("bonbon", "INTEGER DEFAULT 0")
]

cursor.execute("PRAGMA table_info(users)")
colonnes_existantes = [column[1] for column in cursor.fetchall()]

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
    cursor.execute("SELECT pokeball, superball, hyperball, masterball, potion, rappel, bonbon, money, last_daily FROM users WHERE user_id = ?", (u_id,))
    data = cursor.fetchone()
    if not data:
        cursor.execute("INSERT INTO users (user_id, pokeball, superball, hyperball, masterball, potion, rappel, bonbon, money, last_daily) VALUES (?, 5, 0, 0, 0, 0, 0, 0, 100, NULL)", (u_id,))
        conn.commit()
        return {"pokeball": 5, "superball": 0, "hyperball": 0, "masterball": 0, "potion": 0, "rappel": 0, "bonbon": 0, "money": 100, "last_daily": None}
    return {"pokeball": data[0], "superball": data[1], "hyperball": data[2], "masterball": data[3], "potion": data[4], "rappel": data[5], "bonbon": data[6], "money": data[7], "last_daily": data[8]}

def get_spawn_channel_id():
    cursor.execute("SELECT value FROM config WHERE key = 'spawn_channel_id'")
    data = cursor.fetchone()
    return int(data[0]) if data and data[0] else None

def get_spawn_interval():
    cursor.execute("SELECT value FROM config WHERE key = 'spawn_interval_minutes'")
    data = cursor.fetchone()
    return float(data[0]) if data and data[0] else 2.0

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
        types = [t['type']['name'].capitalize() for t in data['types']]
        types_str = " / ".join(types)

        image_url = data['sprites']['other']['official-artwork']['front_shiny' if is_shiny else 'front_default'] or data['sprites']['front_default']

        if is_shiny:
            titre = "🌸✨ ─── [ ⛩️ SANCTUAIRE SAKURA ⛩️ ] ─── ✨🌸"
            description = (
                "🍡 **~ APPARITION D'UN YŌKAI DIVIN ~** 🍡\n\n"
                "Un esprit céleste aux reflets de pétales d'or s'est matérialisé sous les cerisiers en fleurs !\n\n"
                "🌸 **{name} Shiny** ✨\n"
                "📏 Taille : {height}m | ⚖️ Poids : {weight}kg | 🔮 Type : {types}\n\n"
                "*Invoque ton courage et capture-le avec* `!capture <ball>` !"
            ).format(name=name, height=height, weight=weight, types=types_str)
            couleur = 0xFFB7C5
        else:
            titre = "🌸 ─── [ ⛩️ JARDIN DES SAKURAS ⛩️ ] ─── 🌸"
            description = (
                "🍵 **~ UN ESPRIT SAUVAGE APPARAÎT ~** 🍵\n\n"
                "Porté par une brise de printemps, **{name}** émerge des pétales de cerisier...\n"
                "📏 Taille : {height}m | ⚖️ Poids : {weight}kg | 🔮 Type : {types}\n\n"
                "*Utilise* `!capture <ball>` *pour tenter de l'accueillir dans ton clan !*"
            ).format(name=name, height=height, weight=weight, types=types_str)
            couleur = 0xFFC0CB

        pokemon_sauvage = {
            "name": name, 
            "is_shiny": is_shiny, 
            "image_url": image_url,
            "height": height,
            "weight": weight,
            "types": types_str
        }

        embed = discord.Embed(title=titre, description=description, color=couleur)
        embed.set_image(url=image_url)
        embed.set_footer(text="🏮 Voie des Esprits • Clan des Yōkai • Tape !capture")
        await channel.send(embed=embed)

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
    interval = get_spawn_interval()
    boucle_spawn.change_interval(minutes=interval)

@discord_bot.event
async def on_ready():
    print(f"Le bot Discord {discord_bot.user.name} est prêt avec le thème Sakura ! 🌸")
    if not boucle_spawn.is_running():
        boucle_spawn.start()

# --- COMMANDES ADMIN ---
@discord_bot.command()
@commands.has_permissions(administrator=True)
async def adminhelp(ctx):
    embed = discord.Embed(
        title="🛠️ PANNEAU DE CONTRÔLE - ADMIN 🛠️",
        description="Commandes réservées à la gestion du bot sur le serveur :",
        color=0xFFB7C5
    )
    embed.add_field(
        name="⚙️ Configuration :",
        value=(
            "• **`!adminhelp`** — Affiche l'aide.\n"
            "• **`!setchannel`** — Définit le salon des apparitions.\n"
            "• **`!settime <minutes>`** — Modifie l'intervalle de spawn.\n"
            "• **`!pop`** — Force l'apparition d'un Pokémon."
        ),
        inline=False
    )
    await ctx.send(embed=embed)

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def setchannel(ctx, channel: discord.TextChannel = None):
    target_channel = channel or ctx.channel
    cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('spawn_channel_id', ?)", (str(target_channel.id),))
    conn.commit()
    await ctx.send(f"🌸 Salon de spawn défini sur {target_channel.mention} !")

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def settime(ctx, minutes: float):
    if minutes < 0.5:
        await ctx.send("🌸 Minimum 0.5 minute.")
        return
    cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('spawn_interval_minutes', ?)", (str(minutes),))
    conn.commit()
    boucle_spawn.change_interval(minutes=minutes)
    await ctx.send(f"🌸 Intervalle fixé à **{minutes} min** !")

@discord_bot.command(name="pop")
@commands.has_permissions(administrator=True)
async def pop_cmd(ctx):
    await apparaitre_pokemon(ctx.channel)
    await ctx.send("🌸 [ADMIN] Apparition forcée !")

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def addmoney(ctx, member: discord.Member, amount: int):
    get_or_create_user(str(member.id))
    cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (amount, str(member.id)))
    conn.commit()
    await ctx.send(f"🌸 Ajout de **{amount}$** à {member.mention} !")

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def removemoney(ctx, member: discord.Member, amount: int):
    get_or_create_user(str(member.id))
    cursor.execute("UPDATE users SET money = MAX(0, money - ?) WHERE user_id = ?", (amount, str(member.id)))
    conn.commit()
    await ctx.send(f"🌸 Retrait de **{amount}$** à {member.mention} !")

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def givepokemon(ctx, member: discord.Member, pokemon_name: str, shiny: bool = False):
    get_or_create_user(str(member.id))
    nom_cap = pokemon_name.capitalize()
    shiny_int = 1 if shiny else 0
    cursor.execute("INSERT INTO pokedex (user_id, pokemon_name, is_shiny) VALUES (?, ?, ?)", (str(member.id), nom_cap, shiny_int))
    conn.commit()
    await ctx.send(f"🌸 Ajout de **{nom_cap}** à {member.mention} !")

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def resetplayer(ctx, member: discord.Member):
    u_id = str(member.id)
    cursor.execute("DELETE FROM users WHERE user_id = ?", (u_id,))
    cursor.execute("DELETE FROM pokedex WHERE user_id = ?", (u_id,))
    conn.commit()
    get_or_create_user(u_id)
    await ctx.send(f"🌸 Profil de {member.mention} réinitialisé !")


# --- COMMANDES JOUEURS ---
@discord_bot.command()
async def profil(ctx, member: discord.Member = None):
    target = member or ctx.author
    u_data = get_or_create_user(str(target.id))
    cursor.execute("SELECT COUNT(*) FROM pokedex WHERE user_id = ?", (str(target.id),))
    nb_pokes = cursor.fetchone()[0]

    embed = discord.Embed(title=f"⛩️ Profil de {target.display_name} ⛩️", color=0xFFB7C5)
    embed.add_field(name="💰 Argent", value=f"{u_data['money']}$", inline=True)
    embed.add_field(name="📖 Esprits", value=f"{nb_pokes}", inline=True)
    embed.add_field(name="🔴 Balls", value=f"🔴 x{u_data['pokeball']} | 🔵 x{u_data['superball']} | 🟣 x{u_data['hyperball']} | 🟡 x{u_data['masterball']}", inline=False)
    await ctx.send(embed=embed)

# --- INTERACTIVITÉ INVENTAIRE & DÉTAILS AVEC TRADUCTION ---
class PokedexSelect(discord.ui.Select):
    def __init__(self, pokemons):
        options = []
        for name, shiny in pokemons[:25]:
            label = f"{name} (Shiny)" if shiny else name
            emoji = "✨" if shiny else "🌸"
            options.append(discord.SelectOption(label=label, emoji=emoji, value=f"{name}_{shiny}"))
        
        super().__init__(placeholder="Choisis un esprit pour voir ses détails...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        val_parts = self.values[0].split("_")
        name = val_parts[0]
        is_shiny = int(val_parts[1])

        api_name = get_api_name(name)

        response = requests.get(f"https://pokeapi.co/api/v2/pokemon/{api_name}")
        if response.status_code == 200:
            data = response.json()
            height = data['height'] / 10.0
            weight = data['weight'] / 10.0
            types = " / ".join([t['type']['name'].capitalize() for t in data['types']])
            image_url = data['sprites']['other']['official-artwork']['front_shiny' if is_shiny else 'front_default'] or data['sprites']['front_default']

            embed = discord.Embed(
                title=f"⛩️ Fiche de l'Esprit : {name}{' ✨' if is_shiny else ''}",
                description=f"📏 **Taille :** {height}m\n⚖️ **Poids :** {weight}kg\n🔮 **Type(s) :** {types}",
                color=0xFFB7C5 if is_shiny else 0xFFC0CB
            )
            embed.set_image(url=image_url)
            embed.set_footer(text=f"Demandé par {interaction.user.display_name}")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(f"Erreur : Impossible de récupérer les données pour {name} (API ID: {api_name}).", ephemeral=True)

class PokedexView(discord.ui.View):
    def __init__(self, pokemons):
        super().__init__()
        self.add_item(PokedexSelect(pokemons))

@discord_bot.command()
async def inv(ctx, member: discord.Member = None):
    target = member or ctx.author
    cursor.execute("SELECT pokemon_name, is_shiny FROM pokedex WHERE user_id = ?", (str(target.id),))
    pokemons = cursor.fetchall()
    
    if not pokemons:
        await ctx.send(f"🌸 {target.mention} n'a aucun esprit dans son clan !")
        return

    embed = discord.Embed(
        title=f"🌸 Clan de {target.display_name} ({len(pokemons)} esprits)",
        description="Utilise le menu déroulant ci-dessous pour inspecter un esprit en détail !",
        color=0xFFC0CB
    )
    
    view = PokedexView(pokemons)
    await ctx.send(embed=embed, view=view)

@discord_bot.command()
async def shop(ctx):
    embed = discord.Embed(title="⛩️ Boutique ⛩️", description="Utilise `!buy <article> [quantité]`", color=0xFFB7C5)
    embed.add_field(name="Articles", value="pokeball (100$) | superball (300$) | hyperball (600$) | masterball (2500$)", inline=False)
    await ctx.send(embed=embed)

@discord_bot.command()
async def buy(ctx, article: str, quantite: int = 1):
    item = article.lower()
    prix_unitaires = {"pokeball": 100, "superball": 300, "hyperball": 600, "masterball": 2500, "potion": 150, "rappel": 300}

    if item not in prix_unitaires:
        await ctx.send("Article inconnu !")
        return

    cout_total = prix_unitaires[item] * max(1, quantite)
    u_data = get_or_create_user(str(ctx.author.id))

    if u_data["money"] < cout_total:
        await ctx.send(f"Fonds insuffisants ({cout_total}$ requis).")
        return

    cursor.execute(f"UPDATE users SET money = money - ?, {item} = {item} + ? WHERE user_id = ?", (cout_total, quantite, str(ctx.author.id)))
    conn.commit()
    await ctx.send(f"Achat réussi de {quantite}x {item} !")

@discord_bot.command()
async def daily(ctx):
    u_id = str(ctx.author.id)
    u_data = get_or_create_user(u_id)
    now = datetime.now()

    if u_data["last_daily"]:
        last_date = datetime.fromisoformat(u_data["last_daily"])
        if now - last_date < timedelta(hours=24):
            await ctx.send("Offrande déjà récupérée aujourd'hui !")
            return

    cursor.execute("UPDATE users SET money = money + 100, pokeball = pokeball + 3, last_daily = ? WHERE user_id = ?", (now.isoformat(), u_id))
    conn.commit()
    await ctx.send("🌸 Récompense journalière récupérée : 100$ et 3 Pokéballs !")

@discord_bot.command()
async def ia(ctx):
    get_or_create_user(str(ctx.author.id))
    if random.randint(1, 100) <= 65:
        cursor.execute("UPDATE users SET money = money + 60 WHERE user_id = ?", (str(ctx.author.id),))
        conn.commit()
        await ctx.send(f"⚔️ Victoire de {ctx.author.mention} (+60$) !")
    else:
        await ctx.send(f"⚔️ Défaite de {ctx.author.mention}...")

@discord_bot.command()
async def champion(ctx):
    get_or_create_user(str(ctx.author.id))
    if random.randint(1, 100) <= 35:
        cursor.execute("UPDATE users SET money = money + 200 WHERE user_id = ?", (str(ctx.author.id),))
        conn.commit()
        await ctx.send(f"👑 Exploit ! {ctx.author.mention} a vaincu le Boss (+200$) !")
    else:
        await ctx.send(f"⚡ Échec contre le Boss...")

@discord_bot.command()
async def top(ctx):
    cursor.execute("SELECT user_id, money FROM users ORDER BY money DESC LIMIT 5")
    top_users = cursor.fetchall()
    desc = "\n".join([f"<@{u[0]}> — {u[1]}$" for u in top_users])
    embed = discord.Embed(title="⛩️ Classement ⛩️", description=desc or "Aucun", color=0xFFB7C5)
    await ctx.send(embed=embed)

@discord_bot.command()
async def capture(ctx, ball_type: str = "pokeball"):
    global pokemon_sauvage, derniere_capture_anim
    ball = ball_type.lower()
    taux_et_noms = {"pokeball": (70, "Pokéball"), "superball": (85, "Superball"), "hyperball": (95, "Hyperball"), "masterball": (100, "Masterball")}

    if ball not in taux_et_noms or pokemon_sauvage is None:
        await ctx.send("Impossible de capturer pour le moment.")
        return

    user_data = get_or_create_user(str(ctx.author.id))
    if user_data[ball] <= 0:
        await ctx.send("Vous n'avez pas cette ball !")
        return

    derniere_capture_anim = ball
    cursor.execute(f"UPDATE users SET {ball} = {ball} - 1 WHERE user_id = ?", (str(ctx.author.id),))
    
    if random.randint(1, 100) <= taux_et_noms[ball][0]:
        poke, shiny = pokemon_sauvage["name"], pokemon_sauvage["is_shiny"]
        pokemon_sauvage = None
        cursor.execute("INSERT INTO pokedex (user_id, pokemon_name, is_shiny) VALUES (?, ?, ?)", (str(ctx.author.id), poke, 1 if shiny else 0))
        cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (200 if shiny else 50, str(ctx.author.id)))
        conn.commit()
        await ctx.send(f"🌸 Capturé : {poke} {'✨' if shiny else ''} !")
    else:
        pokemon_sauvage = None
        conn.commit()
        await ctx.send("L'esprit s'est enfui...")

# Routes Flask additionnelles pour l'overlay/pokedex existantes
@app.route('/current-pokemon')
def current_pokemon():
    global pokemon_sauvage, derniere_capture_anim
    anim_active = bool(derniere_capture_anim)
    derniere_capture_anim = None
    if pokemon_sauvage:
        return jsonify({**pokemon_sauvage, "anim_capture": anim_active})
    return jsonify({"name": None, "anim_capture": anim_active})

@app.route('/pokedex')
def pokedex_html():
    cursor.execute("SELECT pokemon_name, is_shiny FROM pokedex")
    all_pokes = cursor.fetchall()
    
    cards = ""
    for name, shiny in all_pokes:
        shiny_badge = " ✨" if shiny else ""
        border_color = "#ffd700" if shiny else "#ffb7c5"
        cards += f"""
        <div style="background: rgba(0,0,0,0.8); border: 2px solid {border_color}; border-radius: 12px; padding: 15px; text-align: center; width: 140px; color: white; box-shadow: 0 4px 8px rgba(0,0,0,0.3);">
            <h3 style="margin: 5px 0; font-size: 16px; color: #ffeb3b;">{name}{shiny_badge}</h3>
        </div>
        """
        
    return f"""
    <html>
        <head>
            <title>Galerie des Esprits - Yōkai Bot</title>
            <style>
                body {{ background: #1a1a1a; font-family: Arial, sans-serif; color: white; padding: 20px; }}
                h1 {{ text-align: center; color: #ffb7c5; text-shadow: 2px 2px 4px #000; }}
                .grid {{ display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <h1>⛩️ Galerie des Esprits Capturés ⛩️</h1>
            <div class="grid">
                {cards or "<p style='text-align:center;'>Aucun esprit capturé pour le moment...</p>"}
            </div>
        </body>
    </html>
    """

def run_flask():
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    t_flask = threading.Thread(target=run_flask)
    t_flask.start()

    discord_bot.run(os.getenv('DISCORD_TOKEN'))
