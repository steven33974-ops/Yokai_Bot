import discord
from discord.ext import commands, tasks
import requests
import random
import sqlite3
import os
import asyncio
import threading
from datetime import datetime, timedelta
from flask import Flask
from flask_cors import CORS

# --- SERVEUR WEB (FLASK) ---
app = Flask(__name__)
CORS(app)

@app.route('/')
def keep_alive():
    return "Mon bot Yōkai est bien en ligne !"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

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
        difficulte TEXT DEFAULT 'Facile',
        objectif INTEGER,
        progression INTEGER DEFAULT 0,
        terminee INTEGER DEFAULT 0,
        recompense INTEGER DEFAULT 1000,
        PRIMARY KEY (user_id, type_quete, difficulte)
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS collection_cartes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        carte_id TEXT,
        nom_carte TEXT,
        rarte_carte TEXT,
        image_url TEXT,
        quantite INTEGER DEFAULT 1
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS marche_cartes (
        vente_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        carte_id TEXT,
        nom_carte TEXT,
        rarte_carte TEXT,
        image_url TEXT,
        prix INTEGER
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

        cursor.execute("SELECT objectif, progression, recompense FROM quetes WHERE user_id = ? AND type_quete = 'capture' AND terminee = 0", (user_id_str,))
        quete_en_cours = cursor.fetchone()

        if quete_en_cours:
            obj, prog, recomp = quete_en_cours
            cursor.execute("UPDATE quetes SET progression = MIN(objectif, progression + 1), terminee = CASE WHEN progression + 1 >= objectif THEN 1 ELSE 0 END WHERE user_id = ? AND type_quete = 'capture' AND terminee = 0", (user_id_str,))

            if prog + 1 >= obj:
                cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (recomp, user_id_str))

        conn.commit()

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

@discord_bot.command(name="removemoney")
@commands.has_permissions(administrator=True)
async def removemoney(ctx, member: discord.Member, montant: int):
    get_or_create_user(str(member.id))
    cursor.execute(
        "UPDATE users SET money = MAX(0, money - ?) WHERE user_id = ?",
        (montant, str(member.id)),
    )
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
    cursor.execute("DELETE FROM collection_cartes WHERE user_id = ?", (u_id,))
    cursor.execute("DELETE FROM marche_cartes WHERE user_id = ?", (u_id,))
    conn.commit()
    await ctx.send(f"🌸 Le profil de {member.mention} a été réinitialisé.")


# --- SYSTÈME DE QUÊTES ---
@discord_bot.command(name="quetes")
async def voir_quetes(ctx):
    u_id = str(ctx.author.id)
    get_or_create_user(u_id)
    
    cursor.execute("SELECT type_quete, difficulte, objectif, progression, terminee, recompense FROM quetes WHERE user_id = ?", (u_id,))
    quetes = cursor.fetchall()
    
    if not quetes:
        # Assigner une quête de capture par défaut si aucune n'existe
        cursor.execute("INSERT OR IGNORE INTO quetes (user_id, type_quete, difficulte, objectif, progression, terminee, recompense) VALUES (?, 'capture', 'Facile', 5, 0, 0, 1000)", (u_id,))
        conn.commit()
        cursor.execute("SELECT type_quete, difficulte, objectif, progression, terminee, recompense FROM quetes WHERE user_id = ?", (u_id,))
        quetes = cursor.fetchall()

    embed = discord.Embed(title="📜 Journal des Quêtes Spirituelles", description="Accomplis ces missions pour gagner de l'argent et progresser !", color=0xFFB7C5)
    for q_type, diff, obj, prog, term, recomp in quetes:
        statut = "✅ Terminée" if term == 1 else f"⏳ En cours ({prog}/{obj})"
        embed.add_field(name=f"Quête de {q_type.capitalize()} ({diff})", value=f"Statut : {statut}\n🎁 Récompense : **{recomp}$**", inline=False)
    
    await ctx.send(embed=embed)


# --- SYSTÈME D'HABITATION & PROFIL / BIO ---
@discord_bot.command(name="profil")
async def profil_cmd(ctx, member: discord.Member = None):
    target = member or ctx.author
    u_id = str(target.id)
    u = get_or_create_user(u_id)
    
    embed = discord.Embed(title=f"⛩️ Profil de {target.display_name} ⛩️", description=u["bio"], color=0xFFB7C5)
    embed.add_field(name="💰 Fortune", value=f"{u['money']}$", inline=True)
    embed.add_field(name="🏠 Habitation", value=f"Niv. {u['niv_habitation']} - {u['titre_habitation']}", inline=True)
    embed.add_field(name="🎖️ Badges & Titres", value=u["badges"], inline=False)
    embed.set_thumbnail(url=target.avatar.url if target.avatar else target.default_avatar.url)
    await ctx.send(embed=embed)

@discord_bot.command(name="setbio")
async def setbio(ctx, *, texte: str):
    u_id = str(ctx.author.id)
    get_or_create_user(u_id)
    cursor.execute("UPDATE users SET bio = ? WHERE user_id = ?", (texte, u_id))
    conn.commit()
    await ctx.send("🌸 Ta biographie / histoire de sanctuaire a été mise à jour !")

@discord_bot.command(name="habitation")
async def habitation(ctx):
    u_id = str(ctx.author.id)
    u = get_or_create_user(u_id)
    
    titres_par_niveau = {
        1: "Chambre d'apprenti",
        2: "Pavillon traditionnel",
        3: "Sanctuaire des cerisiers",
        4: "Palais céleste des Yōkai"
    }
    
    prochain_niveau = u["niv_habitation"] + 1
    cout_amelioration = u["niv_habitation"] * 2500
    
    embed = discord.Embed(title=f"🏮 Habitation de {ctx.author.display_name}", description=f"Type actuel : **{u['titre_habitation']}** (Niveau {u['niv_habitation']})", color=0xFFB7C5)
    embed.add_field(name="Amélioration", value=f"Utilise `!ameliorer_habitat` pour passer au niveau supérieur pour **{cout_amelioration}$** !", inline=False)
    await ctx.send(embed=embed)

@discord_bot.command(name="ameliorer_habitat")
async def ameliorer_habitat(ctx):
    u_id = str(ctx.author.id)
    u = get_or_create_user(u_id)
    
    cout = u["niv_habitation"] * 2500
    if u["money"] < cout:
        await ctx.send(f"🌸 Il te faut **{cout}$** pour améliorer ton habitation.")
        return
        
    nouveau_niv = u["niv_habitation"] + 1
    titres = {2: "Pavillon traditionnel", 3: "Sanctuaire des cerisiers", 4: "Palais céleste des Yōkai"}
    nouveau_titre = titres.get(nouveau_niv, "Demeure Légendaire")
    
    cursor.execute("UPDATE users SET money = money - ?, niv_habitation = ?, titre_habitation = ? WHERE user_id = ?", (cout, nouveau_niv, nouveau_titre, u_id))
    conn.commit()
    await ctx.send(f"🎉 Félicitations ! Ton habitation a évolué au niveau {nouveau_niv} : **{nouveau_titre}** !")


# --- SYSTÈME DE CLANS ---
@discord_bot.command(name="creer_clan")
async def creer_clan(ctx, *, nom_clan: str):
    u_id = str(ctx.author.id)
    get_or_create_user(u_id)
    
    cursor.execute("SELECT nom_clan FROM clan_membres WHERE user_id = ?", (u_id,))
    if cursor.fetchone():
        await ctx.send("🌸 Tu fais déjà partie d'un clan !")
        return
        
    cursor.execute("SELECT nom_clan FROM clans WHERE nom_clan = ?", (nom_clan,))
    if cursor.fetchone():
        await ctx.send("🌸 Ce nom de clan existe déjà !")
        return
        
    cursor.execute("INSERT INTO clans (nom_clan, leader, niveau_village, points_village) VALUES (?, ?, 1, 0)", (nom_clan, u_id))
    cursor.execute("INSERT INTO clan_membres (user_id, nom_clan) VALUES (?, ?)", (u_id, nom_clan))
    conn.commit()
    await ctx.send(f"⛩️ Le clan **{nom_clan}** a été fondé avec succès par {ctx.author.mention} !")

@discord_bot.command(name="rejoindre_clan")
async def rejoindre_clan(ctx, *, nom_clan: str):
    u_id = str(ctx.author.id)
    get_or_create_user(u_id)
    
    cursor.execute("SELECT nom_clan FROM clan_membres WHERE user_id = ?", (u_id,))
    if cursor.fetchone():
        await ctx.send("🌸 Tu appartiens déjà à un clan. Quitte-le d'abord si tu veux en changer.")
        return
        
    cursor.execute("SELECT nom_clan FROM clans WHERE nom_clan = ?", (nom_clan,))
    if not cursor.fetchone():
        await ctx.send("🌸 Ce clan n'existe pas.")
        return
        
    cursor.execute("INSERT INTO clan_membres (user_id, nom_clan) VALUES (?, ?)", (u_id, nom_clan))
    conn.commit()
    await ctx.send(f"🌸 {ctx.author.mention} a rejoint le clan **{nom_clan}** !")

@discord_bot.command(name="clan")
async def info_clan(ctx, *, nom_clan: str = None):
    u_id = str(ctx.author.id)
    
    if not nom_clan:
        cursor.execute("SELECT nom_clan FROM clan_membres WHERE user_id = ?", (u_id,))
        res = cursor.fetchone()
        if not res:
            await ctx.send("🌸 Tu n'es dans aucun clan. Utilise `!clan <nom>` ou `!rejoindre_clan <nom>`.")
            return
        nom_clan = res[0]
        
    cursor.execute("SELECT leader, niveau_village, points_village FROM clans WHERE nom_clan = ?", (nom_clan,))
    clan_data = cursor.fetchone()
    if not clan_data:
        await ctx.send("🌸 Clan introuvable.")
        return
        
    leader, niv, pts = clan_data
    cursor.execute("SELECT user_id FROM clan_membres WHERE nom_clan = ?", (nom_clan,))
    membres = cursor.fetchall()
    
    embed = discord.Embed(title=f"⛩️ Clan : {nom_clan}", color=0xFFB7C5)
    embed.add_field(name="👑 Chef", value=f"<@{leader}>", inline=True)
    embed.add_field(name="🏮 Niveau du Village", value=f"Niv. {niv} ({pts} pts)", inline=True)
    embed.add_field(name="👥 Membres", value=f"{len(membres)} membres", inline=False)
    await ctx.send(embed=embed)


# --- SYSTÈME DE CARTES, BOOSTERS ET MARCHÉ (TCG) ---
BOOSTER_TYPES = {
    "standard": {"nom": "Booster Standard", "prix": 500, "description": "Contient des cartes communes et peu communes."},
    "rare": {"nom": "Booster Rare", "prix": 1500, "description": "Contient de fortes chances de cartes rares et holographiques."},
    "celeste": {"nom": "Booster Céleste / Secret", "prix": 5000, "description": "Le pack ultime pour décrocher les cartes secrètes et ultra-rares !"}
}

@discord_bot.command(name="booster_shop")
async def booster_shop(ctx):
    embed = discord.Embed(title="📦 Boutique de Boosters de Cartes", description="Achète des boosters pour collectionner de vraies cartes Pokémon TCG dans ton album !", color=0xFFB7C5)
    for k, v in BOOSTER_TYPES.items():
        embed.add_field(name=f"{v['nom']} (`{k}`)", value=f"💰 Prix : **{v['prix']}$**\n📝 {v['description']}", inline=False)
    embed.set_footer(text="Utilise !acheter_booster <categorie> pour en acquérir un !")
    await ctx.send(embed=embed)

@discord_bot.command(name="acheter_booster")
async def acheter_booster(ctx, categorie: str):
    cat = categorie.lower()
    if cat not in BOOSTER_TYPES:
        await ctx.send("🌸 Catégorie de booster inconnue ! Tape `!booster_shop` pour voir la liste.")
        return
    
    u_id = str(ctx.author.id)
    u = get_or_create_user(u_id)
    prix = BOOSTER_TYPES[cat]["prix"]
    
    if u["money"] < prix:
        await ctx.send(f"🌸 Fonds insuffisants ! Il te faut **{prix}$** pour acheter ce booster.")
        return

    cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (prix, u_id))
    conn.commit()

    carte_num = random.randint(1, 151)
    try:
        url_tcg = f"https://api.tcgdex.net/v2/fr/cards/base1-{carte_num}"
        resp = requests.get(url_tcg)
        if resp.status_code == 200:
            data = resp.json()
            nom_carte = data.get("name", "Pokémon Inconnu")
            rarte_carte = data.get("rarity", "Commune")
            image_url = f"{data.get('image', '')}/high.png" if data.get('image') else f"https://assets.tcgdex.net/fr/base/base1/{carte_num}/high.png"
            carte_id = f"base1-{carte_num}"
        else:
            nom_carte = "Pikachu Promo"
            rarte_carte = "Rare"
            image_url = "https://assets.tcgdex.net/fr/base/base1/58/high.png"
            carte_id = "base1-58"
    except:
        nom_carte = "Dracaufeu Holo"
        rarte_carte = "Ultra-Rare"
        image_url = "https://assets.tcgdex.net/fr/base/base1/4/high.png"
        carte_id = "base1-4"

    cursor.execute("SELECT id, quantite FROM collection_cartes WHERE user_id = ? AND carte_id = ?", (u_id, carte_id))
    existing = cursor.fetchone()
    if existing:
        cursor.execute("UPDATE collection_cartes SET quantite = quantite + 1 WHERE id = ?", (existing[0],))
    else:
        cursor.execute("INSERT INTO collection_cartes (user_id, carte_id, nom_carte, rarte_carte, image_url, quantite) VALUES (?, ?, ?, ?, ?, 1)", 
                       (u_id, carte_id, nom_carte, rarte_carte, image_url))
    conn.commit()

    embed = discord.Embed(
        title=f"✨ Ouverture de {BOOSTER_TYPES[cat]['nom']} ✨",
        description=f"Le paquet s'ouvre... et tu obtiens la carte :\n🏷️ **{nom_carte}** (*Rareté : {rarte_carte}*) !",
        color=0xFFB7C5
    )
    if image_url:
        embed.set_image(url=image_url)
    embed.set_footer(text=f"Ajouté à la collection de {ctx.author.display_name} !")
    await ctx.send(embed=embed)

class AlbumPaginator(discord.ui.View):
    def __init__(self, cartes, member_name):
        super().__init__(timeout=180)
        self.cartes = cartes
        self.member_name = member_name
        self.current_page = 0
        self.max_pages = len(cartes) - 1
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.max_pages

    def create_embed(self):
        carte_actuelle = self.cartes[self.current_page]
        db_id, c_id, nom, rarete, img, qty = carte_actuelle

        embed = discord.Embed(
            title=f"⛩️ Album de Cartes de {self.member_name} (Page {self.current_page + 1}/{self.max_pages + 1})",
            description=f"🏷️ **Nom :** {nom}\n✨ **Rareté :** {rarete}\n📦 **Exemplaires :** x{qty}\n🔑 **ID Album (pour vendre) :** `{db_id}`",
            color=0xFFB7C5
        )
        if img:
            embed.set_image(url=img)
        embed.set_footer(text=f"Réf Carte : {c_id}")
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

@discord_bot.command(name="album")
async def album_cmd(ctx, member: discord.Member = None):
    target = member or ctx.author
    cursor.execute("SELECT id, carte_id, nom_carte, rarte_carte, image_url, quantite FROM collection_cartes WHERE user_id = ?", (str(target.id),))
    cartes = cursor.fetchall()
    
    if not cartes:
        await ctx.send(f"🌸 {target.mention} n'a aucune carte dans son album ! Utilise `!booster_shop` pour en acheter.")
        return
        
    view = AlbumPaginator(cartes, target.display_name)
    await ctx.send(embed=view.create_embed(), view=view)

@discord_bot.command(name="afficher")
async def afficher_cartes(ctx, *ids: int):
    if not ids:
        await ctx.send("🌸 Tu dois indiquer les ID de tes cartes à afficher ! (Ex: `!afficher 1 3 5`)")
        return
    
    if len(ids) > 5:
        await ctx.send("🌸 Tu peux afficher un maximum de 5 cartes en même temps !")
        return

    u_id = str(ctx.author.id)
    placeholders = ','.join(['?'] * len(ids))
    query = f"SELECT id, nom_carte, rarte_carte, image_url, quantite FROM collection_cartes WHERE user_id = ? AND id IN ({placeholders})"
    
    cursor.execute(query, [u_id] + list(ids))
    cartes_trouvees = cursor.fetchall()

    if not cartes_trouvees:
        await ctx.send("🌸 Aucune carte valide trouvée avec ces ID dans ton album.")
        return

    embed = discord.Embed(
        title=f"✨ Vitrine de Cartes de {ctx.author.display_name} ✨",
        description="Voici un aperçu des cartes sélectionnées depuis son album :",
        color=0xFFB7C5
    )

    for db_id, nom, rarete, img, qty in cartes_trouvees:
        embed.add_field(
            name=f"🏷️ [{db_id}] {nom}",
            value=f"Rareté : {rarete} | x{qty}",
            inline=True
        )

    if cartes_trouvees[0][3]:
        embed.set_image(url=cartes_trouvees[0][3])

    await ctx.send(embed=embed)

@discord_bot.command(name="vendre")
async def vendre_carte(ctx, album_id: str, prix: int):
    if not album_id.isdigit():
        await ctx.send("🌸 Erreur : L'ID de l'album doit être un **nombre entier** (ex: `1`, `2`, `12`) et non la référence de la carte.")
        return

    album_id_int = int(album_id)

    if prix <= 0:
        await ctx.send("🌸 Le prix de vente doit être supérieur à 0 $ !")
        return

    u_id = str(ctx.author.id)
    cursor.execute("SELECT carte_id, nom_carte, rarte_carte, image_url, quantite FROM collection_cartes WHERE id = ? AND user_id = ?", (album_id_int, u_id))
    carte = cursor.fetchone()

    if not carte:
        await ctx.send("🌸 Carte introuvable dans ton album avec cet ID !")
        return

    c_id, nom, rarete, img, qty = carte

    if qty > 1:
        cursor.execute("UPDATE collection_cartes SET quantite = quantite - 1 WHERE id = ?", (album_id_int,))
    else:
        cursor.execute("DELETE FROM collection_cartes WHERE id = ?", (album_id_int,))

    cursor.execute("INSERT INTO marche_cartes (user_id, carte_id, nom_carte, rarte_carte, image_url, prix) VALUES (?, ?, ?, ?, ?, ?)",
                   (u_id, c_id, nom, rarete, img, prix))
    conn.commit()

    await ctx.send(f"🌸 Ta carte **{nom}** ({rarete}) a été mise en vente sur le marché pour **{prix}$** !")

@discord_bot.command(name="marche")
async def voir_marche(ctx):
    cursor.execute("SELECT vente_id, user_id, nom_carte, rarte_carte, prix FROM marche_cartes")
    ventes = cursor.fetchall()

    if not ventes:
        await ctx.send("⛩️ Le marché des cartes est actuellement vide.")
        return

    embed = discord.Embed(title="⛩️ Marché des Cartes (Hôtel des Ventes) ⛩️", description="Achète des cartes mises en vente par d'autres joueurs avec `!acheter_carte <id_vente>`", color=0xFFB7C5)
    
    for v_id, vendeur_id, nom, rarete, prix in ventes:
        embed.add_field(
            name=f"🏷️ [{v_id}] {nom} ({rarete})",
            value=f"💰 Prix : **{prix}$**\n👤 Vendeur : <@{vendeur_id}>",
            inline=False
        )
    await ctx.send(embed=embed)

@discord_bot.command(name="acheter_carte")
async def acheter_carte(ctx, vente_id: int):
    u_id = str(ctx.author.id)
    
    cursor.execute("SELECT user_id, carte_id, nom_carte, rarte_carte, image_url, prix FROM marche_cartes WHERE vente_id = ?", (vente_id,))
    vente = cursor.fetchone()

    if not vente:
        await ctx.send("🌸 Cette offre de vente n'existe plus ou a déjà été achetée.")
        return

    vendeur_id, c_id, nom, rarete, img, prix = vente

    if vendeur_id == u_id:
        await ctx.send("🌸 Tu ne peux pas acheter ta propre carte !")
        return

    acheteur_data = get_or_create_user(u_id)
    if acheteur_data["money"] < prix:
        await ctx.send(f"🌸 Fonds insuffisants ! Il te faut **{prix}$** pour acheter cette carte.")
        return

    cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (prix, u_id))
    cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (prix, vendeur_id))
    cursor.execute("DELETE FROM marche_cartes WHERE vente_id = ?", (vente_id,))

    cursor.execute("SELECT id, quantite FROM collection_cartes WHERE user_id = ? AND carte_id = ?", (u_id, c_id))
    existing = cursor.fetchone()
    if existing:
        cursor.execute("UPDATE collection_cartes SET quantite = quantite + 1 WHERE id = ?", (existing[0],))
    else:
        cursor.execute("INSERT INTO collection_cartes (user_id, carte_id, nom_carte, rarte_carte, image_url, quantite) VALUES (?, ?, ?, ?, ?, 1)",
                       (u_id, c_id, nom, rarete, img))
    conn.commit()

    embed = discord.Embed(
        title="🎉 Achat réussi sur le Marché !",
        description=f"Tu as acheté **{nom}** ({rarete}) à <@{vendeur_id}> pour **{prix}$** !",
        color=0xFFB7C5
    )
    if img:
        embed.set_image(url=img)
    await ctx.send(embed=embed)

@discord_bot.command(name="retirer_vente")
async def retirer_vente(ctx, vente_id: int):
    u_id = str(ctx.author.id)
    cursor.execute("SELECT carte_id, nom_carte, rarte_carte, image_url FROM marche_cartes WHERE vente_id = ? AND user_id = ?", (vente_id, u_id))
    vente = cursor.fetchone()

    if not vente:
        await ctx.send("🌸 Offre introuvable ou cette carte ne t'appartient pas.")
        return

    c_id, nom, rarete, img = vente
    cursor.execute("DELETE FROM marche_cartes WHERE vente_id = ?", (vente_id,))

    cursor.execute("SELECT id, quantite FROM collection_cartes WHERE user_id = ? AND carte_id = ?", (u_id, c_id))
    existing = cursor.fetchone()
    if existing:
        cursor.execute("UPDATE collection_cartes SET quantite = quantite + 1 WHERE id = ?", (existing[0],))
    else:
        cursor.execute("INSERT INTO collection_cartes (user_id, carte_id, nom_carte, rarte_carte, image_url, quantite) VALUES (?, ?, ?, ?, ?, 1)",
                       (u_id, c_id, nom, rarete, img))
    conn.commit()
    await ctx.send(f"🌸 Ta carte **{nom}** a été retirée du marché et replacée dans ton album.")

# --- LANCEMENT DU BOT ET DU SERVEUR WEB ---
if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    discord_bot.run('TON_TOKEN_DISCORD')
