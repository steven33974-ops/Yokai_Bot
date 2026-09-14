import os
import threading
import random
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
# 🎁 SYSTÈME DE CAPTURE AVEC BOUTONS & ALÉATOIRE (1025 POKÉMON)
# ==========================================

POKEMONS_SAUVAGES = list(range(1, 1026))

class CaptureView(discord.ui.View):
    def __init__(self, poke_id):
        super().__init__(timeout=30)
        self.poke_id = poke_id
        self.captured = False

    async def tenter_capture(self, interaction: discord.Interaction, nom_ball: str, taux_reussite: float):
        if self.captured:
            await interaction.response.send_message("❌ Cet esprit a déjà été capturé !", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True

        if random.random() < taux_reussite:
            self.captured = True
            embed = interaction.message.embeds[0]
            embed.color = 0x00FF00
            embed.set_footer(text=f"🏮 Capturé avec succès par {interaction.user.display_name} !")
            
            await interaction.response.edit_message(embed=embed, view=self)
            await interaction.followup.send(f"✨ **Bravo {interaction.user.mention} !** Tu as réussi à capturer l'esprit **n°{self.poke_id}** avec une {nom_ball} ! 🌸")
        else:
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(f"💨 Oh non ! L'esprit **n°{self.poke_id}** a esquivé la {nom_ball} de {interaction.user.mention} et s'est échappé dans les bois...", ephemeral=False)

    @discord.ui.button(label="Pokéball", style=discord.ButtonStyle.danger)
    async def pokeball(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.tenter_capture(interaction, "Pokéball", 0.40)

    @discord.ui.button(label="Superball", style=discord.ButtonStyle.primary)
    async def superball(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.tenter_capture(interaction, "Superball", 0.65)

    @discord.ui.button(label="Hyperball", style=discord.ButtonStyle.secondary)
    async def hyperball(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.tenter_capture(interaction, "Hyperball", 0.85)

    @discord.ui.button(label="Masterball", style=discord.ButtonStyle.success)
    async def masterball(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.tenter_capture(interaction, "Masterball", 1.00)


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
    poke_id = random.choice(POKEMONS_SAUVAGES)
    
    embed = discord.Embed(
        title="🌸 — [ ⛩️ JARDIN DES SAKURAS ⛩️ ] — 🌸",
        description=(
            "Un esprit sauvage émerge des cerisiers...\n"
            f"**Esprit # {poke_id}**\n"
            f"🔮 Identifiant dimensionnel n°{poke_id}\n\n"
            "_Clique sur une Ball pour tenter la capture !_"
        ),
        color=0xFF69B4
    )
    embed.set_image(url=f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{poke_id}.png")
    embed.set_footer(text="🏮 Voie des Esprits • Tu as 30 secondes pour le capturer !")
    await ctx.send(embed=embed, view=CaptureView(poke_id))

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
# 🃏 7. ARCHIVES DU TCG (CARTES AVEC CADRES & CLASSES)
# ==========================================

# Base de données simulée des cartes avec leurs différentes classes/raretés et liens d'images avec cadre
CLASSES_CARTES = {
    "standard": {"nom": "Commune / Peu Commune", "couleur": 0xCCCCCC},
    "rare": {"nom": "Rare Brillante", "couleur": 0xFFD700},
    "celeste": {"nom": "Céleste / Ultra-Rare", "couleur": 0xFF69B4}
}

class AlbumView(discord.ui.View):
    def __init__(self, cartes_utilisateur, membre):
        super().__init__(timeout=60)
        self.cartes = cartes_utilisateur
        self.membre = membre
        self.page = 0

    @discord.ui.button(label="◀️ Précédent", style=discord.ButtonStyle.secondary)
    precedent_btn = discord.ui.button(label="◀️ Précédent", style=discord.ButtonStyle.secondary)
    
    # (Tu peux utiliser une vue paginée pour feuilleter l'album de cartes des joueurs)

@bot.command(name="booster_shop")
async def booster_shop(ctx):
    embed = discord.Embed(
        title="📦 Boutique de Boosters TCG",
        description=(
            "Achète des paquets pour remplir ton album et collectionner toutes les cartes avec leurs cadres !\n\n"
            "🏷️ **Standard** (500$) : Idéal pour débuter (communes/peu communes).\n"
            "🟣 **Rare** (1500$) : Meilleures chances de cartes brillantes.\n"
            "✨ **Céleste** (5000$) : Le pack ultime pour les ultra-rares !"
        ),
        color=0xFF69B4
    )
    await ctx.send(embed=embed)

@bot.command(name="acheter_booster")
async def acheter_booster(ctx, type_booster: str):
    type_booster = type_booster.lower()
    if type_booster not in ["standard", "rare", "celeste"]:
        await ctx.send("❌ Type de booster invalide ! Choisis entre `standard`, `rare` ou `celeste`.", ephemeral=True)
        return

    # Simulation d'un tirage aléatoire d'un Pokémon parmi les 1025 avec son cadre
    poke_id = random.choice(POKEMONS_SAUVAGES)
    
    embed = discord.Embed(
        title=f"✨ Ouverture de Booster {type_booster.capitalize()} ✨",
        description=f"Le paquet s'ouvre... et tu obtiens la carte :\n🏷️ **Mewtwo** (*Rareté : {type_booster.capitalize()}*)\n\n_Classe d'artefact scellée avec son cadre authentique._",
        color=0xFFD700
    )
    # Intègre l'image avec le cadre rétro comme sur ton modèle
    embed.set_image(url="https://images.pokemontcg.io/base1/10_hires.png") # Exemple avec le cadre officiel rétro
    embed.set_footer(text=f"Ajouté à la collection de 🌸 ⛩️ {ctx.author.display_name} ⛩️ 🌸 !")
    
    await ctx.send(embed=embed)

@bot.command(name="album")
async def album(ctx, membre: discord.Member = None):
    cible = membre or ctx.author
    embed = discord.Embed(
        title=f"📖 Album de Cartes de {cible.display_name}",
        description="Feuillete ton grimoire pour admirer tes cartes de toutes les classes et les montrer aux autres joueurs !",
        color=0xFF69B4
    )
    embed.add_field(name="🖼️ Cartes Rares & Classées", value="• `1` - Mewtwo [Base - Rareté Rare]\n• `2` - Dracaufeu [Base - Rareté Céleste]", inline=False)
    embed.set_image(url="https://images.pokemontcg.io/base1/4_hires.png") # Aperçu d'une carte dans l'album
    embed.set_footer(text="Utilise les boutons interactifs pour changer de page et admirer les cadres !")
    await ctx.send(embed=embed)

@bot.command(name="afficher")
async def afficher(ctx, *ids: int):
    cartes = ", ".join(map(str, ids))
    embed = discord.Embed(
        title="🖼️ Vitrine des Esprits & Cadres Rares",
        description=f"{ctx.author.mention} expose fièrement ses cartes d'IDs : **{cartes}** !",
        color=0xFFD700
    )
    embed.set_image(url="https://images.pokemontcg.io/base1/2_hires.png") # Vitrine avec cadre
    await ctx.send(embed=embed)

@bot.command(name="marche")
async def marche(ctx):
    embed = discord.Embed(title="🏪 Hôtel des Ventes", description="Voici les cartes de collection actuellement en vente par les joueurs.", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="vendre")
async def vendre(ctx, id_album: int, prix: int):
    embed = discord.Embed(title="🏷️ Annonce de Vente", description=f"Carte encadrée (ID album : **{id_album}**) mise en vente sur le marché pour **{prix}$**.", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="acheter_carte")
async def acheter_carte(ctx, id_vente: int):
    embed = discord.Embed(title="💸 Acquisition Réussie", description=f"Achat de la carte de collection (Vente ID : **{id_vente}**) réussi avec succès !", color=0xFF69B4)
    await ctx.send(embed=embed)

@bot.command(name="retirer_vente")
async def retirer_vente(ctx, id_vente: int):
    embed = discord.Embed(title="🔄 Annulation de Vente", description=f"Vente annulée, la carte a réintégré ton album.", color=0xFF69B4)
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
