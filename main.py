import os
import threading
from flask import Flask
import discord
from discord.ext import commands

# 1. Mini-serveur Flask pour satisfaire Render (Service Web)
app = Flask(__name__)

@app.route('/')
def home():
    return "Le sanctuaire des Yōkai est en ligne ! 🌸"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# 2. Configuration du Bot Discord
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Le sanctuaire est éveillé : {bot.user.name} est en ligne ! 🌸")

# ==========================================
# 🛠️ 1. PANNEAU DE CONTRÔLE ADMIN
# ==========================================

@bot.command(name="adminhelp")
@commands.has_permissions(administrator=True)
async def adminhelp(ctx):
    embed = discord.Embed(title="🛡️ Grimoire Admin", color=discord.Color.red())
    embed.add_field(name="Commandes", value="`!setchannel`, `!settime`, `!pop`, `!addmoney`, `!removemoney`, `!resetplayer`, `!givepokemon`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="setchannel")
@commands.has_permissions(administrator=True)
async def setchannel(ctx, salon: discord.TextChannel = None):
    salon_cible = salon or ctx.channel
    embed = discord.Embed(title="⛩️ Configuration du Salon", description=f"Le salon {salon_cible.mention} est désormais le sanctuaire officiel des esprits.", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="settime")
@commands.has_permissions(administrator=True)
async def settime(ctx, minutes: float):
    embed = discord.Embed(title="⏳ Intervalle d'Apparition", description=f"Intervalle réglé à **{minutes}** minutes.", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="pop")
@commands.has_permissions(administrator=True)
async def pop(ctx):
    embed = discord.Embed(title="✨ Distorsion Dimensionnelle", description="Une distorsion dimensionnelle provoque l'apparition immédiate d'un esprit sauvage !", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="addmoney")
@commands.has_permissions(administrator=True)
async def addmoney(ctx, membre: discord.Member, montant: int):
    embed = discord.Embed(title="💰 Offrande Divine", description=f"**{montant}$** ont été offerts à {membre.mention}.", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="removemoney")
@commands.has_permissions(administrator=True)
async def removemoney(ctx, membre: discord.Member, montant: int):
    embed = discord.Embed(title="💸 Prélèvement du Sanctuaire", description=f"**{montant}$** ont été prélevés à {membre.mention}.", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="resetplayer")
@commands.has_permissions(administrator=True)
async def resetplayer(ctx, membre: discord.Member):
    embed = discord.Embed(title="⚠️ Réinitialisation", description=f"Le profil de {membre.mention} a été entièrement réinitialisé.", color=0xFF0000)
    await ctx.send(embed=embed)

@bot.command(name="givepokemon")
@commands.has_permissions(administrator=True)
async def givepokemon(ctx, membre: discord.Member, nom: str, shiny: bool = False):
    statut = "Shiny/Divine" if shiny else "normal"
    embed = discord.Embed(title="🎁 Don d'Esprit", description=f"Un esprit **{nom}** (*{statut}*) a été confié à {membre.mention}.", color=0xFF69B4)
    await ctx.send(embed=embed)


# ==========================================
# 👤 2. INVENTAIRE, PROFIL & ÉQUIPE
# ==========================================

@bot.command(name="profil")
async def profil(ctx, membre: discord.Member = None):
    cible = membre or ctx.author
    embed = discord.Embed(title=f"⛩️ Profil de 🌸🌸 {cible.display_name} 🌸🌸 ⛩️", color=0xFF69B4)
    embed.add_field(name="💰 Argent", value="900250$", inline=True)
    embed.add_field(name="📖 Esprits", value="3 (Niveau cumulé: 3)", inline=True)
    embed.add_field(name="🏠 Habitation", value="Niv.1/10000 - Chambre d'apprenti", inline=False)
    embed.add_field(name="🏆 Badges", value="Novice du Sanctuaire", inline=False)
    embed.add_field(name="📜 Histoire", value="Aucune histoire écrite pour l'instant...", inline=False)
    embed.add_field(name="🎒 Inventaire", value="🔴 x1001 | 🔵 x0 | 🟣 x0 | 🟡 x0\n🍬 Bonbons: 0 | 🧪 Potions: 0", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="inv")
async def inv(ctx, membre: discord.Member = None):
    cible = membre or ctx.author
    embed = discord.Embed(title=f"🌸 Clan d'esprits de {cible.display_name}", description="Liste des esprits et cartes possédées dans le clan.", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.group(name="equipe", invoke_without_command=True)
async def equipe(ctx):
    embed = discord.Embed(title="🛡️ Gestion de l'Équipe", description="Utilise `!equipe creer` ou `!equipe voir [@membre]`.", color=0xFF69B4)
    await ctx.send(embed=embed)

@equipe.command(name="creer")
async def equipe_creer(ctx):
    embed = discord.Embed(title="✨ Formulaire d'Équipe", description="Formulaire interactif ouvert pour sceller vos 3 Yōkai principaux.", color=0xFF69B4)
    await ctx.send(embed=embed)

@equipe.command(name="voir")
async def equipe_voir(ctx, membre: discord.Member = None):
    cible = membre or ctx.author
    embed = discord.Embed(title=f"🛡️ Équipe de {cible.display_name}", description="Composition de l'équipe de combat actuelle.", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="top")
async def top(ctx):
    embed = discord.Embed(title="🏆 Classement des Dresseurs", description="Classement des dresseurs les plus fortunés du serveur.", color=0xFFD700)
    await ctx.send(embed=embed)


# ==========================================
# 🎁 3. BOUTIQUE, OBJETS & CHASSE
# ==========================================

@bot.command(name="daily")
async def daily(ctx):
    embed = discord.Embed(title="🎁 Offrande Journalière", description=f"{ctx.author.mention}, voici votre offrande journalière (**150$**, **3 Pokéballs** et **1 Bonbon**) !", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="shop")
async def shop(ctx):
    embed = discord.Embed(title="🛍️ Boutique Mystique", description="Articles disponibles : Balls, Potions, Bonbons.", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="buy")
async def buy(ctx, article: str, quantite: int = 1):
    embed = discord.Embed(title="🛒 Achat Validé", description=f"Achat de **{quantite}x {article}** effectué avec succès.", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="feed", aliases=["use"])
async def feed(ctx, id_esprit: int):
    embed = discord.Embed(title="🍬 Repas Spirituel", description=f"Votre esprit (ID : **{id_esprit}**) a été nourri et gagne de l'expérience !", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="trade")
async def trade(ctx, membre: discord.Member, id_1: int, id_2: int):
    embed = discord.Embed(title="🤝 Pacte d'Échange", description=f"Demande d'échange lancée avec {membre.mention} (Esprits ID : **{id_1} <-> {id_2}**).", color=0xFF69B4)
    await ctx.send(embed=embed)


# ==========================================
# ⚔️ 4. COMBATS & DUELS
# ==========================================

@bot.command(name="duel")
async def duel(ctx, adversaire: discord.Member, mise: int = 0):
    embed = discord.Embed(title="⚔️ Arène des Duels", description=f"{ctx.author.mention} défie {adversaire.mention} en duel dans l'arène (Mise : **{mise}$**) !", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="ia")
async def ia(ctx):
    embed = discord.Embed(title="🤖 Entraînement Virtuel", description="L'entraînement contre le dresseur virtuel commence !", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="champion")
async def champion(ctx):
    embed = discord.Embed(title="🐉 Affrontement Suprême", description="Affrontement engagé contre le Boss légendaire du sanctuaire.", color=0xFF69B4)
    await ctx.send(embed=embed)


# ==========================================
# ✨ 5. QUÊTES, HISTOIRE & DESTINÉES
# ==========================================

@bot.command(name="histoire")
async def histoire(ctx, *, texte: str = None):
    if texte:
        embed = discord.Embed(title="📖 Destinée", description="Votre background / récit a été mis à jour avec succès.", color=0xFF69B4)
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title="📖 Chroniques", description="Lecture de votre récit personnel.", color=0xFF69B4)
        await ctx.send(embed=embed)

@bot.command(name="quetes")
async def quetes(ctx):
    embed = discord.Embed(title="⛩️ Quêtes et Défis de 🌸🌸 YokaiiiFox 🌸🌸", color=0xFF69B4)
    embed.add_field(name="Voici l'état d'avancement de tes missions :", value="🟢 [Facile] Mission : Chasseur d'Esprits\n✅ Terminée !\n\nRelève les défis les plus durs pour de plus grandes récompenses !", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="prendre_quete")
async def prendre_quete(ctx, difficulte: str):
    embed = discord.Embed(title="📜 Nouvelle mission acceptée !", description=f"{ctx.author.mention} s'est lancé dans un défi **{difficulte}**.\n🎯 **Objectif** : Capturer 3 esprits.\n💰 **Récompense** : 1000$ !\n\nUtilise `!quetes` pour suivre ta progression.", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="recompense")
async def recompense(ctx):
    embed = discord.Embed(title="🎁 Trésor du Sanctuaire", description="Récompense de quête récupérée avec succès !", color=0xFF69B4)
    await ctx.send(embed=embed)


# ==========================================
# ⛩️ 6. CLANS, VILLAGES & HABITATIONS
# ==========================================

@bot.group(name="clan", invoke_without_command=True)
async def clan(ctx):
    embed = discord.Embed(title="⛩️ Gestion des Clans", description="Commandes : `!clan creer <nom>`, `!clan rejoindre <nom>`, `!clan infos`, `!clan investir`, `!clan village`.", color=0xFF69B4)
    await ctx.send(embed=embed)

@clan.command(name="creer")
async def clan_creer(ctx, *, nom: str):
    embed = discord.Embed(title="⛩️ Fondation d'un Clan", description=f"Le clan **{nom}** a été fondé avec succès par {ctx.author.mention} !", color=0xFF69B4)
    await ctx.send(embed=embed)

@clan.command(name="rejoindre")
async def clan_rejoindre(ctx, *, nom: str):
    embed = discord.Embed(title="⛩️ Nouveau Membre", description=f"{ctx.author.mention} a rejoint le clan **{nom}** !", color=0xFF69B4)
    await ctx.send(embed=embed)

@clan.command(name="infos", aliases=["info"])
async def clan_infos(ctx):
    embed = discord.Embed(title="📊 Archives du Clan", description="Informations et statistiques globales de votre clan.", color=0xFF69B4)
    await ctx.send(embed=embed)

@clan.command(name="investir")
async def clan_investir(ctx, montant: int):
    embed = discord.Embed(title="💰 Prospérité du Village", description=f"Investissement de **{montant}$** validé pour faire prospérer le village du clan.", color=0xFF69B4)
    await ctx.send(embed=embed)

@clan.command(name="village")
async def clan_village(ctx):
    embed = discord.Embed(title="🏰 Citadelle du Clan", description="État actuel de la citadelle et barre de progression.", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="classement")
async def classement(ctx):
    embed = discord.Embed(title="🏆 Classement des Clans - Yokai_Bot", color=0xFFD700)
    embed.add_field(name="🏅 Podiums", value="🥇 🌸 -> CLAN DES YŌKAI <- 🌸 (Village Niv.1) — `0 points`", inline=False)
    embed.set_footer(text="Continuez à faire progresser vos villages pour atteindre le sommet !")
    await ctx.send(embed=embed)

@bot.group(name="habitation", invoke_without_command=True)
async def habitation(ctx):
    embed = discord.Embed(title="🏠 Sanctuaire Intérieur", description="Utilisez `!habitation voir` ou `!habitation ameliorer`.", color=0xFF69B4)
    await ctx.send(embed=embed)

@habitation.command(name="voir")
async def habitation_voir(ctx):
    embed = discord.Embed(title="⛩️ Foyer de 🌸🌸 YokaiiiFox 🌸🌸 ⛩️", color=0xFF69B4)
    embed.add_field(name="🏠 Titre actuel", value="Chambre d'apprenti", inline=False)
    embed.add_field(name="📈 Niveau du foyer", value="Niv. 1 / 10000", inline=False)
    embed.add_field(name="📜 Histoire de la demeure", value="Aucune histoire écrite pour l'instant...\nTape `!habitation ameliorer` pour élever ton sanctuaire !", inline=False)
    await ctx.send(embed=embed)

@habitation.command(name="ameliorer")
async def habitation_ameliorer(ctx):
    embed = discord.Embed(title="✨ Élévation du Foyer", description="Votre foyer s'élève vers un nouveau palier de prestige !", color=0xFF69B4)
    await ctx.send(embed=embed)


# ==========================================
# 🃏 7. ARCHIVES DU TCG (CARTES)
# ==========================================

@bot.command(name="booster_shop")
async def booster_shop(ctx):
    embed = discord.Embed(title="📦 Boutique de Boosters", description="Standards (500$), Rares (1500$), Célestes (5000$).", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="acheter_booster")
async def acheter_booster(ctx, type_booster: str):
    embed = discord.Embed(title="✨ Ouverture de Booster", description=f"Achat d'un booster **{type_booster}** ouvert avec succès !", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="album")
async def album(ctx, membre: discord.Member = None):
    cible = membre or ctx.author
    embed = discord.Embed(title=f"📖 Album de Cartes", description=f"Ouverture de l'album de cartes de {cible.mention}.", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="afficher")
async def afficher(ctx, *ids: int):
    cartes = ", ".join(map(str, ids))
    embed = discord.Embed(title="🖼️ Vitrine des Esprits", description=f"Cartes exposées (IDs : **{cartes}**).", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="marche")
async def marche(ctx):
    embed = discord.Embed(title="🏪 Hôtel des Ventes", description="Voici les cartes actuellement en vente par les joueurs.", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="vendre")
async def vendre(ctx, id_album: int, prix: int):
    embed = discord.Embed(title="🏷️ Annonce de Vente", description=f"Carte (ID album : **{id_album}**) mise en vente sur le marché pour **{prix}$**.", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="acheter_carte")
async def acheter_carte(ctx, id_vente: int):
    embed = discord.Embed(title="💸 Acquisition Réussie", description=f"Achat de la carte (Vente ID : **{id_vente}**) réussi avec succès !", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="retirer_vente")
async def retirer_vente(ctx, id_vente: int):
    embed = discord.Embed(title="🔄 Annulation de Vente", description=f"Vente annulée, la carte (ID : **{id_vente}**) a réintégré votre album.", color=0xFF69B4)
    await ctx.send(embed=embed)


if __name__ == "__main__":
    # Lancement du serveur web Flask dans un thread séparé pour Render
    threading.Thread(target=run_web).start()
    
    # Récupération du token depuis les variables d'environnement de Render
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ Erreur : Le token Discord (DISCORD_TOKEN) n'est pas défini dans les variables d'environnement !")
