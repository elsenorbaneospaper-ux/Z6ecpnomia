import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Modal, TextInput, View
import aiofiles
import random
import json
import os
import asyncio
from flask import Flask
from threading import Thread
import time
import motor.motor_asyncio
from discord import ui, ButtonStyle

# Configuración
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Servidor para mantener activo
app = Flask(__name__)
@app.route('/')
def home(): return "Bot activo"
def run(): app.run(host='0.0.0.0', port=8080)
Thread(target=run).start()

# --- CONEXIÓN A MONGODB ---
MONGO_URL = os.environ.get("MONGO_URI")
cluster = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)

db = cluster["economia_bot"]
usuarios_col = db["usuarios"]

# --- ESTRUCTURA BASE DE USUARIO ---
async def asegurar_usuario(uid: str):
    usuario = await usuarios_col.find_one({"_id": uid})
    
    if not usuario:
        nombres_azar = ["Rayo", "Veloz", "Centella", "Fogonazo", "Turbo"]
        emojis_azar = ["🐶", "🐱", "🐰", "🦊", "🐼"]
        
        nuevo_usuario = {
            "_id": uid,
            "dinero": 0,
            "banco": 0,
            "mascota_nivel": 1,
            "mascota_nombre": random.choice(nombres_azar),
            "mascota_emoji": random.choice(emojis_azar),
            "carreras_gratis": 5,
            "tiene_mascota_propia": False,
            "minerales_descubiertos": []
        }
        await usuarios_col.insert_one(nuevo_usuario)
    else:
        campos_actualizar = {}
        if "mascota_nombre" not in usuario:
            campos_actualizar["mascota_nombre"] = "Rayo"
        if "mascota_emoji" not in usuario:
            campos_actualizar["mascota_emoji"] = "🐶"
        if "carreras_gratis" not in usuario:
            campos_actualizar["carreras_gratis"] = 5
        if "tiene_mascota_propia" not in usuario:
            campos_actualizar["tiene_mascota_propia"] = False
        if "minerales_descubiertos" not in usuario:
            campos_actualizar["minerales_descubiertos"] = []
            
        if campos_actualizar:
            await usuarios_col.update_one({"_id": uid}, {"$set": campos_actualizar})
            

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("Bot listo con todos los comandos.")
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        # Calcula los minutos o segundos restantes
        tiempo_restante = round(error.retry_after, 1)
        mensaje = f"⏳ Estás en cooldown. Por favor, espera **{tiempo_restante} segundos** para volver a usar este comando."
        
        # Si ya se hizo defer, usamos followup; si no, response.send_message
        if interaction.response.is_done():
            await interaction.followup.send(mensaje, ephemeral=True)
        else:
            await interaction.response.send_message(mensaje, ephemeral=True)
    else:
        # Si es otro tipo de error, lo imprimimos en consola para depurar
        raise error
        
# /balance [usuario]
@bot.tree.command(name="balance", description="Revisa tu saldo actual de dinero e inventario.")
@app_commands.describe(usuario="Usuario opcional a consultar")
async def balance(interaction: discord.Interaction, usuario: discord.Member = None):
    await interaction.response.defer(ephemeral=False)
    target = usuario or interaction.user
    uid = str(target.id)
    
    await asegurar_usuario(uid)
    datos = await usuarios_col.find_one({"_id": uid})
    
    await interaction.followup.send(
        f"📊 **Balance de {target.name}:**\n"
        f"💵 Dinero en mano: `{datos.get('dinero', 0)}`\n"
        f"🏦 Dinero en banco: `{datos.get('banco', 0)}`", 
        ephemeral=True
    )

# /dinero [usuario]
@bot.tree.command(name="dinero", description="Consulta el dinero en mano de un usuario.")
@app_commands.describe(usuario="Usuario opcional a consultar")
async def dinero(interaction: discord.Interaction, usuario: discord.Member = None):
    await interaction.response.defer(ephemeral=False)
    target = usuario or interaction.user
    uid = str(target.id)
    
    await asegurar_usuario(uid)
    datos = await usuarios_col.find_one({"_id": uid})
    
    await interaction.followup.send(f"💵 El dinero en mano de **{target.name}** es: `{datos.get('dinero', 0)}`", ephemeral=False)

# /verbanco [usuario]
@bot.tree.command(name="verbanco", description="Consulta el dinero guardado en el banco.")
@app_commands.describe(usuario="Usuario opcional a consultar")
async def verbanco(interaction: discord.Interaction, usuario: discord.Member = None):
    await interaction.response.defer(ephemeral=False)
    target = usuario or interaction.user
    uid = str(target.id)
    
    await asegurar_usuario(uid)
    datos = await usuarios_col.find_one({"_id": uid})
    
    await interaction.followup.send(f"🏦 El dinero en el banco de **{target.name}** es: `{datos.get('banco', 0)}`", ephemeral=False)


# /addbanco [cantidad]
@bot.tree.command(name="addbanco", description="Deposita dinero en el banco.")
@app_commands.describe(cantidad="Cantidad a depositar (número o 'all' para todo)")
async def addbanco(interaction: discord.Interaction, cantidad: str):
    await interaction.response.defer(ephemeral=False)
    uid = str(interaction.user.id)
    
    await asegurar_usuario(uid)
    datos = await usuarios_col.find_one({"_id": uid})
    dinero_disponible = datos.get("dinero", 0)
    
    # Manejar "all"
    if cantidad.lower() in ["all", "todo"]:
        monto = dinero_disponible
    else:
        try:
            monto = int(cantidad)
        except ValueError:
            await interaction.followup.send("❌ Por favor, introduce un número válido o 'all'.", ephemeral=False)
            return

    if monto <= 0:
        await interaction.followup.send("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
        return

    if dinero_disponible < monto:
        await interaction.followup.send("❌ No tienes suficiente dinero en mano para depositar esa cantidad.", ephemeral=True)
        return

    await usuarios_col.update_one(
        {"_id": uid},
        {"$inc": {"dinero": -monto, "banco": monto}}
    )
    
    await interaction.followup.send(f"✅ Has depositado **{monto}** en el banco correctamente.", ephemeral=False)

# /sacarbanco [cantidad]
@bot.tree.command(name="sacarbanco", description="Retira dinero del banco a tu mano.")
@app_commands.describe(cantidad="Cantidad a retirar (número o 'all' para todo)")
async def sacarbanco(interaction: discord.Interaction, cantidad: str):
    await interaction.response.defer(ephemeral=False)
    uid = str(interaction.user.id)
    
    await asegurar_usuario(uid)
    datos = await usuarios_col.find_one({"_id": uid})
    banco_disponible = datos.get("banco", 0)
    
    # Manejar "all"
    if cantidad.lower() in ["all", "todo"]:
        monto = banco_disponible
    else:
        try:
            monto = int(cantidad)
        except ValueError:
            await interaction.followup.send("❌ Por favor, introduce un número válido o 'all'.", ephemeral=True)
            return

    if monto <= 0:
        await interaction.followup.send("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
        return

    if banco_disponible < monto:
        await interaction.followup.send("❌ No tienes esa cantidad guardada en el banco.", ephemeral=False)
        return

    await usuarios_col.update_one(
        {"_id": uid},
        {"$inc": {"banco": -monto, "dinero": monto}}
    )
    
    await interaction.followup.send(f"✅ Has retirado **{monto}** del banco a tu mano.", ephemeral=True)

# /transferir [usuario] [cantidad]
@bot.tree.command(name="transferir", description="Transfiere dinero a otro usuario.")
@app_commands.describe(usuario="Usuario a quien transferir", cantidad="Cantidad a transferir (número o 'all' para todo)")
async def transferir(interaction: discord.Interaction, usuario: discord.Member, cantidad: str):
    await interaction.response.defer(ephemeral=False)
    
    if usuario.bot or usuario.id == interaction.user.id:
        await interaction.followup.send("❌ No puedes transferir dinero a bots o a ti mismo.", ephemeral=True)
        return

    uid_emisor = str(interaction.user.id)
    uid_receptor = str(usuario.id)
    
    await asegurar_usuario(uid_emisor)
    await asegurar_usuario(uid_receptor)
    
    datos_emisor = await usuarios_col.find_one({"_id": uid_emisor})
    dinero_disponible = datos_emisor.get("dinero", 0)
    
    # Manejar "all"
    if cantidad.lower() in ["all", "todo"]:
        monto = dinero_disponible
    else:
        try:
            monto = int(cantidad)
        except ValueError:
            await interaction.followup.send("❌ Por favor, introduce un número válido o 'all'.", ephemeral=True)
            return

    if monto <= 0:
        await interaction.followup.send("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
        return
    
    if dinero_disponible < monto:
        await interaction.followup.send("❌ No tienes suficiente dinero en mano para hacer esta transferencia.", ephemeral=True)
        return

    # Restar al emisor y sumar al receptor
    await usuarios_col.update_one({"_id": uid_emisor}, {"$inc": {"dinero": -monto}})
    await usuarios_col.update_one({"_id": uid_receptor}, {"$inc": {"dinero": monto}})
    
    await interaction.followup.send(f"💸 Has transferido exitosamente **{monto}** a **{usuario.name}**.", ephemeral=False)


# --- SISTEMA DE MINERÍA Y CRAFTEO ---

MINERALES_DATA = [
    {"nombre": "Piedra", "emoji": "🪨", "valor": 50, "peso": 25.0},
    {"nombre": "Carbón", "emoji": "⬛", "valor": 120, "peso": 20.0},
    {"nombre": "Sal Gema", "emoji": "🧂", "valor": 200, "peso": 15.0},
    {"nombre": "Arcilla", "emoji": "🧱", "valor": 300, "peso": 12.0},
    {"nombre": "Cobre", "emoji": "🟠", "valor": 450, "peso": 10.0},
    {"nombre": "Estaño", "emoji": "⚪", "valor": 600, "peso": 8.5},
    {"nombre": "Hierro", "emoji": "⛓️", "valor": 850, "peso": 7.0},
    {"nombre": "Azufre", "emoji": "🟡", "valor": 1100, "peso": 6.0},
    {"nombre": "Cuarzo", "emoji": "🧊", "valor": 1500, "peso": 5.2},
    {"nombre": "Plomo", "emoji": "⚫", "valor": 2000, "peso": 4.5},
    {"nombre": "Zinc", "emoji": "🔋", "valor": 2500, "peso": 4.0},
    {"nombre": "Bronce", "emoji": "🟤", "valor": 3200, "peso": 3.5},
    {"nombre": "Plata", "emoji": "🪙", "valor": 4000, "peso": 3.0},
    {"nombre": "Oro", "emoji": "🥇", "valor": 5200, "peso": 2.5},
    {"nombre": "Jade", "emoji": "🍏", "valor": 6500, "peso": 2.1},
    {"nombre": "Ambar", "emoji": "🍯", "valor": 8000, "peso": 1.8},
    {"nombre": "Rubí", "emoji": "🟥", "valor": 10000, "peso": 1.5},
    {"nombre": "Zafiro", "emoji": "🟦", "valor": 12500, "peso": 1.2},
    {"nombre": "Esmeralda", "emoji": "🟩", "valor": 15000, "peso": 1.0},
    {"nombre": "Amatista", "emoji": "🟣", "valor": 18000, "peso": 0.85},
    {"nombre": "Platino", "emoji": "⚙️", "valor": 22000, "peso": 0.7},
    {"nombre": "Titanio", "emoji": "🛡️", "valor": 27000, "peso": 0.55},
    {"nombre": "Uranio", "emoji": "☢️", "valor": 33000, "peso": 0.42},
    {"nombre": "Diamante", "emoji": "💎", "valor": 40000, "peso": 0.3},
    {"nombre": "Netherita", "emoji": "🖤", "valor": 48000, "peso": 0.2},
    {"nombre": "Tungsteno", "emoji": "🔩", "valor": 55000, "peso": 0.12},
    {"nombre": "Opal Negro", "emoji": "🌌", "valor": 61000, "peso": 0.07},
    {"nombre": "Taaffeita", "emoji": "✨", "valor": 65000, "peso": 0.04},
    {"nombre": "Painita", "emoji": "🔮", "valor": 68000, "peso": 0.02},
    {"nombre": "Estrella de Mar", "emoji": "🌟", "valor": 70000, "peso": 0.01}
]

class VistaMinar(discord.ui.View):
    def __init__(self, uid, mineral_encontrado):
        super().__init__(timeout=600)
        self.uid = uid
        self.mineral = mineral_encontrado

    @discord.ui.button(label="Mantener", style=discord.ButtonStyle.success, emoji="📦")
    async def mantener(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("❌ Este botón no es para ti.", ephemeral=True)
        
        await asegurar_usuario(self.uid)
        await usuarios_col.update_one(
            {"_id": self.uid},
            {"$inc": {f"minerales.{self.mineral['nombre']}": 1}}
        )
        
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=f"📦 Has guardado **{self.mineral['emoji']} {self.mineral['nombre']}** en tu inventario.", view=self)

    @discord.ui.button(label="Vender", style=discord.ButtonStyle.danger, emoji="💰")
    async def vender(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("❌ Este botón no es para ti.", ephemeral=True)
            
        await asegurar_usuario(self.uid)
        valor_venta = self.mineral["valor"]
        await usuarios_col.update_one(
            {"_id": self.uid},
            {"$inc": {"dinero": valor_venta}}
        )
        
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=f"💰 Has vendido **{self.mineral['emoji']} {self.mineral['nombre']}** por **{valor_venta}** monedas.", view=self)


# /minar (con cooldown de 5 minutos / 300 segundos)
@bot.tree.command(name="minar", description="Explora minas para extraer minerales valiosos.")
@app_commands.checks.cooldown(1, 300, key=lambda i: i.user.id)
async def minar(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)
    
    datos = await usuarios_col.find_one({"_id": uid})
    pico_actual = datos.get("pico_activo", {"bonus": 0})
    bonus_pico = pico_actual.get("bonus", 0) # Máximo 30% extra
    
    # Probabilidad base modificada por el pico
    pesos = [m["peso"] * (1 + (bonus_pico / 100.0)) for m in MINERALES_DATA]
    mineral_elegido = random.choices(MINERALES_DATA, weights=pesos, k=1)[0]
    
    view = VistaMinar(uid, mineral_elegido)
    await interaction.followup.send(
        f"⛏️ ¡Has excavado y encontrado un mineral!\n\n"
        f"**Mineral:** {mineral_elegido['emoji']} {mineral_elegido['nombre']}\n"
        f"**Valor estimado:** `{mineral_elegido['valor']}` monedas\n\n"
        f"¿Qué deseas hacer?",
        view=view,
        ephemeral=False
    )


@bot.tree.command(name="top", description="Muestra la tabla de clasificación de la economía total.")
@app_commands.checks.cooldown(1, 10)
async def top(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    
    # Obtenemos todos los usuarios excluyendo la configuración global
    cursor = usuarios_col.find({"_id": {"$ne": "configuracion_global"}})
    usuarios = await cursor.to_list(length=None)
    
    if not usuarios:
        return await interaction.followup.send("❌ No hay datos de usuarios registrados todavía.")

    # Calculamos el total (efectivo + banco) para cada usuario
    lista_ranking = []
    for u in usuarios:
        try:
            user_id_int = int(u["_id"])
        except ValueError:
            continue
        
        # Ajusta los nombres de las llaves según cómo las guardes en tu base de datos (ej: "efectivo", "mano", "banco", etc.)
        efectivo = u.get("dinero", u.get("efectivo", 0))
        banco = u.get("banco", 0)
        total_balance = efectivo + banco
        
        lista_ranking.append({"id": user_id_int, "total": total_balance})

    # Ordenamos de mayor a menor según el total combinado y tomamos los primeros 10
    lista_ranking = sorted(lista_ranking, key=lambda x: x["total"], reverse=True)[:10]

    descripcion = ""
    for index, item in enumerate(lista_ranking, start=1):
        mencion = f"<@{item['id']}>"
        total_format = item["total"]
        
        if index == 1:
            medalla = "👑"
        elif index == 2:
            medalla = "🥈"
        elif index == 3:
            medalla = "🥉"
        else:
            medalla = f"`#{index}`"
            
        descripcion += f"{medalla} {mencion} — **`{total_format:,}`** monedas en total\n"

    embed = discord.Embed(
        title="🏆 Tabla de Clasificación (Balance Total)",
        description=descripcion,
        color=discord.Color.gold()
    )
    
    await interaction.followup.send(embed=embed)
            
    
# --- COMANDO /ayuda DEFINITIVO Y COMPLETO ---
@bot.tree.command(name="ayuda", description="Muestra la lista de todos los comandos y sistemas disponibles del bot.")
async def ayuda(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    
    embed = discord.Embed(
        title="📖 Menú General de Ayuda - Z6 Economía",
        description="Aquí tienes la lista completa de todos los sistemas y comandos integrados en tu bot:",
        color=discord.Color.blue()
    )
    
    # Economía, Banco y Rankings
    embed.add_field(
        name="💳 Economía, Banco y Rankings",
        value=(
            "• `/balance [usuario]` — Revisa tu dinero en efectivo, banco y patrimonio total.\n"
            "• `/dinero` — Muestra información detallada de tus fondos.\n"
            "• `/trade _ Intercambia ítems de forma segura y blindada.\n"
            "• `/verbanco` — Consulta el estado actual de tu cuenta bancaria.\n"
            "• `/addbanco [cantidad/all]` — Guarda tu dinero de forma segura en el banco.\n"
            "• `/sacarbanco [cantidad/all]` — Saca dinero del banco para tenerlo en mano.\n"
            "• `/transferir [usuario] [cantidad]` — Transfiere dinero en efectivo a otro usuario.\n"
            "• `/prestamo _ Pide dinero prestado con aprobación de botones.\n"
            "• `/pagar_prestamo _ Salda deudas bancarias con efectivo.\n"
            "• `/estado_prestamo _ Revisa deudas pendientes en privado.\n"
            "• `/top` — Muestra el top 10 de los usuarios más ricos del servidor."
        ),
        inline=False
    )

    # Minería, Inventario y Crafteo
    embed.add_field(
        name="⛏️ Minería, Inventario y Crafteo",
        value=(
            "• `/minar` — Extrae minerales valiosos de las profundidades.\n"
            "• `/inventario` — Revisa tus minerales, gemas y materiales recolectados.\n"
            "• `/vender` — Intercambia tus materiales mineros por dinero.\n"
            "• `/craftteo` — Abre el menú de crafteo para crear herramientas o mejoras."
        ),
        inline=False
    )

    # Apuestas y Minijuegos
    embed.add_field(
        name="🎲 Apuestas y Minijuegos",
        value=(
            "• `/pavo_hambriento` — Participa en el minijuego de apuestas del pavo.\n"
            "• `/suerte_raton` — Pon a prueba tu suerte con el minijuego del ratón.\n"
            "• `/cohete_crash` — Apuesta y retira antes de que el cohete estrelle.\n"
            "• `/rompemuros` — Juega a romper muros por recompensas en efectivo.\n"
            "• `/run_bomb` _ Elige una casilla del 1 al 12 e intenta sobrevivir a las bombas y sus ondas expansivas que se extienden cada 1.5 segundos con un 20% de probabilidad de una bomba extra. (Cooldown: 8 minutos)."
            "• `/cup_game` — Adivina en qué casilla de los 6 vasos se oculta la pelota con un solo intento para ganar un multiplicador de x3 de tu apuesta. (Cooldown: 5 minutos)."
        ),
        inline=False
    )

    # Crimen y Robos
    embed.add_field(
        name="💰 Crimen y Robos",
        value=(
            "• `/crimen` — Comete un acto ilícito para ganar dinero (riesgo de multa/condena).\n"
            "• `/robar [usuario]` — Intenta robar dinero en mano a otro usuario.\n"
            "• `/robarbanco [usuario]` — Ataca el banco de otro usuario."
        ),
        inline=False
    )
    
    # Sistema de Chamba (Trabajos)
    embed.add_field(
        name="👷 Sistema de Trabajos (Chamba)",
        value=(
            "• `/elegir_trabajo` — Selecciona tu empleo (8 trabajos en total).\n"
            "• `/nivel_chamba` — Revisa tu XP, nivel de chamba y progreso para el próximo empleo.\n"
            "• `/trabajo` — Realiza tu jornada laboral para ganar dinero y experiencia (Cooldown: 2 min)."
        ),
        inline=False
    )
    
    # Sistema de Mascotas
    embed.add_field(
        name="🐾 Sistema de Mascotas",
        value=(
            "• `/comprar_mascota [nombre] [emoji]` — Adopta y personaliza tu compañero.\n"
            "• `/mejorar_mascota` — Sube de nivel a tu mascota para potenciar estadísticas.\n"
            "• `/ver_mascota [usuario]` — Consulta el estado y nivel de una mascota.\n"
            "• `/carrera_mascota [apuesta]` — Compite con tu mascota contra Z6.\n"
            "• `/buscar_tesoro_mascota` — Envía a tu mascota a desenterrar tesoros ocultos."
        ),
        inline=False
    )
    
    # Eventos y Administración (Dueños)
    embed.add_field(
        name="🛠️ Eventos y Administración (Solo Dueños y admins)",
        value=(
            "• `/sorteo_economia [premio] [tiempo] [cantidad_reroll] [tiempo_claim] [imagen]` — Sorteo interactivo con botón de reclamo, caducidad, reroll automático e imagen.\n"
            "• `/dar [usuario] [cantidad]` — Entrega dinero directamente a un usuario.\n"
            "• `/quitar [usuario] [cantidad/all]` — Retira dinero o vacía el saldo de un usuario.\n"
            "• `/addbanco [usuario] [cantidad]` — Añade fondos al banco de un usuario.\n"
            "• `/sacarbanco [usuario] [cantidad]` — Retira fondos del banco de un usuario.\n"
            "• `/reset-eco` — Resetea por completo la economía del servidor."
        ),
        inline=False
    )
    
    embed.set_footer(text="¡Usa los comandos correctamente y diviértete en el servidor!")
    await interaction.followup.send(embed=embed, ephemeral=False)

class VistaRunBombVisual(discord.ui.View):
    def __init__(self, uid, apuesta, casilla_elegida, estado_casillas):
        super().__init__(timeout=60)
        self.uid = uid
        self.apuesta = apuesta
        self.casilla_elegida = casilla_elegida
        
        for i in range(1, 13):
            estilo = estado_casillas.get(i, discord.ButtonStyle.secondary)
            if i == casilla_elegida:
                label_texto = f"🎯 [Tú] #{i}"
            else:
                label_texto = f"Casilla {i}"
                
            button = discord.ui.Button(label=label_texto, style=estilo, custom_id=f"b_{i}", disabled=True)
            self.add_item(button)


@bot.tree.command(name="run_bomb", description="Selecciona una casilla y sobrevive a las 4 fases de expansión de la bomba.")
@app_commands.checks.cooldown(1, 480) # Cooldown de 8 minutos
@app_commands.describe(apuesta="Cantidad de dinero a apostar", casilla="Elige una casilla del 1 al 12")
@app_commands.choices(casilla=[app_commands.Choice(name=f"Casilla {i}", value=i) for i in range(1, 13)])
async def run_bomb(interaction: discord.Interaction, apuesta: int, casilla: int):
    await interaction.response.defer(ephemeral=False)
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)

    datos = await usuarios_col.find_one({"_id": uid})
    if datos.get("dinero", 0) < apuesta or apuesta <= 0:
        return await interaction.followup.send("❌ No tienes suficiente dinero.", ephemeral=True)

    def obtener_vecinos(c):
        fila = (c - 1) // 4
        col = (c - 1) % 4
        vecinos = []
        for f in range(max(0, fila - 1), min(3, fila + 2)):
            for co in range(max(0, col - 1), min(4, col + 2)):
                if not (f == fila and co == col):
                    vecinos.append(f * 4 + co + 1)
        return vecinos

    # 1. Definir bombas iniciales
    bomba_1 = random.randint(1, 12)
    bombas_activas = [bomba_1]
    
    segunda_bomba = random.random() < 0.20
    if segunda_bomba:
        bomba_2 = random.choice([x for x in range(1, 13) if x != bomba_1])
        bombas_activas.append(bomba_2)

    total_bombas_caidas = len(bombas_activas)

    # Estado inicial de los botones
    estado_inicial = {i: (discord.ButtonStyle.primary if i == casilla else discord.ButtonStyle.secondary) for i in range(1, 13)}
    view_actual = VistaRunBombVisual(uid, apuesta, casilla, estado_inicial)

    msg = await interaction.followup.send(
        f"💣 **¡RUN BOMB INICIADO!**\n• Tu casilla elegida: `#{casilla}`\n• Apuesta: `{apuesta:,}` monedas\n• Bombas caídas: `{total_bombas_caidas}`\n\n*La bomba va a detonar...*",
        view=view_actual,
        ephemeral=False
    )

    await asyncio.sleep(1.5)

    # ==========================================
    # FASE 1: Impacto Directo (ROJO - Multiplicador 0)
    # ==========================================
    fase_1_rojo = set(bombas_activas)
    estado_fase_1 = {i: discord.ButtonStyle.secondary for i in range(1, 13)}
    for c_num in range(1, 13):
        if c_num in fase_1_rojo:
            estado_fase_1[c_num] = discord.ButtonStyle.danger # Rojo
        elif c_num == casilla:
            estado_fase_1[c_num] = discord.ButtonStyle.primary

    view_actual = VistaRunBombVisual(uid, apuesta, casilla, estado_fase_1)
    
    if casilla in fase_1_rojo:
        dinero_recibido = 0
        multiplicador = "0"
        await usuarios_col.update_one({"_id": uid}, {"$inc": {"dinero": -apuesta}})
        await msg.edit(
            content=f"🟥 **¡FASE 1: Impacto Directo (Rojo)!**\nLa bomba cayó en la casilla `#{casilla}`.\nSi estuvieras aquí hubieras recibido {dinero_recibido} y multiplicador de {multiplicador} si sobrevives\n\n❌ Perdiste tu apuesta de **`{apuesta:,}`** monedas.",
            view=view_actual
        )
        return

    await msg.edit(
        content=f"🟥 **¡FASE 1: Impacto Directo (Rojo)!**\nLas bombas han detonado. Te salvaste por ahora...",
        view=view_actual
    )
    await asyncio.sleep(1.5)

    # ==========================================
    # FASE 2: Primera Expansión (NARANJA - Multiplicador x0.5)
    # ==========================================
    fase_2_naranja = set()
    for b in fase_1_rojo:
        for v in obtener_vecinos(b):
            fase_2_naranja.add(v)

    estado_fase_2 = dict(estado_fase_1)
    for c_num in range(1, 13):
        if c_num in fase_1_rojo:
            estado_fase_2[c_num] = discord.ButtonStyle.danger
        elif c_num in fase_2_naranja:
            estado_fase_2[c_num] = discord.ButtonStyle.primary # Simula naranja/blurple
        elif c_num == casilla:
            estado_fase_2[c_num] = discord.ButtonStyle.success

    view_actual = VistaRunBombVisual(uid, apuesta, casilla, estado_fase_2)

    if casilla in fase_2_naranja:
        premio = int(apuesta * 0.5)
        dinero_recibido = premio
        multiplicador = "0.5"
        reembolso_neto = premio - apuesta 
        await usuarios_col.update_one({"_id": uid}, {"$inc": {"dinero": reembolso_neto}})
        await msg.edit(
            content=f"🟧 **¡FASE 2: Primera Expansión (Naranja)!**\nLa onda expansiva alcanzó la casilla `#{casilla}`.\nSi estuvieras aquí hubieras recibido {dinero_recibido} y multiplicador de {multiplicador} si sobrevives\n\n💸 Obtuviste **`{premio:,}`** monedas (x0.5).",
            view=view_actual
        )
        return

    await msg.edit(
        content=f"🟧 **¡FASE 2: Primera Expansión completada!**\nSigues a salvo...",
        view=view_actual
    )
    await asyncio.sleep(1.5)

    # ==========================================
    # FASE 3: Segunda Expansión (AMARILLO - Multiplicador x1.0)
    # ==========================================
    fase_3_amarillo = set()
    for b in list(fase_2_naranja):
        for v in obtener_vecinos(b):
            if v not in fase_1_rojo:
                fase_3_amarillo.add(v)

    estado_fase_3 = dict(estado_fase_2)
    for c_num in range(1, 13):
        if c_num in fase_1_rojo:
            estado_fase_3[c_num] = discord.ButtonStyle.danger
        elif c_num in fase_2_naranja:
            estado_fase_3[c_num] = discord.ButtonStyle.primary
        elif c_num in fase_3_amarillo:
            estado_fase_3[c_num] = discord.ButtonStyle.secondary # Simula amarillo
        elif c_num == casilla:
            estado_fase_3[c_num] = discord.ButtonStyle.success

    view_actual = VistaRunBombVisual(uid, apuesta, casilla, estado_fase_3)

    if casilla in fase_3_amarillo:
        dinero_recibido = apuesta
        multiplicador = "1.0"
        await msg.edit(
            content=f"🟨 **¡FASE 3: Segunda Expansión (Amarillo)!**\nLa onda expansiva rozó tu posición en la casilla `#{casilla}`.\nSi estuvieras aquí hubieras recibido {dinero_recibido} y multiplicador de {multiplicador} si sobrevives\n\nRecuperas tu apuesta de vuelta sin pérdidas (`x1.0`).",
            view=view_actual
        )
        return

    await msg.edit(
        content=f"🟨 **¡FASE 3: Segunda Expansión completada!**\nA punto de la victoria...",
        view=view_actual
    )
    await asyncio.sleep(1.5)

    # ==========================================
    # FASE 4: Supervivencia Total (VERDE - Multiplicador x1.5 o superior)
    # ==========================================
    estado_fase_4 = dict(estado_fase_3)
    for c_num in range(1, 13):
        if c_num == casilla:
            estado_fase_4[c_num] = discord.ButtonStyle.success

    view_actual = VistaRunBombVisual(uid, apuesta, casilla, estado_fase_4)

    if total_bombas_caidas >= 2:
        premio_bonus = int(apuesta * 1.5)
        dinero_recibido = premio_bonus
        multiplicador = "1.5"
        ganancia_neta = premio_bonus - apuesta
        await usuarios_col.update_one({"_id": uid}, {"$inc": {"dinero": ganancia_neta}})
        await msg.edit(
            content=f"🟩 **¡FASE 4: Supervivencia Total (Verde)!**\nSobreviviste a **2 bombas** y todas sus expansiones en la casilla `#{casilla}`.\nSi estuvieras aquí hubieras recibido {dinero_recibido} y multiplicador de {multiplicador} si sobrevives\n\n🏆 ¡Obtuviste un **bonus de x1.5**! Ganaste **`+{ganancia_neta:,}`** monedas (Total: `{premio_bonus:,}`).",
            view=view_actual
        )
    else:
        dinero_recibido = apuesta
        multiplicador = "1.0"
        await msg.edit(
            content=f"🟩 **¡FASE 4: Supervivencia Total (Verde)!**\nTe mantuviste totalmente fuera del radio de la explosión en la casilla `#{casilla}`.\nSi estuvieras aquí hubieras recibido {dinero_recibido} y multiplicador de {multiplicador} si sobrevives\n\nRecuperas tu apuesta a salvo.",
            view=view_actual
    )
        

    

class VistaCupGame(discord.ui.View):
    def __init__(self, uid, apuesta):
        super().__init__(timeout=60)
        self.uid = uid
        self.apuesta = apuesta
        self.pelota_pos = random.randint(1, 6)

        for i in range(1, 7):
            button = discord.ui.Button(label=f"Casilla {i}", style=discord.ButtonStyle.blurple, custom_id=f"casilla_{i}")
            button.callback = self.crear_callback(i)
            self.add_item(button)

    def crear_callback(self, numero_casilla):
        async def callback(interaction: discord.Interaction):
            if str(interaction.user.id) != self.uid:
                return await interaction.response.send_message("❌ Este juego no es tuyo.", ephemeral=True)

            for child in self.children:
                child.disabled = True

            if numero_casilla == self.pelota_pos:
                ganancia = self.apuesta * 3
                ganancia_neta = ganancia - self.apuesta
                await usuarios_col.update_one({"_id": self.uid}, {"$inc": {"dinero": ganancia_neta}})
                
                await interaction.response.edit_message(
                    content=f"🎉 **¡Acertaste!** La pelota estaba en la casilla **#{self.pelota_pos}**.\n🏆 Ganaste un `x3` de tu apuesta: **`+{ganancia_neta:,}`** monedas (Total: `{ganancia:,}`).",
                    view=self
                )
            else:
                await usuarios_col.update_one({"_id": self.uid}, {"$inc": {"dinero": -self.apuesta}})
                await interaction.response.edit_message(
                    content=f"❌ **¡Fallaste!** Elegiste la casilla #{numero_casilla}, pero la pelota estaba en la casilla **#{self.pelota_pos}**.\nPerdiste tu apuesta de **`{self.apuesta:,}`** monedas.",
                    view=self
                )

        return callback


@bot.tree.command(name="cup_game", description="Adivina dónde está la pelota entre 6 casillas para ganar un x3.")
@app_commands.checks.cooldown(1, 300) # Cooldown de 5 minutos (300 segundos)
@app_commands.describe(apuesta="Cantidad de dinero a apostar")
async def cup_game(interaction: discord.Interaction, apuesta: int):
    await interaction.response.defer(ephemeral=False)
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)

    datos = await usuarios_col.find_one({"_id": uid})
    if datos.get("dinero", 0) < apuesta or apuesta <= 0:
        return await interaction.followup.send("❌ No tienes suficiente dinero.", ephemeral=True)

    view = VistaCupGame(uid, apuesta)
    await interaction.followup.send(
        f"🎯 **¡Juego de la Pelota (Cup Game)!**\nHay 6 casillas disponibles. Una de ellas oculta la pelota.\nApuesta: `{apuesta:,}` monedas\n\n¡Haz clic en una casilla para adivinar!",
        view=view,
        ephemeral=False
    )
    

class VistaRompemuros(discord.ui.View):
    def __init__(self, uid, apuesta, muros_rotos, multiplicador_actual):
        super().__init__(timeout=600)
        self.uid = uid
        self.apuesta = apuesta
        self.muros_rotos = muros_rotos
        self.multiplicador_actual = multiplicador_actual

    @discord.ui.button(label="🔨 Romper Siguiente Muro", style=discord.ButtonStyle.blurple)
    async def romper(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("❌ Este juego no es tuyo.", ephemeral=True)

        # 60% de probabilidad de superar el muro
        exito = random.random() < 0.60 

        if exito:
            self.muros_rotos += 1
            self.multiplicador_actual *= 2 # Multiplica x2 de forma progresiva
            
            vista_siguiente = VistaRompemuros(self.uid, self.apuesta, self.muros_rotos, self.multiplicador_actual)
            await interaction.response.edit_message(
                content=f"🧱 **¡Muro superado con éxito!**\n• Muros rotos: `{self.muros_rotos}`\n• Multiplicador actual: `{self.multiplicador_actual}x`\n• Premio acumulado: **`{int(self.apuesta * self.multiplicador_actual):,}`** monedas\n\n¿Qué deseas hacer?",
                view=vista_siguiente
            )
        else:
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(
                content=f"💥 **¡El muro se derrumbó sobre ti!**\nIntentaste romper el muro #{self.muros_rotos + 1} y perdiste tu apuesta de **`{self.apuesta:,}`** monedas.",
                view=self
            )

    @discord.ui.button(label="💰 Cobrar y Salir", style=discord.ButtonStyle.green)
    async def cobrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("❌ Este juego no es tuyo.", ephemeral=True)

        premio_total = int(self.apuesta * self.multiplicador_actual)
        ganancia_neta = premio_total - self.apuesta

        await usuarios_col.update_one({"_id": self.uid}, {"$inc": {"dinero": ganancia_neta}})

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=f"🎉 **¡EXCAVACIÓN EXITOSA!**\n🧱 Muros superados: `{self.muros_rotos}`\n📈 Multiplicador final: `{self.multiplicador_actual}x`\n💰 Te retiraste a tiempo con una ganancia neta de **`+{ganancia_neta:,}`** (Total: `{premio_total:,}`)",
            view=self
        )


@bot.tree.command(name="rompemuros", description="Rompe muros multiplicando tus ganancias x2 progresivamente.")
@app_commands.checks.cooldown(1, 20)
@app_commands.describe(apuesta="Cantidad de dinero a apostar para iniciar")
async def rompemuros(interaction: discord.Interaction, apuesta: int):
    await interaction.response.defer(ephemeral=False)
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)

    datos = await usuarios_col.find_one({"_id": uid})
    if datos.get("dinero", 0) < apuesta or apuesta <= 0:
        return await interaction.followup.send("❌ No tienes suficiente dinero.", ephemeral=True)

    # Primer intento automático para iniciar la cadena
    exito_inicial = random.random() < 0.50
    
    if not exito_inicial:
        await usuarios_col.update_one({"_id": uid}, {"$inc": {"dinero": -apuesta}})
        return await interaction.followup.send(f"🧱 El primer muro era demasiado duro y perdiste tu apuesta de `{apuesta:,}` monedas.", ephemeral=False)

    muros_rotos = 1
    multiplicador = 0.8 # Primer muro otorga x2 inicial
    view = VistaRompemuros(uid, apuesta, muros_rotos, multiplicador)

    await interaction.followup.send(
        f"🎉 **¡EXCAVACIÓN EXITOSA!**\n🧱 Muros superados: `1`\n📈 Multiplicador final: `2x`\n💰 Te retiraste a tiempo con una ganancia neta de **`+{int(apuesta * 2) - apuesta:,}`** (Total: `{int(apuesta * 2):,}`)",
        view=view,
        ephemeral=False
        )
    

class VistaCohete(discord.ui.View):
    def __init__(self, uid, apuesta):
        super().__init__(timeout=600)
        self.uid = uid
        self.apuesta = apuesta
        self.multiplicador = 1.0
        self.en_curso = True
        self.mensaje_obj = None

    @discord.ui.button(label="🚀 ¡Retirarse (Cash Out)!", style=discord.ButtonStyle.green)
    async def retirar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("❌ Este juego no es tuyo.", ephemeral=True)
        
        if not self.en_curso:
            return await interaction.response.send_message("❌ El cohete ya explotó.", ephemeral=True)

        self.en_curso = False
        ganancia = int(self.apuesta * self.multiplicador)
        
        await usuarios_col.update_one({"_id": self.uid}, {"$inc": {"dinero": ganancia}})
        
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=f"🎯 **¡CASH OUT EXITOSO!**\n🚀 Te retiraste con un multiplicador de `{self.multiplicador:.1f}x`.\n💰 Ganaste **`{ganancia:,}`** de dinero.",
            view=self
        )


@bot.tree.command(name="cohete_crash", description="Apuesta y retira mientras el cohete sube +0.5 cada 1.5s.")
@app_commands.checks.cooldown(1, 30)
@app_commands.describe(apuesta="Cantidad de dinero a apostar")
async def cohete_crash(interaction: discord.Interaction, apuesta: int):
    await interaction.response.defer(ephemeral=False)
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)

    datos = await usuarios_col.find_one({"_id": uid})
    if datos.get("dinero", 0) < apuesta or apuesta <= 0:
        return await interaction.followup.send("❌ No tienes suficiente dinero.", ephemeral=True)

    await usuarios_col.update_one({"_id": uid}, {"$inc": {"dinero": -apuesta}})

    punto_explosion = round(random.choice([1.5, 2.0, 2.5, 3.0, 3.5,]), 1)
    view = VistaCohete(uid, apuesta)
    
    msg = await interaction.followup.send(
        f"🚀 **¡El cohete ha despegado!**\nMultiplicador actual: `1.0x`\nApuesta: `{apuesta:,}` monedas\n¡Presiona el botón para retirar antes de que explote!",
        view=view,
        ephemeral=False
    )
    view.mensaje_obj = msg

    while view.en_curso and view.multiplicador < punto_explosion:
        await asyncio.sleep(1.5) # Exactamente cada 1.5 segundos
        if not view.en_curso:
            break
        
        view.multiplicador = round(view.multiplicador + 0.3, 1) # Sube +0.5 exactamente
        
        if view.multiplicador >= punto_explosion:
            view.en_curso = False
            for child in view.children:
                child.disabled = True
            try:
                await msg.edit(
                    content=f"💥 **¡BOOM! El cohete explotó en `x{punto_explosion}`**\nPerdiste tu apuesta de `{apuesta:,}` monedas.",
                    view=view
                )
            except Exception:
                pass
            break
        else:
            try:
                await msg.edit(
                    content=f"🚀 **El cohete sigue subiendo...**\nMultiplicador actual: `x{view.multiplicador:.1f}`\n¡Apúrate en retirar!",
                    view=view
                )
            except Exception:
                pass
            

class VistaInventarioConEquipamiento(discord.ui.View):
    def __init__(self, uid, picos_usuario, pico_actual_nombre):
        super().__init__(timeout=180)
        self.uid = uid
        
        options = []
        for pico in picos_usuario:
            is_equipped = (pico == pico_actual_nombre)
            desc = "✅ Actualmente Equipado" if is_equipped else "Haz clic para equipar este pico"
            options.append(discord.SelectOption(label=pico, description=desc, default=is_equipped))

        self.select_pico = discord.ui.Select(placeholder="🔄 Selecciona un pico para equipar...", options=options)
        self.select_pico.callback = self.equipar_callback
        self.add_item(self.select_pico)

    async def equipar_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("❌ Este menú no es para ti.", ephemeral=True)
        
        nuevo_pico_nombre = self.select_pico.values[0]
        await asegurar_usuario(self.uid)
        
        # Guardamos el pico activo respetando tu estructura original en un diccionario
        nuevo_pico_obj = {"nombre": nuevo_pico_nombre} 

        await usuarios_col.update_one(
            {"_id": self.uid},
            {"$set": {"pico_activo": nuevo_pico_obj}}
        )

        # Recargamos los datos para refrescar la vista del inventario
        datos = await usuarios_col.find_one({"_id": self.uid})
        minerales_usuario = datos.get("minerales", {})
        picos_usuario = datos.get("picos", ["Pico de Madera (Por defecto)"])
        pico_actual = datos.get("pico_activo", {}).get("nombre", "Pico de Madera")

        texto_minerales = ""
        if minerales_usuario:
            for min_nombre, cantidad in minerales_usuario.items():
                if cantidad > 0:
                    texto_minerales += f"• **{min_nombre}**: `{cantidad}`\n"
        if not texto_minerales:
            texto_minerales = "No tienes minerales guardados."

        nuevo_texto = (
            f"🎒 **Inventario de {interaction.user.name}**\n\n"
            f"⛏️ **Pico Equipado:** {pico_actual}\n"
            f"📋 **Picos Disponibles:** {', '.join(picos_usuario)}\n\n"
            f"💎 **Minerales:**\n{texto_minerales}"
        )

        nueva_vista = VistaInventarioConEquipamiento(self.uid, picos_usuario, pico_actual)
        await interaction.response.edit_message(content=nuevo_texto, view=nueva_vista)


@bot.tree.command(name="inventario", description="Muestra tu inventario, minerales y te permite equipar picos.")
@app_commands.checks.cooldown(1, 5)
async def inventario(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)
    
    datos = await usuarios_col.find_one({"_id": uid})
    minerales_usuario = datos.get("minerales", {})
    picos_usuario = datos.get("picos", ["Pico de Madera (Por defecto)"])
    pico_actual = datos.get("pico_activo", {})
    pico_nombre_actual = pico_actual.get('nombre', 'Pico de Madera')

    texto_minerales = ""
    if minerales_usuario:
        for min_nombre, cantidad in minerales_usuario.items():
            if cantidad > 0:
                texto_minerales += f"• **{min_nombre}**: `{cantidad}`\n"
    else:
        texto_minerales = "No tienes minerales guardados."

    mensaje_inventario = (
        f"🎒 **Inventario de {interaction.user.name}**\n\n"
        f"⛏️ **Pico Equipado:** {pico_nombre_actual}\n"
        f"📋 **Picos Disponibles:** {', '.join(picos_usuario)}\n\n"
        f"💎 **Minerales:**\n{texto_minerales}"
    )

    view = VistaInventarioConEquipamiento(uid, picos_usuario, pico_nombre_actual)
    await interaction.followup.send(mensaje_inventario, view=view)
class VistaSeleccionCrafteo(discord.ui.View):
    def __init__(self, uid, recetas_dict):
        super().__init__(timeout=180)
        self.uid = uid
        self.recetas_dict = recetas_dict
        
        options = []
        for nombre, info in recetas_dict.items():
            bonus = info.get('bonus', 0)
            options.append(discord.SelectOption(label=nombre, description=f"Bonus: +{bonus}% | Ver receta y craftear"))
        
        if not options:
            options.append(discord.SelectOption(label="No hay picos", description="Un administrador debe añadir recetas con addcrafteo"))

        self.select_item = discord.ui.Select(placeholder="Selecciona un pico para ver su receta...", options=options)
        self.select_item.callback = self.seleccionar_callback
        self.add_item(self.select_item)

    async def seleccionar_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("❌ Este menú no es para ti.", ephemeral=True)
        
        item_elegido = self.select_item.values[0]
        info_receta = self.recetas_dict.get(item_elegido, {})
        costos = info_receta.get("costos", {}) # O si guardas los costos directos, ajústalo aquí
        bonus = info_receta.get("bonus", 0)
        
        vista_boton = VistaBotonCrafteo(self.uid, item_elegido, info_receta, self.recetas_dict)
        
        texto_receta = f"🛠️ **Receta para craftear: `{item_elegido}`** (+{bonus}% bonus)\n\n**Materiales necesarios:**\n"
        if isinstance(costos, dict) and costos:
            for mat, cant in costos.items():
                texto_receta += f"• **{mat}**: `{cant}` unidades\n"
        else:
            texto_receta += "• No hay costos configurados para este pico.\n"
            
        texto_receta += "\n¡Haz clic en el botón de abajo para fabricarlo!"
        
        await interaction.response.edit_message(content=texto_receta, view=vista_boton)


class VistaBotonCrafteo(discord.ui.View):
    def __init__(self, uid, item, info_receta, recetas_dict):
        super().__init__(timeout=180)
        self.uid = uid
        self.item = item
        self.info_receta = info_receta
        self.recetas_dict = recetas_dict

    @discord.ui.button(label="🔨 ¡Craftear Ahora!", style=discord.ButtonStyle.green)
    async def boton_craftear(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("❌ No puedes usar este botón.", ephemeral=True)
        
        await asegurar_usuario(self.uid)
        datos = await usuarios_col.find_one({"_id": self.uid})
        
        # Obtenemos los minerales reales del usuario según tu estructura
        minerales_usuario = datos.get("minerales", {})
        pico_actual = datos.get("pico_activo", {}).get("nombre", "Pico de Madera")
        
        costos = self.info_receta.get("costos", {})

        # Validar materiales y calcular faltantes
        materiales_faltantes = {}
        for mat, requerido in costos.items():
            tenido = minerales_usuario.get(mat, 0)
            if tenido < requerido:
                materiales_faltantes[mat] = requerido - tenido

        if materiales_faltantes:
            texto_faltantes = f"❌ **No tienes suficientes minerales.** (Llevas equipado: `{pico_actual}`). Te falta:\n"
            for mat, faltan in materiales_faltantes.items():
                texto_faltantes += f"• **{mat}**: te faltan `{faltan}` unidades\n"
            return await interaction.response.send_message(texto_faltantes, ephemeral=True)

        # Descontar minerales y añadir el pico al inventario/picos del usuario
        nuevos_minerales = minerales_usuario.copy()
        for mat, requerido in costos.items():
            nuevos_minerales[mat] -= requerido
            
        picos_usuario = datos.get("picos", ["Pico de Madera (Por defecto)"])
        if self.item not in picos_usuario:
            picos_usuario.append(self.item)

        await usuarios_col.update_one(
            {"_id": self.uid},
            {
                "$set": {
                    "minerales": nuevos_minerales,
                    "picos": picos_usuario
                }
            }
        )

        await interaction.response.send_message(f"✅ ¡Has crafteo exitosamente el pico **{self.item}**! Ya está disponible en tus picos.", ephemeral=True)

    @discord.ui.button(label="↩️ Volver al Menú", style=discord.ButtonStyle.gray)
    async def volver(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("❌ No puedes usar este botón.", ephemeral=True)
        
        vista_principal = VistaSeleccionCrafteo(self.uid, self.recetas_dict)
        await interaction.response.edit_message(content="🛠️ **Menú de Crafteo**\nSelecciona un pico del menú desplegable para ver su receta:", view=vista_principal)


@bot.tree.command(name="craftteo", description="Abre el menú de crafteo de picos interactivo.")
@app_commands.checks.cooldown(1, 10)
async def craftteo(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)
    
    # Leemos la configuración global exactamente como lo haces en tu código actual
    config = await usuarios_col.find_one({"_id": "configuracion_global"})
    recetas = config.get("recetas_crafteo", {}) if config else {}
    
    if not recetas:
        return await interaction.followup.send("❌ No hay picos ni recetas configuradas por el administrador todavía.", ephemeral=True)
    
    view = VistaSeleccionCrafteo(uid, recetas)
    await interaction.followup.send(
        "🛠️ **Menú de Crafteo de Picos**\nSelecciona un pico del menú desplegable para ver su receta:",
        view=view,
        ephemeral=False
        )
                                 

# /addcrafteo (Solo Administradores)
@bot.tree.command(name="addcrafteo", description="Configura los materiales y bonos de un pico crafteable (Admin).")
@app_commands.describe(
    nombre_pico="Nombre del pico",
    bonus_porcentaje="Porcentaje de bonificación (máximo 30%)",
    mineral_1="Primer mineral requerido", cantidad_1="Cantidad del mineral 1",
    mineral_2="Segundo mineral requerido (opcional)", cantidad_2="Cantidad del mineral 2",
    mineral_3="Tercer mineral requerido (opcional)", cantidad_3="Cantidad del mineral 3"
)
async def addcrafteo(
    interaction: discord.Interaction, 
    nombre_pico: str, 
    bonus_porcentaje: int,
    mineral_1: str, cantidad_1: int,
    mineral_2: str = None, cantidad_2: int = 0,
    mineral_3: str = None, cantidad_3: int = 0
):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ No tienes permisos de administrador para usar este comando.", ephemeral=True)
        
    if bonus_porcentaje > 30:
        return await interaction.response.send_message("❌ El porcentaje máximo de bonificación para un pico es de 30%.", ephemeral=True)
        
    await interaction.response.defer(ephemeral=True)
    
    costos = {mineral_1: cantidad_1}
    if mineral_2 and cantidad_2 > 0:
        costos[mineral_2] = cantidad_2
    if mineral_3 and cantidad_3 > 0:
        costos[mineral_3] = cantidad_3
        
    nueva_receta = {
        "nombre": nombre_pico,
        "bonus": bonus_porcentaje,
        "costos": costos
    }
    
    await usuarios_col.update_one(
        {"_id": "configuracion_global"},
        {"$set": {f"recetas_crafteo.{nombre_pico}": nueva_receta}},
        upsert=True
    )
    
    await interaction.followup.send(
        f"✅ ¡Receta del pico **{nombre_pico}** agregada con éxito!\n"
        f"• **Bonus:** +{bonus_porcentaje}%\n"
        f"• **Costos:** {costos}",
        ephemeral=True
)

# /indice_minerales
@bot.tree.command(name="indice_minerales", description="Muestra la lista, emojis y valores de todos los minerales disponibles.")
async def indice_minerales(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    
    descripcion = "💎 **Índice de Minerales Disponibles:**\n\n"
    for idx, mineral in enumerate(MINERALES_DATA, start=1):
        descripcion += f"{idx}. {mineral['emoji']} **{mineral['nombre']}** — Valor: `{mineral['valor']}` monedas\n"
    
    await interaction.followup.send(descripcion, ephemeral=False)

# --- JUEGO SUERTE DEL RATÓN (/suerte_raton [apuesta]) ---
class VistaSuerteRaton(discord.ui.View):
    def __init__(self, uid, apuesta, raton_pos):
        super().__init__(timeout=300)
        self.uid = uid
        self.apuesta = apuesta
        self.raton_pos = raton_pos
        self.intentos_restantes = 3
        self.intentos_usados = 0
        self.crear_botones()

    def crear_botones(self):
        self.clear_items()
        # Cuadrícula de 4x3 (12 casillas en total)
        for i in range(12):
            btn = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label=f"Casilla {i+1}",
                custom_id=f"raton_{i}",
                row=i // 3
            )
            btn.callback = self.callback_casilla
            self.add_item(btn)

    async def callback_casilla(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("❌ Este juego no es tuyo.", ephemeral=True)

        custom_id = interaction.data["custom_id"]
        elegida_idx = int(custom_id.split("_")[1])
        
        self.intentos_usados += 1
        self.intentos_restantes -= 1

        # Mapeo de cuadrícula 4 filas x 3 columnas (índices 0 al 11)
        fila_raton, col_raton = divmod(self.raton_pos, 3)
        fila_elegida, col_elegida = divmod(elegida_idx, 3)
        
        # Calcular distancia de Manhattan
        distancia = abs(fila_raton - fila_elegida) + abs(col_raton - col_elegida)

        # Buscar y actualizar el botón presionado
        for child in self.children:
            if child.custom_id == custom_id:
                if elegida_idx == self.raton_pos:
                    child.style = discord.ButtonStyle.success
                    child.label = "🐭 ¡Atrapado!"
                    child.disabled = True
                else:
                    child.style = discord.ButtonStyle.danger
                    child.label = f"❌ (Dist: {distancia})"
                    child.disabled = True

        # Si atrapó al ratón
        if elegida_idx == self.raton_pos:
            for child in self.children:
                child.disabled = True

            multiplicador = 3 if self.intentos_usados == 1 else 2
            ganancia_neta = self.apuesta * multiplicador - self.apuesta
            total_recibido = self.apuesta * multiplicador

            await asegurar_usuario(self.uid)
            await usuarios_col.update_one({"_id": self.uid}, {"$inc": {"dinero": ganancia_neta}})

            return await interaction.response.edit_message(
                content=f"🧀 **¡EXCELENTE!** ¡Atrapaste al ratón en el intento #{self.intentos_usados}!\n"
                        f"🎉 Multiplicador obtenido: **x{multiplicador}**\n"
                        f"💰 Ganaste **{total_recibido}** monedas en total.",
                view=self
            )

        # Si se le acabaron los intentos
        if self.intentos_restantes <= 0:
            for child in self.children:
                child.disabled = True
                if child.custom_id == f"raton_{self.raton_pos}":
                    child.style = discord.ButtonStyle.success
                    child.label = "🐭 ¡Era aquí!"

            await asegurar_usuario(self.uid)
            await usuarios_col.update_one({"_id": self.uid}, {"$inc": {"dinero": -self.apuesta}})

            return await interaction.response.edit_message(
                content=f"💀 **¡Te quedaste sin intentos!** El ratón se escapó.\n"
                        f"Perdiste tu apuesta de **{self.apuesta}** monedas.",
                view=self
            )

        # Si falló pero aún tiene intentos
        await interaction.response.edit_message(
            content=f"🔍 **Fallaste.** El ratón está a una distancia de **{distancia}** casillas.\n"
                    f"⚠️ Te quedan **{self.intentos_restantes}** intentos.",
            view=self
        )


@bot.tree.command(name="suerte_raton", description="Busca al ratón oculto en una cuadrícula de 12 casillas con pistas.")
@app_commands.checks.cooldown(1, 360)
@app_commands.describe(apuesta="Cantidad de dinero a apostar")
async def suerte_raton(interaction: discord.Interaction, apuesta: int):
    await interaction.response.defer(ephemeral=False)
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)
    
    datos = await usuarios_col.find_one({"_id": uid})
    if datos.get("dinero", 0) < apuesta or apuesta <= 0:
        return await interaction.followup.send("❌ No tienes suficiente dinero o la apuesta no es válida.", ephemeral=True)

    raton_oculto = random.randint(0, 11)
    view = VistaSuerteRaton(uid, apuesta, raton_oculto)
    
    await interaction.followup.send(
        f"🐭 **¡Juego de Suerte del Ratón!**\n"
        f"Apuesta: `{apuesta}` | Tienes **3 intentos** para atraparlo en la cuadrícula de abajo:",
        view=view,
        ephemeral=False
        )

    # --- JUEGO PAVO HAMBRIENTO (/pavo_hambriento [apuesta]) ---
class VistaPavoHambriento(discord.ui.View):
    def __init__(self, uid, apuesta, limite_explosion):
        super().__init__(timeout=600)
        self.uid = uid
        self.apuesta = apuesta
        self.limite_explosion = limite_explosion # En qué número de alimento explota
        self.alimentos_dados = 0
        self.multiplicador = 1.0

    @discord.ui.button(label="Alimentar Pavo 🦃", style=discord.ButtonStyle.primary)
    async def alimentar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("❌ Este juego no es tuyo.", ephemeral=True)

        self.alimentos_dados += 1
        self.multiplicador = round(self.multiplicador + 0.3, 2)

        # Si llega o supera el límite oculto de hambre, el pavo explota / se empacha
        if self.alimentos_dados >= self.limite_explosion:
            for child in self.children:
                child.disabled = True

            await asegurar_usuario(self.uid)
            await usuarios_col.update_one({"_id": self.uid}, {"$inc": {"dinero": -self.apuesta}})

            return await interaction.response.edit_message(
                content=f"💥 **¡El pavo se ha empachado y explotó!** Le diste comida **{self.alimentos_dados} veces** y se pasó del límite.\n"
                        f"Perdiste tu apuesta de **{self.apuesta}** monedas.",
                view=self
            )

        ganancia_actual = int(self.apuesta * self.multiplicador)
        await interaction.response.edit_message(
            content=f"🦃 **¡Le diste comida al pavo!**\n"
                    f"🍽️ Veces alimentado: **{self.alimentos_dados}**\n"
                    f"📈 Multiplicador actual: **{self.multiplicador}x**\n"
                    f"💰 Ganancia acumulada estimada: **{ganancia_actual}**\n"
                    f"⚠️ *¡Cuidado! No sabes cuándo se llenará por completo.*",
            view=self
        )

    @discord.ui.button(label="Cobrar y Salir 💰", style=discord.ButtonStyle.success)
    async def cobrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("❌ Este juego no es tuyo.", ephemeral=True)

        if self.alimentos_dados == 0:
            return await interaction.response.send_message("❌ Debes alimentar al pavo al menos una vez antes de cobrar.", ephemeral=True)

        for child in self.children:
            child.disabled = True

        total_recibido = int(self.apuesta * self.multiplicador)
        ganancia_neta = total_recibido - self.apuesta

        await asegurar_usuario(self.uid)
        await usuarios_col.update_one({"_id": self.uid}, {"$inc": {"dinero": ganancia_neta}})

        await interaction.response.edit_message(
            content=f"🎯 **¡CASH OUT EXITOSO CON EL PAVO!**\n"
                    f"🦃 Lo alimentaste **{self.alimentos_dados} veces**.\n"
                    f"📈 Multiplicador final: **{self.multiplicador}x**\n"
                    f"💰 Ganaste **{total_recibido}** monedas (+{ganancia_neta} neto).",
            view=self
        )


@bot.tree.command(name="pavo_hambriento", description="Alimenta al pavo sin que explote para multiplicar tus ganancias.")
@app_commands.checks.cooldown(1, 360)
@app_commands.describe(apuesta="Cantidad de dinero a apostar")
async def pavo_hambriento(interaction: discord.Interaction, apuesta: int):
    await interaction.response.defer(ephemeral=False)
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)
    
    datos = await usuarios_col.find_one({"_id": uid})
    if datos.get("dinero", 0) < apuesta or apuesta <= 0:
        return await interaction.followup.send("❌ No tienes suficiente dinero o la apuesta no es válida.", ephemeral=True)

    # El límite de cuántas veces soporta el pavo antes de estallar (por ejemplo, entre 3 y 8 veces)
    limite_explosion = random.randint(1, 5)
    
    view = VistaPavoHambriento(uid, apuesta, limite_explosion)
    
    await interaction.followup.send(
        f"🦃 **¡Comienza el juego del Pavo Hambriento!**\n"
        f"Apuesta: `{apuesta}` | Cada porción de comida sube la apuesta un **x0.3**.\n"
        f"Usa los botones de abajo con cuidado:",
        view=view,
        ephemeral=False
    )
    

# --- CONFIGURACIÓN DE LOS 8 TRABAJOS (Actualizada con pago máximo de 3000 y albañil hasta 500) ---
TRABAJOS_DATA = [
    {"nivel_req": 1, "nombre": "Albañil 🧱", "min_pago": 150, "max_pago": 500, "xp_da": 25},
    {"nivel_req": 3, "nombre": "Repartidor 🛵", "min_pago": 300, "max_pago": 850, "xp_da": 30},
    {"nivel_req": 6, "nombre": "Cajero 🛒", "min_pago": 500, "max_pago": 1200, "xp_da": 35},
    {"nivel_req": 10, "nombre": "Mecánico 🔧", "min_pago": 800, "max_pago": 1600, "xp_da": 40},
    {"nivel_req": 15, "nombre": "Programador 💻", "min_pago": 1100, "max_pago": 2100, "xp_da": 45},
    {"nivel_req": 21, "nombre": "Policía 👮", "min_pago": 1500, "max_pago": 2500, "xp_da": 50},
    {"nivel_req": 28, "nombre": "Médico 🩺", "min_pago": 2000, "max_pago": 2800, "xp_da": 55},
    {"nivel_req": 36, "nombre": "Empresario 👔", "min_pago": 2500, "max_pago": 3000, "xp_da": 60},
]

async def asegurar_perfil_trabajo(uid: str):
    await asegurar_usuario(uid)
    await usuarios_col.update_one(
        {"_id": uid, "trabajo": {"$exists": False}},
        {"$set": {"trabajo": 0, "xp_chamba": 0, "nivel_chamba": 1}}
    )


# --- 1. COMANDO /elegir_trabajo ---
class VistaElegirTrabajo(discord.ui.View):
    def __init__(self, uid, nivel_usuario):
        super().__init__(timeout=300)
        self.uid = uid
        
        for idx, trabajo in enumerate(TRABAJOS_DATA):
            disabled = nivel_usuario < trabajo["nivel_req"]
            estilo = discord.ButtonStyle.secondary if disabled else discord.ButtonStyle.success
            
            btn = discord.ui.Button(
                label=f"Nivel {trabajo['nivel_req']}: {trabajo['nombre'].split()[0]}",
                style=estilo,
                custom_id=f"trabajo_{idx}",
                disabled=disabled
            )
            btn.callback = self.callback_btn
            self.add_item(btn)

    async def callback_btn(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("❌ Este menú no es tuyo.", ephemeral=True)

        idx = int(interaction.data["custom_id"].split("_")[1])
        trabajo_elegido = TRABAJOS_DATA[idx]

        await usuarios_col.update_one({"_id": self.uid}, {"$set": {"trabajo": idx}})
        
        await interaction.response.edit_message(
            content=f"✅ ¡Has cambiado exitosamente tu empleo a **{trabajo_elegido['nombre']}**!",
            view=None
        )


@bot.tree.command(name="elegir_trabajo", description="Elige un nuevo trabajo disponible según tu nivel en chamba.")
async def elegir_trabajo(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    uid = str(interaction.user.id)
    await asegurar_perfil_trabajo(uid)

    datos = await usuarios_col.find_one({"_id": uid})
    nivel_chamba = datos.get("nivel_chamba", 1)
    trabajo_actual_idx = datos.get("trabajo", 0)

    if nivel_chamba < 3:
        return await interaction.followup.send("❌ Necesitas ser al menos **Nivel 3** en chamba para poder elegir un trabajo.", ephemeral=True)

    descripcion = "👷 **Selecciona tu nuevo empleo:**\nLos trabajos avanzados requieren mayor nivel pero pagan mucho más.\n\n"
    for idx, t in enumerate(TRABAJOS_DATA):
        estado = "✅ (Actual)" if idx == trabajo_actual_idx else ("🔒 (Bloqueado)" if nivel_chamba < t["nivel_req"] else "🔓 (Disponible)")
        descripcion += f"• **{t['nombre']}** — Req. Nivel {t['nivel_req']} {estado}\n"

    view = VistaElegirTrabajo(uid, nivel_chamba)
    await interaction.followup.send(descripcion, view=view, ephemeral=False)


# --- 2. COMANDO /nivel_chamba ---
@bot.tree.command(name="nivel_chamba", description="Muestra tu nivel, XP actual y cuánto te falta para el siguiente trabajo.")
async def nivel_chamba(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    uid = str(interaction.user.id)
    await asegurar_perfil_trabajo(uid)

    datos = await usuarios_col.find_one({"_id": uid})
    nivel = datos.get("nivel_chamba", 1)
    xp = datos.get("xp_chamba", 0)
    trabajo_idx = datos.get("trabajo", 0)
    trabajo_actual = TRABAJOS_DATA[trabajo_idx]

    xp_necesaria = nivel * 100
    
    proximo_trabajo = None
    for t in TRABAJOS_DATA:
        if t["nivel_req"] > nivel:
            proximo_trabajo = t
            break

    info_prox = f"• Próximo empleo: **{proximo_trabajo['nombre']}** (Requiere Nivel {proximo_trabajo['nivel_req']})" if proximo_trabajo else "• ¡Has alcanzado el rango máximo de empleos!"

    await interaction.followup.send(
        f"📊 **Estadísticas de Chamba de {interaction.user.name}**\n\n"
        f"👔 Trabajo actual: **{trabajo_actual['nombre']}**\n"
        f"⭐ Nivel en Chamba: `{nivel}`\n"
        f"✨ Experiencia (XP): `{xp} / {xp_necesaria}`\n"
        f"{info_prox}",
        ephemeral=False
    )


# --- 3. COMANDO /trabajo (Cooldown: 2 minutos / 120 seg) ---
@bot.tree.command(name="trabajo", description="Trabaja en tu empleo actual para ganar dinero y experiencia.")
@app_commands.checks.cooldown(1, 120)
async def trabajo(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    uid = str(interaction.user.id)
    await asegurar_perfil_trabajo(uid)

    datos = await usuarios_col.find_one({"_id": uid})
    trabajo_idx = datos.get("trabajo", 0)
    nivel = datos.get("nivel_chamba", 1)
    xp = datos.get("xp_chamba", 0)

    t_info = TRABAJOS_DATA[trabajo_idx]
    
    # Generar pago adaptado al rango del trabajo seleccionado (máximo 3000)
    pago = random.randint(t_info["min_pago"], t_info["max_pago"])
    ganancia_xp = t_info["xp_da"]

    nueva_xp = xp + ganancia_xp
    nuevo_nivel = nivel
    xp_limite = nivel * 100

    subio_nivel = False
    if nueva_xp >= xp_limite:
        nueva_xp -= xp_limite
        nuevo_nivel += 1
        subio_nivel = True

    await usuarios_col.update_one(
        {"_id": uid},
        {
            "$inc": {"dinero": pago},
            "$set": {"xp_chamba": nueva_xp, "nivel_chamba": nuevo_nivel}
        }
    )

    msg = (
        f"💼 **¡Jornada laboral completada como {t_info['nombre']}!**\n"
        f"💵 Ganaste: **{pago}** monedas\n"
        f"✨ Experiencia obtenida: `+{ganancia_xp} XP`"
    )

    if subio_nivel:
        msg += f"\n\n🎉 **¡FELICIDADES! Subiste al Nivel {nuevo_nivel} de Chamba.** ¡Revisa /elegir_trabajo para ver si hay nuevos empleos!"

    await interaction.followup.send(msg, ephemeral=False)


# --- CLASE 1: Menú de selección de ítems para el inventario ---
class SelectInventarioTrade(discord.ui.Select):
    def __init__(self, datos_usuario, duenio_id, callback_origen):
        self.duenio_id = duenio_id
        self.callback_origen = callback_origen
        options = []
        
        # 1. Dinero en mano
        dinero = datos_usuario.get("dinero", 0)
        if dinero > 0:
            options.append(discord.SelectOption(label=f"Dinero: {dinero:,} monedas", value="dinero", description="Ofrecer dinero en mano", emoji="💰"))
        
        # 2. XP de Chamba
        xp_chamba = datos_usuario.get("xp_chamba", 0)
        if xp_chamba > 0:
            options.append(discord.SelectOption(label=f"XP Chamba: {xp_chamba:,}", value="xp_chamba", description="Ofrecer experiencia de trabajo", emoji="✨"))
        
        # 3. Nivel de Chamba
        nivel_chamba = datos_usuario.get("nivel_chamba", 1)
        if nivel_chamba > 1:
            options.append(discord.SelectOption(label=f"Nivel de Chamba: Nvl {nivel_chamba}", value="nivel_chamba", description="Ofrecer niveles de trabajo", emoji="👔"))
        
        # 4. Picos
        picos = datos_usuario.get("picos", [])
        for pico in picos[:8]:
            options.append(discord.SelectOption(label=f"Pico: {pico}", value=f"pico_{pico}", description="Ofrecer este pico", emoji="⛏️"))
            
        # 5. Minerales
        minerales = datos_usuario.get("minerales", {})
        for min_nombre, cant in list(minerales.items())[:8]:
            if cant > 0:
                options.append(discord.SelectOption(label=f"Mineral: {min_nombre} (x{cant})", value=f"mineral_{min_nombre}", description="Ofrecer este mineral", emoji="💎"))

        # 6. Mascota
        if datos_usuario.get("tiene_mascota_propia", False):
            nombre_m = datos_usuario.get("mascota_nombre", "Mascota")
            emoji_m = datos_usuario.get("mascota_emoji", "🐾")
            options.append(discord.SelectOption(label=f"Mascota: {nombre_m}", value="mascota", description="Ofrecer tu mascota actual", emoji=emoji_m))

        if not options:
            options.append(discord.SelectOption(label="Nada que ofrecer", value="nada", description="No tienes ítems disponibles"))

        super().__init__(placeholder="Selecciona qué objeto deseas ofrecer...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.duenio_id:
            return await interaction.response.send_message("❌ Este menú de trade no te pertenece.", ephemeral=True)
        
        # Guardamos la selección y pasamos al siguiente paso
        await self.callback_origen(interaction, self.values[0])


# --- CLASE 2: Vista de Confirmación Final (Antiestafa) ---
class VistaConfirmarTrade(discord.ui.View):
    def __init__(self, emisor_id, receptor_id, oferta_emisor, oferta_receptor):
        super().__init__(timeout=60)
        self.emisor_id = emisor_id
        self.receptor_id = receptor_id
        self.oferta_emisor = oferta_emisor
        self.oferta_receptor = oferta_receptor
        self.confirmados = set()
        self.completado = False

    @discord.ui.button(label="✅ Confirmar Intercambio", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if uid != self.emisor_id and uid != self.receptor_id:
            return await interaction.response.send_message("❌ No formas parte de este intercambio.", ephemeral=True)

        self.confirmados.add(uid)

        if len(self.confirmados) == 2:
            self.completado = True
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(content="🔄 **¡Ambos confirmaron! Procesando transferencia segura en la base de datos...**", view=self)
            self.stop()
        else:
            await interaction.response.edit_message(content=f"⏳ <@{uid}> ha confirmado. Falta que la otra parte confirme para ejecutar el trade.", view=self)

    @discord.ui.button(label="❌ Cancelar Trade", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if uid != self.emisor_id and uid != self.receptor_id:
            return await interaction.response.send_message("❌ No puedes cancelar esto.", ephemeral=True)
        
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="❌ El intercambio ha sido cancelado.", view=self)
        self.stop()


# --- CLASE 3: Vista temporal para contener el select ---
class VistaMenuUnico(discord.ui.View):
    def __init__(self, datos_usuario, duenio_id, callback_origen):
        super().__init__(timeout=60)
        self.add_item(SelectInventarioTrade(datos_usuario, duenio_id, callback_origen))


# --- COMANDO /TRADE PRINCIPAL ---
@bot.tree.command(name="trade", description="Inicia un intercambio seguro de picos, minerales, dinero, XP, chamba o mascotas.")
@app_commands.checks.cooldown(1, 15)
@app_commands.describe(usuario="Usuario con el que deseas realizar el intercambio")
async def trade(interaction: discord.Interaction, usuario: discord.Member):
    emisor_id = str(interaction.user.id)
    receptor_id = str(usuario.id)

    if emisor_id == receptor_id:
        return await interaction.response.send_message("❌ No puedes hacer un trade contigo mismo.", ephemeral=True)

    await asegurar_usuario(emisor_id)
    await asegurar_usuario(receptor_id)

    # 1. Solicitud inicial
    class VistaSolicitud(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
            self.aceptado = False

        @discord.ui.button(label="Aceptar Trade", style=discord.ButtonStyle.success)
        async def aceptar(self, inter: discord.Interaction, btn: discord.ui.Button):
            if str(inter.user.id) != receptor_id:
                return await inter.response.send_message("❌ Esta solicitud no es para ti.", ephemeral=True)
            self.aceptado = True
            for child in self.children: child.disabled = True
            await inter.response.edit_message(content=f"✅ ¡Trade aceptado por <@{receptor_id}>!", view=self)
            self.stop()

        @discord.ui.button(label="Rechazar", style=discord.ButtonStyle.danger)
        async def rechazar(self, inter: discord.Interaction, btn: discord.ui.Button):
            if str(inter.user.id) != receptor_id:
                return await inter.response.send_message("❌ No puedes rechazar esto.", ephemeral=True)
            for child in self.children: child.disabled = True
            await inter.response.edit_message(content=f"❌ Solicitud de trade rechazada.", view=self)
            self.stop()

    vista_sol = VistaSolicitud()
    await interaction.response.send_message(
        f"🤝 **Solicitud de Intercambio**\n<@{receptor_id}>, <@{emisor_id}> quiere iniciar un trade seguro contigo.",
        view=vista_sol, ephemeral=False
    )
    msg_sol = await interaction.original_response()

    await vista_sol.wait()
    if not vista_sol.aceptado:
        await asyncio.sleep(5)
        try: await msg_sol.delete()
        except: pass
        return

    # Variables para almacenar qué va a dar cada uno
    seleccion_emisor = None
    seleccion_receptor = None

    # 2. Turno del Emisor para elegir
    async def cb_emisor(inter, eleccion):
        nonlocal seleccion_emisor
        seleccion_emisor = eleccion
        await inter.response.edit_message(content=f"📦 <@{emisor_id}> ha seleccionado su oferta.", view=None)

    datos_emisor = await usuarios_col.find_one({"_id": emisor_id})
    msg_e = await interaction.followup.send(
        f"💼 **Turno de <@{emisor_id}> (Emisor):** Elige qué vas a ofrecer:",
        view=VistaMenuUnico(datos_emisor, emisor_id, cb_emisor), ephemeral=False
    )

    # Esperar a que el emisor elija (máximo 60s)
    while seleccion_emisor is None:
        await asyncio.sleep(1)

    # 3. Turno del Receptor para elegir
    async def cb_receptor(inter, eleccion):
        nonlocal seleccion_receptor
        seleccion_receptor = eleccion
        await inter.response.edit_message(content=f"📦 <@{receptor_id}> ha seleccionado su oferta.", view=None)

    datos_receptor = await usuarios_col.find_one({"_id": receptor_id})
    msg_r = await interaction.followup.send(
        f"💼 **Turno de <@{receptor_id}> (Receptor):** Elige qué vas a ofrecer:",
        view=VistaMenuUnico(datos_receptor, receptor_id, cb_receptor), ephemeral=False
    )

    while seleccion_receptor is None:
        await asyncio.sleep(1)

    # 4. Panel de Resumen y Doble Confirmación Antiestafa
    vista_conf = VistaConfirmarTrade(emisor_id, receptor_id, seleccion_emisor, seleccion_receptor)
    msg_conf = await interaction.followup.send(
        f"⚖️ **Resumen del Intercambio**\n\n"
        f"• <@{emisor_id}> ofrece: `{seleccion_emisor}`\n"
        f"• <@{receptor_id}> ofrece: `{seleccion_receptor}`\n\n"
        f"⚠️ **Verifiquen bien antes de confirmar. Ambos deben presionar el botón verde.**",
        view=vista_conf, ephemeral=False
    )

    await vista_conf.wait()

    # 5. Ejecución Atómica en MongoDB si ambos aceptaron
    if vista_conf.completado:
        # AQUÍ PROGRAMAS TU LÓGICA DE TRANSACCIÓN REAL USANDO `update_one`
        # (Ej: restar a uno y sumar al otro según lo que contenga `seleccion_emisor` y `seleccion_receptor`)
        
        await interaction.followup.send(f"🎉 **¡Intercambio realizado con éxito y de forma segura!**", ephemeral=False)
    else:
        await interaction.followup.send(f"❌ El intercambio fue cancelado o expiró.", ephemeral=False)

    # Borrar mensajes del trade 5 segundos después
    await asyncio.sleep(5)
    try:
        await msg_sol.delete()
        await msg_e.delete()
        await msg_r.delete()
        await msg_conf.delete()
    except:
        pass
        
# --- COMANDO 2: /pagar_prestamo ---
@bot.tree.command(name="pagar_prestamo", description="Paga total o parcialmente tu deuda pendiente con el banco.")
@app_commands.checks.cooldown(1, 10)
@app_commands.describe(cantidad="Cantidad de monedas que vas a abonar o pagar")
async def pagar_prestamo(interaction: discord.Interaction, cantidad: int):
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)

    if cantidad <= 0:
        return await interaction.response.send_message("❌ Ingresa una cantidad válida para pagar.", ephemeral=True)

    datos = await usuarios_col.find_one({"_id": uid})
    dinero_mano = datos.get("dinero", 0)
    deuda_actual = datos.get("prestamo", 0)

    if deuda_actual <= 0:
        return await interaction.response.send_message("✅ ¡No tienes ninguna deuda pendiente con el banco!", ephemeral=True)

    if dinero_mano < cantidad:
        return await interaction.response.send_message(f"❌ No tienes suficiente dinero en mano. Tienes **{dinero_mano:,} monedas**.", ephemeral=True)

    # Si intenta pagar más de lo que debe, ajustamos al monto exacto de la deuda
    pago_efectivo = min(cantidad, deuda_actual)
    nueva_deuda = deuda_actual - pago_efectivo

    # Restar dinero en mano y actualizar la deuda en MongoDB
    await usuarios_col.update_one(
        {"_id": uid},
        {
            "$inc": {"dinero": -pago_efectivo},
            "$set": {"prestamo": nueva_deuda}
        }
    )

    if nueva_deuda == 0:
        await interaction.response.send_message(
            f"🎉 **¡Deuda Saldada!** Has pagado **{pago_efectivo:,} monedas**. Ya no le debes nada al banco.",
            ephemeral=False
        )
    else:
        await interaction.response.send_message(
            f"💳 Has abonado **{pago_efectivo:,} monedas** a tu préstamo.\n📉 Deuda restante: **{nueva_deuda:,} monedas**.",
            ephemeral=False
        )


# --- COMANDO 3: /estado_prestamo ---
@bot.tree.command(name="estado_prestamo", description="Revisa si tienes deudas activas con el banco.")
@app_commands.checks.cooldown(1, 5)
async def estado_prestamo(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)

    datos = await usuarios_col.find_one({"_id": uid})
    deuda = datos.get("prestamo", 0)

    if deuda > 0:
        await interaction.response.send_message(
            f"📊 **Estado Financiero**\n🔴 Tienes una deuda activa de: **{deuda:,} monedas**.\nUsa `/pagar_prestamo` para saldarla.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"📊 **Estado Financiero**\n🟢 ¡Estás limpio! No tienes deudas pendientes con el banco.",
            ephemeral=True
        )

# --- VISTA 1: Botones de Aceptar o Rechazar Préstamo ---
class VistaDecisionPrestamo(discord.ui.View):
    def __init__(self, solicitante_id, cantidad):
        super().__init__(timeout=60)
        self.solicitante_id = solicitante_id
        self.cantidad = cantidad
        self.aprobado = None

    @discord.ui.button(label="Aceptar Préstamo", style=discord.ButtonStyle.success, emoji="✅")
    async def aceptar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Cualquiera puede presionar el botón para aprobarlo o tomarlo (según tu lógica de banco comunitario o bot general)
        self.aprobado = True
        for child in self.children:
            child.disabled = True
        
        # Otorgar el préstamo en MongoDB al solicitante
        await asegurar_usuario(self.solicitante_id)
        await usuarios_col.update_one(
            {"_id": self.solicitante_id},
            {
                "$inc": {"dinero": self.cantidad},
                "$set": {"prestamo": self.cantidad}
            }
        )

        await interaction.response.edit_message(
            content=f"🏦 **¡Préstamo Aprobado!**\nEl préstamo de **{self.cantidad:,} monedas** solicitado por <@{self.solicitante_id}> ha sido aceptado y entregado por <@{interaction.user.id}>.",
            view=self
        )
        self.stop()

    @discord.ui.button(label="Rechazar", style=discord.ButtonStyle.danger, emoji="❌")
    async def rechazar(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.aprobado = False
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=f"❌ El préstamo de **{self.cantidad:,} monedas** solicitado por <@{self.solicitante_id}> fue rechazado.",
            view=self
        )
        self.stop()


# --- COMANDO /PRESTAMO CON BOTONES ---
@bot.tree.command(name="prestamo", description="Solicita un préstamo bancario interactivo.")
@app_commands.checks.cooldown(1, 30)
@app_commands.describe(cantidad="Cantidad de monedas que deseas pedir prestadas")
async def prestamo(interaction: discord.Interaction, cantidad: int):
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)

    if cantidad <= 0:
        return await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)

    if cantidad > 10000:
        return await interaction.response.send_message("❌ El banco no te puede prestar más de **10,000 monedas** de golpe.", ephemeral=True)

    datos = await usuarios_col.find_one({"_id": uid})
    deuda_actual = datos.get("prestamo", 0)

    if deuda_actual > 0:
        return await interaction.response.send_message(
            f"❌ Ya tienes un préstamo activo de **{deuda_actual:,} monedas**. Debes pagarlo antes de pedir otro.",
            ephemeral=True
        )

    # Crear la vista con los botones interactivos
    vista = VistaDecisionPrestamo(uid, cantidad)

    await interaction.response.send_message(
        f"📋 **Solicitud de Préstamo**\n<@{uid}> ha solicitado un préstamo por **{cantidad:,} monedas**.\n¿Deseas aceptar o cancelar esta solicitud?",
        view=vista,
        ephemeral=False
    )
    

# --- COMANDOS DE MASCOTAS (Integrados con la estructura base) ---

@bot.tree.command(name="comprar_mascota", description="Adopta y personaliza tu compañero virtual.")
@app_commands.describe(nombre="Nombre para tu mascota", emoji="Emoji representativo (ej: 🐶, 🐱)")
async def comprar_mascota(interaction: discord.Interaction, nombre: str, emoji: str):
    await interaction.response.defer(ephemeral=False)
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)

    datos = await usuarios_col.find_one({"_id": uid})
    if datos.get("tiene_mascota_propia", False):
        return await interaction.followup.send("❌ Ya tienes una mascota adoptada.", ephemeral=True)

    # Costo por adopción (puedes ajustarlo si deseas)
    costo = 1000
    if datos.get("dinero", 0) < costo:
        return await interaction.followup.send(f"❌ No tienes suficiente dinero. Adoptar una mascota cuesta **{costo}** monedas.", ephemeral=True)

    await usuarios_col.update_one(
        {"_id": uid},
        {
            "$inc": {"dinero": -costo},
            "$set": {
                "tiene_mascota_propia": True,
                "mascota_nombre": nombre,
                "mascota_emoji": emoji,
                "mascota_nivel": 1
            }
        }
    )

    await interaction.followup.send(
        f"🎉 **¡Felicidades por tu adopción!**\n"
        f"Has adoptado a {emoji} **{nombre}** con éxito.",
        ephemeral=False
    )


@bot.tree.command(name="mejorar_mascota", description="Sube de nivel a tu mascota para potenciar sus estadísticas y hallazgos.")
async def mejorar_mascota(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)

    datos = await usuarios_col.find_one({"_id": uid})
    if not datos.get("tiene_mascota_propia", False):
        return await interaction.followup.send("❌ No tienes ninguna mascota. Usa `/comprar_mascota` primero.", ephemeral=True)

    nivel_actual = datos.get("mascota_nivel", 1)
    costo_mejora = nivel_actual * 750  # El costo sube según el nivel

    if datos.get("dinero", 0) < costo_mejora:
        return await interaction.followup.send(f"❌ No tienes suficiente dinero. Subir de nivel a tu mascota cuesta **{costo_mejora}** monedas.", ephemeral=True)

    await usuarios_col.update_one(
        {"_id": uid},
        {
            "$inc": {"dinero": -costo_mejora, "mascota_nivel": 1}
        }
    )

    await interaction.followup.send(
        f"⭐ **¡Mejora exitosa!** Tu mascota {datos.get('mascota_emoji')} **{datos.get('mascota_nombre')}** ha subido al **Nivel {nivel_actual + 1}**.",
        ephemeral=False
    )


@bot.tree.command(name="ver_mascota", description="Revisa el estado, nivel y nombre de tu mascota o la de otro usuario.")
@app_commands.describe(usuario="Usuario del que deseas ver la mascota (opcional)")
async def ver_mascota(interaction: discord.Interaction, usuario: discord.Member = None):
    await interaction.response.defer(ephemeral=False)
    target = usuario or interaction.user
    uid = str(target.id)
    await asegurar_usuario(uid)

    datos = await usuarios_col.find_one({"_id": uid})
    if not datos.get("tiene_mascota_propia", False):
        msg = f"❌ {target.mention} no tiene ninguna mascota adoptada." if usuario else "❌ No tienes ninguna mascota adoptada."
        return await interaction.followup.send(msg, ephemeral=True)

    nombre = datos.get("mascota_nombre", "Mascota")
    emoji = datos.get("mascota_emoji", "🐾")
    nivel = datos.get("mascota_nivel", 1)

    await interaction.followup.send(
        f"🐾 **Información de Mascota ({target.name})**\n\n"
        f"• Nombre: {emoji} **{nombre}**\n"
        f"• Nivel: `{nivel}`\n"
        f"• Estado: ¡Lista para buscar tesoros con `/buscar_tesoro_mascota`!",
        ephemeral=False
    )


# --- CARRERA DE MASCOTAS (/carrera_mascota [apuesta]) ---
class VistaCarreraMascota(discord.ui.View):
    def __init__(self, uid, apuesta):
        super().__init__(timeout=80)
        self.uid = uid
        self.apuesta = apuesta

    @discord.ui.button(label="¡Competir contra Z6 🤖!", style=discord.ButtonStyle.primary, emoji="🏁")
    async def competir_z6(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("❌ Esta carrera no es tuya.", ephemeral=True)

        for child in self.children:
            child.disabled = True

        # Probabilidad de ganar a Z6 (50%)
        gana_usuario = random.choice([True, False])
        await asegurar_usuario(self.uid)

        if gana_usuario:
            premio = self.apuesta * 2
            await usuarios_col.update_one({"_id": self.uid}, {"$inc": {"dinero": self.apuesta}}) # Gana su apuesta de vuelta + ganancia neta igual
            await interaction.response.edit_message(
                content=f"🏆 **¡Victoria en la carrera!** Tu mascota corrió con todo y le ganó a Z6. Ganaste **{premio}** monedas.",
                view=self
            )
        else:
            await usuarios_col.update_one({"_id": self.uid}, {"$inc": {"dinero": -self.apuesta}})
            await interaction.response.edit_message(
                content=f"💨 **¡Derrota!** Z6 fue más rápido esta vez. Perdiste tu apuesta de **{self.apuesta}** monedas.",
                view=self
            )


@bot.tree.command(name="carrera_mascota", description="Pon a competir a tu mascota contra Z6 para duplicar tu apuesta.")
@app_commands.describe(apuesta="Cantidad de dinero a apostar en la carrera")
@app_commands.checks.cooldown(1, 300)
async def carrera_mascota(interaction: discord.Interaction, apuesta: int):
    await interaction.response.defer(ephemeral=False)
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)

    datos = await usuarios_col.find_one({"_id": uid})
    if not datos.get("tiene_mascota_propia", False):
        return await interaction.followup.send("❌ Necesitas adoptar una mascota con `/comprar_mascota` para competir.", ephemeral=True)

    if datos.get("dinero", 0) < apuesta or apuesta <= 0:
        return await interaction.followup.send("❌ No tienes suficiente dinero o la cantidad no es válida.", ephemeral=True)

    nombre_mascota = datos.get("mascota_nombre", "Mascota")
    emoji_mascota = datos.get("mascota_emoji", "🐾")

    view = VistaCarreraMascota(uid, apuesta)
    await interaction.followup.send(
        f"🏁 **¡Carrera de Mascotas!**\n"
        f"Tu mascota {emoji_mascota} **{nombre_mascota}** está lista en la línea de salida.\n"
        f"Apuesta actual: `{apuesta}` monedas. Presiona el botón para iniciar:",
        view=view,
        ephemeral=False
    )


# --- BUSCAR TESORO CON MASCOTA (Cooldown: 10 minutos / 600 seg) ---
@bot.tree.command(name="buscar_tesoro_mascota", description="Envía a tu mascota a buscar tesoros ocultos y desenterrar monedas.")
@app_commands.checks.cooldown(1, 600)
async def buscar_tesoro_mascota(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)

    datos = await usuarios_col.find_one({"_id": uid})
    
    if not datos.get("tiene_mascota_propia", False):
        return await interaction.followup.send("❌ No tienes ninguna mascota adoptada. Usa `/comprar_mascota` primero.", ephemeral=True)

    nombre_mascota = datos.get("mascota_nombre", "Mascota")
    emoji_mascota = datos.get("mascota_emoji", "🐾")
    nivel_mascota = datos.get("mascota_nivel", 1)

    # Varía según el nivel de la mascota, topado en un máximo de 8,000 monedas
    calculo_premio = min(200 + (nivel_mascota * 400) + random.randint(0, 600), 8000)

    await usuarios_col.update_one({"_id": uid}, {"$inc": {"dinero": calculo_premio}})

    await interaction.followup.send(
        f"🗺️ **¡Expedición de Tesoro completada!**\n"
        f"<@{uid}>, tu mascota {emoji_mascota} **{nombre_mascota}** ha encontrado **{calculo_premio}** monedas desenterrándolas del suelo.",
        ephemeral=False
    )

import asyncio
import re

# IDs de los dueños permitidos para usar estos comandos
DUENOS_IDS = {
    1491476806203740373,
    1209982260892409920,
    1439675836746829986
}

def es_dueno(interaction: discord.Interaction) -> bool:
    return interaction.user.id in DUENOS_IDS

def parsear_tiempo(tiempo_str: str) -> int:
    """Convierte cadenas como '3m', '1h', '30s' a segundos totales."""
    match = re.match(r"^(\d+)([smhd])$", tiempo_str.lower().strip())
    if not match:
        return 0
    cantidad, unidad = int(match.group(1)), match.group(2)
    multiplicadores = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return cantidad * multiplicadores.get(unidad, 1)


# --- VISTA PARA RECLAMAR EL SORTEO ---
class VistaClaimSorteo(discord.ui.View):
    def __init__(self, ganador_id: int, premio: str, tiempo_claim_seg: int, original_interaction: discord.Interaction, rerolls_restantes: int, tiempo_total_str: str, imagen_url: str):
        super().__init__(timeout=tiempo_claim_seg)
        self.ganador_id = ganador_id
        self.premio = premio
        self.original_interaction = original_interaction
        self.rerolls_restantes = rerolls_restantes
        self.tiempo_total_str = tiempo_total_str
        self.imagen_url = imagen_url
        self.reclamado = False

    @discord.ui.button(label="🎉 ¡Reclamar Sorteo!", style=discord.ButtonStyle.success)
    async def reclamar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ganador_id:
            return await interaction.response.send_message("❌ ¡Este sorteo no es para ti! Debes esperar a que expire el tiempo de reclamo si no lo reclama.", ephemeral=True)

        self.reclamado = True
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=f"🎁 **¡Sorteo finalizado y reclamado con éxito!**\n"
                    f"🏆 Ganador: <@{self.ganador_id}>\n"
                    f"🏆 Premio: **{self.premio}**",
            view=self
        )
        self.stop()

    async def on_timeout(self):
        if self.reclamado:
            return

        # Desactivar botones si expira el tiempo de claim
        for child in self.children:
            child.disabled = True

        try:
            await self.message.edit(
                content=f"⏳ **Tiempo de reclamo expirado.** El ganador (<@{self.ganador_id}>) no reclamó a tiempo.",
                view=self
            )
        except Exception:
            pass

        # Realizar Reroll automático si quedan intentos
        if self.rerolls_restantes > 0:
            await ejecutar_reroll_automatico(self.original_interaction, self.premio, self.rerolls_restantes - 1, self.tiempo_total_str, self.imagen_url)


async def ejecutar_reroll_automatico(interaction: discord.Interaction, premio: str, rerolls_restantes: int, tiempo_str: str, imagen_url: str):
    # Obtener los miembros del canal/servidor para seleccionar un nuevo ganador al azar
    guild = interaction.guild
    miembros = [m for m in guild.members if not m.bot]
    
    if not miembros:
        return await interaction.followup.send("❌ No hay participantes válidos para hacer reroll automático.", ephemeral=False)

    nuevo_ganador = random.choice(miembros)
    tiempo_claim_seg = 180  # 3 minutos por defecto para el claim del reroll

    embed = discord.Embed(
        title="🎁 ¡Reroll Automático de Sorteo!",
        description=f"El ganador anterior no reclamó a tiempo.\n\n"
                    f"🏆 Premio: **{premio}**\n"
                    f"👤 Nuevo Ganador Mencionado: {nuevo_ganador.mention}\n"
                    f"⏰ Tienes **3 minutos** para presionar el botón y reclamar.",
        color=discord.Color.gold()
    )
    if imagen_url:
        embed.set_image(url=imagen_url)

    view = VistaClaimSorteo(nuevo_ganador.id, premio, tiempo_claim_seg, interaction, rerolls_restantes, tiempo_str, imagen_url)
    
    msg = await interaction.channel.send(content=f"🚨 **¡Reroll automático!** {nuevo_ganador.mention}", embed=embed, view=view)
    view.message = msg


# --- 1. COMANDO /sorteo_economia (Solo Dueños) ---
@bot.tree.command(name="sorteo_economia", description="Sorteo interactivo avanzado con botón de reclamo y caducidad automática.")
@app_commands.describe(
    premio="Descripción o nombre del premio",
    tiempo="Duración del sorteo (ej: 1h, 30m, 10s)",
    cantidad_reroll="Número de veces que se repetirá automáticamente si no se reclama",
    tiempo_claim="Tiempo límite para reclamar (ej: 3m)",
    imagen="Imagen adjunta desde tus archivos para el sorteo"
)
async def sorteo_economia(
    interaction: discord.Interaction, 
    premio: str, 
    tiempo: str, 
    cantidad_reroll: int, 
    tiempo_claim: str, 
    imagen: discord.Attachment = None
):
    if not es_dueno(interaction):
        return await interaction.response.send_message("❌ No tienes permisos para usar este comando de dueño.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    t_segundos = parsear_tiempo(tiempo)
    c_segundos = parsear_tiempo(tiempo_claim)

    if t_segundos <= 0 or c_segundos <= 0:
        return await interaction.followup.send("❌ Formato de tiempo inválido. Usa sufijos como `s`, `m`, `h` (ej: `3m`, `1h`).", ephemeral=True)

    imagen_url = imagen.url if imagen else None

    embed = discord.Embed(
        title="🎁 ¡Nuevo Sorteo de Economía!",
        description=f"🏆 Premio: **{premio}**\n"
                    f"⏳ Tiempo restante para el sorteo: **{tiempo}**\n"
                    f"🔄 Rerolls disponibles: `{cantidad_reroll}`\n"
                    f"⏱️ Tiempo límite de reclamo: `{tiempo_claim}`",
        color=discord.Color.blurple()
    )
    if imagen_url:
        embed.set_image(url=imagen_url)

    msg_sorteo = await interaction.channel.send(embed=embed)
    await interaction.followup.send("✅ Sorteo iniciado correctamente en el canal.", ephemeral=True)

    # Esperar a que termine el tiempo del sorteo principal
    await asyncio.sleep(t_segundos)

    # Elegir ganador inicial
    guild = interaction.guild
    miembros = [m for m in guild.members if not m.bot]

    if not miembros:
        return await msg_sorteo.edit(content="❌ El sorteo terminó pero no hay participantes disponibles.", embed=None, view=None)

    ganador_inicial = random.choice(miembros)

    embed_ganador = discord.Embed(
        title="🎉 ¡Sorteo Finalizado!",
        description=f"🏆 Premio: **{premio}**\n"
                    f"👑 Ganador: {ganador_inicial.mention}\n\n"
                    f"⚠️ Tienes `{tiempo_claim}` para presionar el botón de abajo y reclamar.",
        color=discord.Color.green()
    )
    if imagen_url:
        embed_ganador.set_image(url=imagen_url)

    view = VistaClaimSorteo(ganador_inicial.id, premio, c_segundos, interaction, cantidad_reroll, tiempo, imagen_url)
    
    await msg_sorteo.edit(content=f"🔔 **¡Tenemos un ganador!** {ganador_inicial.mention}", embed=embed_ganador, view=view)
    view.message = msg_sorteo


# --- 2. COMANDO /dar (Solo Dueños) ---
@bot.tree.command(name="dar", description="Entrega dinero directamente a un usuario.")
@app_commands.describe(usuario="Usuario al que se le entregará el dinero", cantidad="Cantidad de monedas a otorgar")
async def dar(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    if not es_dueno(interaction):
        return await interaction.response.send_message("❌ No tienes permisos para usar este comando de dueño.", ephemeral=True)

    if cantidad <= 0:
        return await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    uid = str(usuario.id)
    await asegurar_usuario(uid)

    await usuarios_col.update_one({"_id": uid}, {"$inc": {"dinero": cantidad}})

    await interaction.followup.send(f"✅ Se han entregado exitosamente **{cantidad}** monedas a {usuario.mention}.", ephemeral=False)


# --- 3. COMANDO /quitar (Solo Dueños) ---
@bot.tree.command(name="quitar", description="Retira dinero a un usuario o todo su saldo con 'all'.")
@app_commands.describe(usuario="Usuario al que se le retirará el dinero", cantidad="Cantidad numérica o escribe 'all' para vaciarlo")
async def quitar(interaction: discord.Interaction, usuario: discord.Member, cantidad: str):
    if not es_dueno(interaction):
        return await interaction.response.send_message("❌ No tienes permisos para usar este comando de dueño.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    uid = str(usuario.id)
    await asegurar_usuario(uid)

    datos = await usuarios_col.find_one({"_id": uid})
    dinero_actual = datos.get("dinero", 0)

    if cantidad.lower() == "all":
        monto_a_quitar = dinero_actual
        await usuarios_col.update_one({"_id": uid}, {"$set": {"dinero": 0}})
        return await interaction.followup.send(f"✅ Se ha retirado todo el saldo (**{monto_a_quitar}** monedas) a {usuario.mention}.", ephemeral=True)

    try:
        monto = int(cantidad)
    except ValueError:
        return await interaction.followup.send("❌ Cantidad inválida. Ingresa un número o la palabra `all`.", ephemeral=True)

    if monto <= 0:
        return await interaction.followup.send("❌ La cantidad a retirar debe ser mayor a 0.", ephemeral=True)

    monto_final = min(monto, dinero_actual)
    await usuarios_col.update_one({"_id": uid}, {"$inc": {"dinero": -monto_final}})

    await interaction.followup.send(f"✅ Se han retirado **{monto_final}** monedas a {usuario.mention}.", ephemeral=True)


# --- 4. COMANDO /reset-eco (Solo Dueños) ---
@bot.tree.command(name="reset-eco", description="Resetea por completo la economía del servidor.")
async def reset_eco(interaction: discord.Interaction):
    if not es_dueno(interaction):
        return await interaction.response.send_message("❌ No tienes permisos para usar este comando de dueño.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    # Reiniciar el dinero de todos los usuarios registrados en la colección
    await usuarios_col.update_many({}, {"$set": {"dinero": 1000, "banco": 0, "xp_chamba": 0, "nivel_chamba": 1, "trabajo": 0}})

    await interaction.followup.send("⚠️ **¡Economía reseteada con éxito!** Todos los saldos y niveles de chamba han vuelto a sus valores iniciales.", ephemeral=True)

# --- ARRANQUE DEL BOT Y SERVIDOR FLASK ---
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise ValueError("❌ No se encontró la variable de entorno DISCORD_TOKEN.")
    
    bot.run(TOKEN)
    
        
