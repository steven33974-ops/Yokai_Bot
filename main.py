import discord
from discord.ext import commands

# Configuration du bot avec les intents nécessaires
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
    """Affiche le grimoire d'aide réservé aux administrateurs."""
    embed = discord.Embed(title="🛡️ Grimoire Admin", color=discord.Color.red())
    embed.add_field(name="Commandes", value="`!setchannel`, `!settime`, `!pop`, `!addmoney`, `!removemoney`, `!resetplayer`, `!givepokemon`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="setchannel")
@commands.has_permissions(administrator=True)
async def setchannel(ctx, salon: discord.TextChannel = None):
    salon_cible = salon or ctx.channel
    await ctx.send(f"⛩️ Le salon {salon_cible.mention} est désormais le sanctuaire officiel des esprits.")

@bot.command(name="settime")
@commands.has_permissions(administrator=True)
async def settime(ctx, minutes: float):
    await ctx.send(f"⏳ Intervalle d'apparition réglé à {minutes} minutes.")

@bot.command(name="pop")
@commands.has_permissions(administrator=True)
async def pop(ctx):
    await ctx.send("✨ Une distorsion dimensionnelle provoque l'apparition immédiate d'un esprit sauvage !")

@bot.command(name="addmoney")
@commands.has_permissions(administrator=True)
async def addmoney(ctx, membre: discord.Member, montant: int):
    await ctx.send(f"💰 {montant}$ ont été offerts à {membre.mention}.")

@bot.command(name="removemoney")
@commands.has_permissions(administrator=True)
async def removemoney(ctx, membre: discord.Member, montant: int):
    await ctx.send(f"💸 {montant}$ ont été prélevés à {membre.mention}.")

@bot.command(name="resetplayer")
@commands.has_permissions(administrator=True)
async def resetplayer(ctx, membre: discord.Member):
    await ctx.send(f"⚠️ Le profil de {membre.mention} a été entièrement réinitialisé.")

@bot.command(name="givepokemon")
@commands.has_permissions(administrator=True)
async def givepokemon(ctx, membre: discord.Member, nom: str, shiny: bool = False):
    statut = "Shiny/Divine" if shiny else "normal"
    await ctx.send(f"🎁 Un esprit {nom} ({statut}) a été confié à {membre.mention}.")


# ==========================================
# 👤 2. INVENTAIRE, PROFIL & ÉQUIPE
# ==========================================

@bot.command(name="profil")
async def profil(ctx, membre: discord.Member = None):
    cible = membre or ctx.author
    await ctx.send(f"📜 Affichage du profil et de la carte d'identité de {cible.mention}.")

@bot.command(name="inv")
async def inv(ctx, membre: discord.Member = None):
    cible = membre or ctx.author
    await ctx.send(f"🌸 Ouverture du clan d'esprits (Pokédex) de {cible.mention}.")

@bot.group(name="equipe", invoke_without_command=True)
async def equipe(ctx):
    await ctx.send("Utilise `!equipe creer` ou `!equipe voir [@membre]`.")

@equipe.command(name="creer")
async def equipe_creer(ctx):
    await ctx.send("✨ Formulaire interactif ouvert pour sceller vos 3 Yōkai principaux.")

@equipe.command(name="voir")
async def equipe_voir(ctx, membre: discord.Member = None):
    cible = membre or ctx.author
    await ctx.send(f"🛡️ Composition de l'équipe de combat de {cible.mention}.")

@bot.command(name="top")
async def top(ctx):
    await ctx.send("🏆 Classement des dresseurs les plus fortunés du serveur.")


# ==========================================
# 🎁 3. BOUTIQUE, OBJETS & CHASSE
# ==========================================

@bot.command(name="daily")
async def daily(ctx):
    await ctx.send(f"🎁 {ctx.author.mention}, voici votre offrande journalière (150$, 3 Pokéballs et 1 Bonbon) !")

@bot.command(name="shop")
async def shop(ctx):
    await ctx.send("🛍️ Bienvenue à la boutique mystique ! Articles disponibles : Balls, Potions, Bonbons.")

@bot.command(name="buy")
async def buy(ctx, article: str, quantite: int = 1):
    await ctx.send(f"🛒 Achat de {quantite}x {article} effectué avec succès.")

@bot.command(name="feed", aliases=["use"])
async def feed(ctx, id_esprit: int):
    await ctx.send(f"🍬 Votre esprit (ID : {id_esprit}) a été nourri et gagne de l'expérience !")

@bot.command(name="trade")
async def trade(ctx, membre: discord.Member, id_1: int, id_2: int):
    await ctx.send(f"🤝 Demande d'échange lancée avec {membre.mention} (Esprits ID : {id_1} <-> {id_2}).")


# ==========================================
# ⚔️ 4. COMBATS & DUELS
# ==========================================

@bot.command(name="duel")
async def duel(ctx, adversaire: discord.Member, mise: int = 0):
    await ctx.send(f"⚔️ {ctx.author.mention} défie {adversaire.mention} en duel dans l'arène (Mise : {mise}$) !")

@bot.command(name="ia")
async def ia(ctx):
    await ctx.send("🤖 L'entraînement contre le dresseur virtuel commence !")

@bot.command(name="champion")
async def champion(ctx):
    await ctx.send("🐉 Affrontement suprême engagé contre le Boss légendaire du sanctuaire.")


# ==========================================
# ✨ 5. QUÊTES, HISTOIRE & DESTINÉES
# ==========================================

@bot.command(name="histoire")
async def histoire(ctx, *, texte: str = None):
    if texte:
        await ctx.send("📖 Votre background / récit a été mis à jour.")
    else:
        await ctx.send("📖 Lecture de votre récit personnel.")

@bot.command(name="quetes")
async def quetes(ctx):
    await ctx.send("📜 Journal de vos missions spirituelles en cours.")

@bot.command(name="prendre_quete")
async def prendre_quete(ctx, difficulte: str):
    await ctx.send(f"🎯 Quête de niveau **{difficulte}** acceptée ! Préparez la chasse.")

@bot.command(name="recompense")
async def recompense(ctx):
    await ctx.send("🎁 Récompense de quête récupérée avec succès !")


# ==========================================
# ⛩️ 6. CLANS, VILLAGES & HABITATIONS
# ==========================================

@bot.group(name="clan", invoke_without_command=True)
async def clan(ctx):
    await ctx.send("⛩️ Commandes clan : `!clan creer <nom>`, `!clan rejoindre <nom>`, `!clan infos`, `!clan investir`, `!clan village`.")

@clan.command(name="creer")
async def clan_creer(ctx, *, nom: str):
    await ctx.send(f"⛩️ Le clan **{nom}** a été fondé ! Vous en êtes le Chef suprême.")

@clan.command(name="rejoindre")
async def clan_rejoindre(ctx, *, nom: str):
    await ctx.send(f"🌸 Vous avez rejoint les rangs du clan **{nom}**.")

@clan.command(name="infos", aliases=["info"])
async def clan_infos(ctx):
    await ctx.send("📊 Informations et statistiques de votre clan.")

@clan.command(name="investir")
async def clan_investir(ctx, montant: int):
    await ctx.send(f"💰 Investissement de {montant}$ validé pour faire prospérer le village du clan.")

@clan.command(name="village")
async def clan_village(ctx):
    await ctx.send("🏰 État actuel de la citadelle et barre de progression.")

@bot.command(name="classement")
async def classement(ctx):
    await ctx.send("🏅 Panthéon des meilleurs clans du serveur.")

@bot.group(name="habitation", invoke_without_command=True)
async def habitation(ctx):
    await ctx.send("🏠 Utilisez `!habitation voir` ou `!habitation ameliorer`.")

@habitation.command(name="voir")
async def habitation_voir(ctx):
    await ctx.send("🏡 Standing de votre demeure actuelle et jauge de progression.")

@habitation.command(name="ameliorer")
async def habitation_ameliorer(ctx):
    await ctx.send("✨ Votre foyer s'élève vers un nouveau palier de prestige !")


# ==========================================
# 🃏 7. ARCHIVES DU TCG (CARTES)
# ==========================================

@bot.command(name="booster_shop")
async def booster_shop(ctx):
    await ctx.send("📦 Boutique de boosters : Standard (500$), Rare (1500$), Céleste (5000$).")

@bot.command(name="acheter_booster")
async def acheter_booster(ctx, type_booster: str):
    await ctx.send(f"✨ Achat d'un booster **{type_booster}** ouvert avec succès !")

@bot.command(name="album")
async def album(ctx, membre: discord.Member = None):
    cible = membre or ctx.author
    await ctx.send(f"📖 Ouverture de l'album de cartes de {cible.mention}.")

@bot.command(name="afficher")
async def afficher(ctx, *ids: int):
    cartes = ", ".join(map(str, ids))
    await ctx.send(f"🖼️ Vitrine de cartes exposée (IDs : {cartes}).")

@bot.command(name="marche")
async def marche(ctx):
    await ctx.send("🏪 Hôtel des ventes : voici les cartes actuellement en vente par les joueurs.")

@bot.command(name="vendre")
async def vendre(ctx, id_album: int, prix: int):
    await ctx.send(f"🏷️ Carte (ID album : {id_album}) mise en vente sur le marché pour {prix}$.")

@bot.command(name="acheter_carte")
async def acheter_carte(ctx, id_vente: int):
    await ctx.send(f"💸 Achat de la carte (Vente ID : {id_vente}) réussi !")

@bot.command(name="retirer_vente")
async def retirer_vente(ctx, id_vente: int):
    await ctx.send(f"🔄 Vente annulée, la carte (ID : {id_vente}) a réintégré votre album.")

# Lancement du bot (Remplacez 'VOTRE_TOKEN' par votre vrai token Discord)
# bot.run("VOTRE_TOKEN")
