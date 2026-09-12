import discord
from discord.ext import commands, tasks
import requests
import random
import sqlite3
import os
import threading
import asyncio
from flask import Flask, jsonify, request
from flask_cors import CORS
from twitchio.ext import commands as twitch_commands
from datetime import datetime, timedelta

# --- BASE DE DONNÉES ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'pokemon_bot.db')

conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()

# Tables
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

# Migration automatique des colonnes d'inventaire
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

# --- TOUTES LES COMMANDES ADMIN COMPLÈTES ---
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
            "• **`!adminhelp`** — Affiche l'aide complète des administrateurs.\n"
            "• **`!setchannel`** — Définit le salon actuel (ou un autre salon mentionné) comme le sanctuaire officiel où les esprits sauvages apparaîtront.\n"
            "• **`!settime <minutes>`** — Modifie le temps d'attente entre chaque apparition de Pokémon (minimum 0.5 minute).\n"
            "• **`!pop`** — Force l'apparition immédiate d'un esprit sauvage pour l'overlay ou les tests."
        ),
        inline=False
    )
    embed.add_field(
        name="💰 Économie & Modération :",
        value=(
            "• **`!addmoney @joueur <montant>`** — Ajoute une quantité spécifique d'argent au compte du dresseur ciblé.\n"
            "• **`!removemoney @joueur <montant>`** — Retire une quantité d'argent au compte du dresseur ciblé.\n"
            "• **`!givepokemon @joueur <nom> [True]`** — Offre un Pokémon directement dans le Pokédex d'un joueur (écris `True` à la fin si tu veux qu'il soit Shiny).\n"
            "• **`!resetplayer @joueur`** — Réinitialise totalement le profil, l'argent et le Pokédex d'un dresseur."
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
    await ctx.send(f"🌸 Les Pokémon réapparaîtront désormais dans le salon sacré {target_channel.mention} !")

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def settime(ctx, minutes: float):
    if minutes < 0.5:
        await ctx.send("🌸 Le temps de spawn doit être d'au moins 0.5 minute (30 secondes).")
        return
    cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('spawn_interval_minutes', ?)", (str(minutes),))
    conn.commit()
    boucle_spawn.change_interval(minutes=minutes)
    await ctx.send(f"🌸 L'intervalle entre chaque apparition est désormais fixé à **{minutes} minute(s)** !")

@discord_bot.command(name="pop")
@commands.has_permissions(administrator=True)
async def pop_cmd(ctx):
    await apparaitre_pokemon(ctx.channel)
    await ctx.send("🌸 [ADMIN] Un esprit sauvage vient d'être invoqué de force pour l'overlay !")

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def addmoney(ctx, member: discord.Member, amount: int):
    get_or_create_user(str(member.id))
    cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (amount, str(member.id)))
    conn.commit()
    await ctx.send(f"🌸 Ajout de **{amount}$** au compte de {member.mention} avec succès !")

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def removemoney(ctx, member: discord.Member, amount: int):
    get_or_create_user(str(member.id))
    cursor.execute("UPDATE users SET money = MAX(0, money - ?) WHERE user_id = ?", (amount, str(member.id)))
    conn.commit()
    await ctx.send(f"🌸 Retrait de **{amount}$** du compte de {member.mention} avec succès !")

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def givepokemon(ctx, member: discord.Member, pokemon_name: str, shiny: bool = False):
    get_or_create_user(str(member.id))
    nom_cap = pokemon_name.capitalize()
    shiny_int = 1 if shiny else 0
    cursor.execute("INSERT INTO pokedex (user_id, pokemon_name, is_shiny) VALUES (?, ?, ?)", (str(member.id), nom_cap, shiny_int))
    conn.commit()
    shiny_txt = " ✨ [SHINY] ✨" if shiny else ""
    await ctx.send(f"🌸 Ajout de **{nom_cap}**{shiny_txt} dans le Pokédex de {member.mention} avec succès !")

@discord_bot.command()
@commands.has_permissions(administrator=True)
async def resetplayer(ctx, member: discord.Member):
    u_id = str(member.id)
    cursor.execute("DELETE FROM users WHERE user_id = ?", (u_id,))
    cursor.execute("DELETE FROM pokedex WHERE user_id = ?", (u_id,))
    conn.commit()
    get_or_create_user(u_id)
    await ctx.send(f"🌸 Le profil et le Pokédex de {member.mention} ont été totalement réinitialisés !")


# --- COMMANDES JOUEURS ---
@discord_bot.command()
async def profil(ctx, member: discord.Member = None):
    target = member or ctx.author
    u_data = get_or_create_user(str(target.id))
    
    cursor.execute("SELECT COUNT(*) FROM pokedex WHERE user_id = ?", (str(target.id),))
    nb_pokes = cursor.fetchone()[0]

    embed = discord.Embed(title=f"⛩️ Profil de {target.display_name} ⛩️", color=0xFFB7C5)
    embed.add_field(name="💰 Argent", value=f"{u_data['money']}$", inline=True)
    embed.add_field(name="📖 Esprits capturés", value=f"{nb_pokes}", inline=True)
    embed.add_field(name="🔴 Pokéballs", value=f"🔴 x{u_data['pokeball']} | 🔵 x{u_data['superball']} | 🟣 x{u_data['hyperball']} | 🟡 x{u_data['masterball']}", inline=False)
    embed.add_field(name="🧪 Objets", value=f"Potion: x{u_data['potion']} | Rappel: x{u_data['rappel']} | Bonbon: x{u_data['bonbon']}", inline=False)
    await ctx.send(embed=embed)

@discord_bot.command()
async def inv(ctx, member: discord.Member = None):
    target = member or ctx.author
    cursor.execute("SELECT pokemon_name, is_shiny FROM pokedex WHERE user_id = ?", (str(target.id),))
    pokemons = cursor.fetchall()
    
    if not pokemons:
        await ctx.send(f"🌸 {target.mention} n'a encore capturé aucun esprit dans son Pokédex !")
        return

    liste_pokes = []
    for p in pokemons:
        shiny_icon = "✨" if p[1] == 1 else ""
        liste_pokes.append(f"{p[0]} {shiny_icon}")

    description = ", ".join(liste_pokes[:30])
    if len(liste_pokes) > 30:
        description += f"\n\n*(Et {len(liste_pokes) - 30} autres...)*"

    embed = discord.Embed(title=f"🌸 Pokédex de {target.display_name} ({len(liste_pokes)} capturés)", description=description, color=0xFFC0CB)
    await ctx.send(embed=embed)

@discord_bot.command()
async def shop(ctx):
    embed = discord.Embed(title="⛩️ Boutique du Sanctuaire Sakura ⛩️", description="Utilise `!buy <article> [quantité]` pour acheter !", color=0xFFB7C5)
    embed.add_field(name="🔴 Pokéball", value="Prix : 100$ (`!buy pokeball`)", inline=False)
    embed.add_field(name="🔵 Superball", value="Prix : 300$ (`!buy superball`)", inline=False)
    embed.add_field(name="🟣 Hyperball", value="Prix : 600$ (`!buy hyperball`)", inline=False)
    embed.add_field(name="🟡 Masterball", value="Prix : 2500$ (`!buy masterball`)", inline=False)
    embed.add_field(name="🧪 Potion / Rappel", value="Potion: 150$ | Rappel: 300$", inline=False)
    await ctx.send(embed=embed)

@discord_bot.command()
async def buy(ctx, article: str, quantite: int = 1):
    item = article.lower()
    prix_unitaires = {"pokeball": 100, "superball": 300, "hyperball": 600, "masterball": 2500, "potion": 150, "rappel": 300}

    if item not in prix_unitaires:
        await ctx.send("Cet article n'existe pas dans la boutique ! Tape `!shop` pour voir la liste.")
        return

    if quantite < 1:
        quantite = 1

    cout_total = prix_unitaires[item] * quantite
    u_data = get_or_create_user(str(ctx.author.id))

    if u_data["money"] < cout_total:
        await ctx.send(f"🌸 {ctx.author.mention}, tu n'as pas assez d'argent ! Il te faut **{cout_total}$**.")
        return

    cursor.execute(f"UPDATE users SET money = money - ?, {item} = {item} + ? WHERE user_id = ?", (cout_total, quantite, str(ctx.author.id)))
    conn.commit()
    await ctx.send(f"🌸 Achat réussi ! {ctx.author.mention} a acheté **{quantite}x {item}** pour **{cout_total}$** !")

@discord_bot.command()
async def daily(ctx):
    u_id = str(ctx.author.id)
    u_data = get_or_create_user(u_id)
    now = datetime.now()

    if u_data["last_daily"]:
        last_date = datetime.fromisoformat(u_data["last_daily"])
        if now - last_date < timedelta(hours=24):
            reste = timedelta(hours=24) - (now - last_date)
            heures, reste_sec = divmod(reste.seconds, 3600)
            minutes = reste_sec // 60
            await ctx.send(f"🌸 {ctx.author.mention}, tu as déjà récupéré ton offrande quotidienne ! Reviens dans **{heures}h {minutes}m**.")
            return

    cursor.execute("UPDATE users SET money = money + 100, pokeball = pokeball + 3, last_daily = ? WHERE user_id = ?", (now.isoformat(), u_id))
    conn.commit()
    await ctx.send(f"🌸 {ctx.author.mention} a récupéré son offrande quotidienne : **100$** et **3 Pokéballs** !")

@discord_bot.command()
async def ia(ctx):
    get_or_create_user(str(ctx.author.id))
    if random.randint(1, 100) <= 65:
        gain = 60
        cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (gain, str(ctx.author.id)))
        conn.commit()
        await ctx.send(f"⚔️ **Victoire !** {ctx.author.mention} a triomphé du dresseur virtuel et remporte **{gain}$** !")
    else:
        await ctx.send(f"⚔️ **Défaite...** Le dresseur virtuel était trop fort cette fois-ci ! Entraîne-toi encore.")

@discord_bot.command()
async def champion(ctx):
    get_or_create_user(str(ctx.author.id))
    if random.randint(1, 100) <= 35:
        gain = 200
        cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (gain, str(ctx.author.id)))
        conn.commit()
        await ctx.send(f"👑 **EXPLOIT LÉGENDAIRE !** {ctx.author.mention} a vaincu le Boss Mewtwo et empoche la récompense suprême de **{gain}$** !")
    else:
        await ctx.send(f"⚡ Le Boss Mewtwo a terrassé l'équipe de {ctx.author.mention} d'un simple regard... C'est une défaite cuisante !")

@discord_bot.command()
async def top(ctx):
    cursor.execute("""
        SELECT u.user_id, u.money, COUNT(p.id) as nb_poke 
        FROM users u 
        LEFT JOIN pokedex p ON u.user_id = p.user_id 
        GROUP BY u.user_id 
        ORDER BY nb_poke DESC, u.money DESC 
        LIMIT 5
    """)
    top_users = cursor.fetchall()

    description = ""
    for i, u in enumerate(top_users, 1):
        try:
            user_obj = await discord_bot.fetch_user(int(u[0]))
            nom = user_obj.name
        except:
            nom = f"Utilisateur {u[0]}"
        description += f"**{i}.** {nom} — 📖 {u[2]} esprits | 💰 {u[1]}$\n"

    embed = discord.Embed(title="⛩️ Classement des Meilleurs Dresseurs ⛩️", description=description or "Aucun dresseur pour l'instant.", color=0xFFB7C5)
    await ctx.send(embed=embed)

@discord_bot.command()
async def capture(ctx, ball_type: str = "pokeball"):
    global pokemon_sauvage, derniere_capture_anim
    ball = ball_type.lower()
    taux_et_noms = {"pokeball": (70, "Pokéball"), "superball": (85, "Superball"), "hyperball": (95, "Hyperball"), "masterball": (100, "Masterball")}

    if ball not in taux_et_noms:
        await ctx.send("Cette relique/balle est inconnue ! Choisis parmi : `pokeball`, `superball`, `hyperball`, `masterball`.")
        return

    user_data = get_or_create_user(str(ctx.author.id))

    if pokemon_sauvage is None:
        await ctx.send("🌸 Aucun esprit sauvage ne se manifeste en ce moment !")
        return

    if user_data[ball] <= 0:
        await ctx.send(f"{ctx.author.mention}, tu ne possèdes pas de **{taux_et_noms[ball][1]}** !")
        return

    derniere_capture_anim = ball

    cursor.execute(f"UPDATE users SET {ball} = {ball} - 1 WHERE user_id = ?", (str(ctx.author.id),))
    
    taux = taux_et_noms[ball][0]
    if random.randint(1, 100) <= taux:
        pokemon_attrape, est_shiny = pokemon_sauvage["name"], pokemon_sauvage["is_shiny"]
        pokemon_sauvage = None

        gain = 200 if est_shiny else 50
        shiny_int = 1 if est_shiny else 0

        cursor.execute("INSERT INTO pokedex (user_id, pokemon_name, is_shiny) VALUES (?, ?, ?)", (str(ctx.author.id), pokemon_attrape, shiny_int))
        cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (gain, str(ctx.author.id)))
        conn.commit()

        texte_shiny = " ✨ **SHINY CÉLESTE** ✨" if est_shiny else ""
        await ctx.send(f"🌸 **Rituel réussi !** {ctx.author.mention} a charmé **{pokemon_attrape}**{texte_shiny} avec une **{taux_et_noms[ball][1]}** et gagne **{gain}$** !")
    else:
        nom = pokemon_sauvage["name"]
        pokemon_sauvage = None
        await ctx.send(f"💨 L'esprit de **{nom}** s'est évaporé dans un nuage de pétales malgré ta **{taux_et_noms[ball][1]}** !")
    conn.commit()


# --- BOT TWITCH ---
class TwitchBot(twitch_commands.Bot):
    def __init__(self):
        super().__init__(
            token=os.getenv('TWITCH_TOKEN'),
            client_id=os.getenv('TWITCH_CLIENT_ID'),
            client_secret=os.getenv('TWITCH_CLIENT_SECRET'),
            prefix='!',
            initial_channels=['yokaiiifox']
        )

    async def event_ready(self):
        print(f"Le bot Twitch est connecté au chat de la chaîne : {self.connected_channels[0]} 🌸")

    @twitch_commands.command(name='capture')
    async def twitch_capture(self, ctx: twitch_commands.Context):
        global pokemon_sauvage, derniere_capture_anim
        username = ctx.author.name

        if pokemon_sauvage is None:
            await ctx.send(f"@{username} 🌸 Aucun esprit sauvage ne se manifeste sur le live en ce moment !")
            return

        user_id = f"twitch_{ctx.author.id}"
        user_data = get_or_create_user(user_id)

        if user_data["pokeball"] <= 0:
            await ctx.send(f"@{username}, tu n'as plus de **Pokéball** dans ton inventaire ! 🏮")
            return

        derniere_capture_anim = "pokeball"

        cursor.execute("UPDATE users SET pokeball = pokeball - 1 WHERE user_id = ?", (user_id,))
        
        if random.randint(1, 100) <= 70:
            pokemon_attrape, est_shiny = pokemon_sauvage["name"], pokemon_sauvage["is_shiny"]
            pokemon_sauvage = None

            gain = 200 if est_shiny else 50
            shiny_int = 1 if est_shiny else 0

            cursor.execute("INSERT INTO pokedex (user_id, pokemon_name, is_shiny) VALUES (?, ?, ?)", (user_id, pokemon_attrape, shiny_int))
            cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (gain, user_id))
            conn.commit()

            shiny_txt = " ✨ [SHINY] ✨" if est_shiny else ""
            await ctx.send(f"🌸 **Rituel réussi !** @{username} a capturé **{pokemon_attrape}**{shiny_txt} avec une Pokéball et remporte **{gain}$** !")
        else:
            nom = pokemon_sauvage["name"]
            pokemon_sauvage = None
            conn.commit()
            await ctx.send(f"💨 L'esprit de **{nom}** s'est enfui dans un nuage de pétales malgré la Pokéball de @{username} !")


# --- SERVEUR WEB (FLASK) ---
app = Flask(__name__)
CORS(app)

@app.route('/')
def overlay_html():
    return """
    <html>
        <head>
            <style>
                body { background-color: rgba(0,0,0,0); margin: 0; font-family: Arial, sans-serif; overflow: hidden; }
                #container { text-align: center; color: white; text-shadow: 2px 2px 4px #000; position: absolute; top: 20px; left: 20px; background: rgba(0, 0, 0, 0.75); padding: 20px; border-radius: 15px; border: 3px solid #ffb7c5; width: 250px; }
                .poke-img { width: 140px; height: 140px; image-rendering: pixelated; animation: float 2s ease-in-out infinite; }
                @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
                h2 { margin: 8px 0; font-size: 20px; color: #ffeb3b; }
                p { margin: 5px 0; font-size: 15px; color: #ffffff; font-weight: bold; background: rgba(255, 183, 197, 0.2); padding: 4px; border-radius: 6px; }

                #pokeball-anim {
                    position: absolute;
                    bottom: -100px;
                    left: 145px;
                    width: 60px;
                    height: 60px;
                    transform: translateX(-50%);
                    display: none;
                    z-index: 99;
                }
                @keyframes throwBall {
                    0% { bottom: -100px; opacity: 1; transform: scale(0.5) rotate(0deg); }
                    50% { bottom: 200px; transform: scale(1.2) rotate(360deg); }
                    100% { bottom: 120px; transform: scale(0.8) rotate(720deg); opacity: 0; }
                }
                .throwing {
                    display: block !important;
                    animation: throwBall 0.8s ease-in-out forwards;
                }
            </style>
        </head>
        <body>
            <div id="container">
                <div id="content"></div>
            </div>
            <img id="pokeball-anim" src="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/poke-ball.png" />

            <script>
                let lastStateAnim = false;

                async function updateOverlay() {
                    try {
                        let response = await fetch('/current-pokemon');
                        let data = await response.json();
                        let container = document.getElementById('content');
                        let ballElem = document.getElementById('pokeball-anim');

                        if (data.anim_capture && !lastStateAnim) {
                            ballElem.classList.remove('throwing');
                            void ballElem.offsetWidth;
                            ballElem.classList.add('throwing');
                            lastStateAnim = true;
                        } else if (!data.anim_capture) {
                            lastStateAnim = false;
                        }

                        if (data.name) {
                            let shinyText = data.is_shiny ? " ✨ SHINY ✨" : "";
                            container.innerHTML = `
                                <img class="poke-img" src="${data.image_url}" />
                                <h2>${data.name}${shinyText}</h2>
                                <p>🔮 Type : ${data.types}</p>
                                <p>📏 ${data.height}m | ⚖️ ${data.weight}kg</p>
                            `;
                        } else {
                            container.innerHTML = "";
                        }
                    } catch (e) { console.log(e); }
                }
                setInterval(updateOverlay, 1000);
                updateOverlay();
            </script>
        </body>
    </html>
    """

@app.route('/current-pokemon')
def current_pokemon():
    global pokemon_sauvage, derniere_capture_anim
    
    anim_active = False
    if derniere_capture_anim:
        anim_active = True
        derniere_capture_anim = None

    if pokemon_sauvage:
        return jsonify({
            "name": pokemon_sauvage["name"],
            "is_shiny": pokemon_sauvage["is_shiny"],
            "image_url": pokemon_sauvage["image_url"],
            "height": pokemon_sauvage["height"],
            "weight": pokemon_sauvage["weight"],
            "types": pokemon_sauvage["types"],
            "anim_capture": anim_active
        })
    return jsonify({"name": None, "anim_capture": anim_active})

import os

def run_flask():
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


# --- LANCEMENT MULTI-THREAD ---
def run_twitch():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    twitch_bot = TwitchBot()
    twitch_bot.run()

if __name__ == '__main__':
    t_flask = threading.Thread(target=run_flask)
    t_flask.start()

    t_twitch = threading.Thread(target=run_twitch)
    t_twitch.start()

    discord_bot.run(os.getenv('DISCORD_TOKEN'))
