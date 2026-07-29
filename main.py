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
            "dinero": 1000,
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
        if str(interaction.user.id) == "1491476806203740373":
            return
            
        tiempo_restante = round(error.retry_after, 1)
        await interaction.response.send_message(
            f"⏳ Estás en tiempo de espera. Por favor, espera **{tiempo_restante} segundos** antes de volver a usar este comando.",
            ephemeral=True
        )
    else:
        raise error

# /balance [usuario]
@bot.tree.command(name="balance", description="Revisa tu saldo actual de dinero e inventario.")
@app_commands.describe(usuario="Usuario opcional a consultar")
async def balance(interaction: discord.Interaction, usuario: discord.Member = None):
    await interaction.response.defer(ephemeral=True)
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
    await interaction.response.defer(ephemeral=True)
    target = usuario or interaction.user
    uid = str(target.id)
    
    await asegurar_usuario(uid)
    datos = await usuarios_col.find_one({"_id": uid})
    
    await interaction.followup.send(f"💵 El dinero en mano de **{target.name}** es: `{datos.get('dinero', 0)}`", ephemeral=True)

# /verbanco [usuario]
@bot.tree.command(name="verbanco", description="Consulta el dinero guardado en el banco.")
@app_commands.describe(usuario="Usuario opcional a consultar")
async def verbanco(interaction: discord.Interaction, usuario: discord.Member = None):
    await interaction.response.defer(ephemeral=True)
    target = usuario or interaction.user
    uid = str(target.id)
    
    await asegurar_usuario(uid)
    datos = await usuarios_col.find_one({"_id": uid})
    
    await interaction.followup.send(f"🏦 El dinero en el banco de **{target.name}** es: `{datos.get('banco', 0)}`", ephemeral=True)


# /addbanco [cantidad]
@bot.tree.command(name="addbanco", description="Deposita dinero en el banco.")
@app_commands.describe(cantidad="Cantidad a depositar (número o 'all' para todo)")
async def addbanco(interaction: discord.Interaction, cantidad: str):
    await interaction.response.defer(ephemeral=True)
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
            await interaction.followup.send("❌ Por favor, introduce un número válido o 'all'.", ephemeral=True)
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
    
    await interaction.followup.send(f"✅ Has depositado **{monto}** en el banco correctamente.", ephemeral=True)

# /sacarbanco [cantidad]
@bot.tree.command(name="sacarbanco", description="Retira dinero del banco a tu mano.")
@app_commands.describe(cantidad="Cantidad a retirar (número o 'all' para todo)")
async def sacarbanco(interaction: discord.Interaction, cantidad: str):
    await interaction.response.defer(ephemeral=True)
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
        await interaction.followup.send("❌ No tienes esa cantidad guardada en el banco.", ephemeral=True)
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
    await interaction.response.defer(ephemeral=True)
    
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
    
    await interaction.followup.send(f"💸 Has transferido exitosamente **{monto}** a **{usuario.name}**.", ephemeral=True)


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
        super().__init__(timeout=60)
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
@app_commands.cooldown(1, 300, key=app_commands.CooldownType.user)
async def minar(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
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
        ephemeral=True
    )


# /inventario
@bot.tree.command(name="inventario", description="Muestra tus minerales recolectados y picos actuales.")
async def inventario(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)
    
    datos = await usuarios_col.find_one({"_id": uid})
    minerales_usuario = datos.get("minerales", {})
    picos_usuario = datos.get("picos", ["Pico de Madera (Por defecto)"])
    pico_actual = datos.get("pico_activo", {"nombre": "Pico de Madera", "bonus": 0})
    
    texto_minerales = ""
    if minerales_usuario:
        for min_nombre, cantidad in minerales_usuario.items():
            if cantidad > 0:
                texto_minerales += f"• **{min_nombre}**: `{cantidad}`\n"
    else:
        texto_minerales = "No tienes minerales guardados."
        
    await interaction.followup.send(
        f"🎒 **Inventario de {interaction.user.name}**\n\n"
        f"🛠️ **Pico Equipado:** {pico_actual.get('nombre')} (+{pico_actual.get('bonus')}% probabilidad)\n"
        f"📋 **Picos Disponibles:** {', '.join(picos_usuario)}\n\n"
        f"💎 **Minerales:**\n{texto_minerales}",
        ephemeral=True
    )


class VistaCrafteo(discord.ui.View):
    def __init__(self, uid):
        super().__init__(timeout=60)
        self.uid = uid

    @discord.ui.button(label="Ver Recetas de Picos", style=discord.ButtonStyle.primary, emoji="🛠️")
    async def craftear_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("❌ No puedes usar este menú.", ephemeral=True)
            
        await asegurar_usuario(self.uid)
        config = await usuarios_col.find_one({"_id": "configuracion_global"})
        recetas = config.get("recetas_crafteo", {}) if config else {}
        
        if not recetas:
            return await interaction.response.send_message("❌ No hay picos configurados por los administradores todavía.", ephemeral=True)
            
        msg = "🛠️ **Menú de Crafteo de Picos Disponibles:**\n"
        for pico_nombre, info in recetas.items():
            costos_str = ", f'{cant}x {min_name}' for min_name, cant in info['costos'].items()"
            msg += f"• **{pico_nombre}** (+{info['bonus']}% bonus) -> Costos configurados\n"
            
        await interaction.response.edit_message(content=msg, view=None)


# /crafteo
@bot.tree.command(name="crafteo", description="Abre el menú de crafteo para crear picos mejores.")
async def crafteo(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    uid = str(interaction.user.id)
    
    view = VistaCrafteo(uid)
    await interaction.followup.send(
        "🛠️ Bienvenido al sistema de crafteo. Haz clic abajo para ver los picos disponibles:",
        view=view,
        ephemeral=True
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
    await interaction.response.defer(ephemeral=True)
    
    descripcion = "💎 **Índice de Minerales Disponibles:**\n\n"
    for idx, mineral in enumerate(MINERALES_DATA, start=1):
        descripcion += f"{idx}. {mineral['emoji']} **{mineral['nombre']}** — Valor: `{mineral['valor']}` monedas\n"
    
    await interaction.followup.send(descripcion, ephemeral=True)

# --- JUEGO SUERTE DEL RATÓN (/suerte_raton [apuesta]) ---
class VistaSuerteRaton(discord.ui.View):
    def __init__(self, uid, apuesta, raton_pos):
        super().__init__(timeout=60)
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
@app_commands.cooldown(1, 360, key=app_commands.CooldownType.user)
@app_commands.describe(apuesta="Cantidad de dinero a apostar")
async def suerte_raton(interaction: discord.Interaction, apuesta: int):
    await interaction.response.defer(ephemeral=True)
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
        ephemeral=True
        )

    # --- JUEGO PAVO HAMBRIENTO (/pavo_hambriento [apuesta]) ---
class VistaPavoHambriento(discord.ui.View):
    def __init__(self, uid, apuesta, limite_explosion):
        super().__init__(timeout=60)
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
@app_commands.cooldown(1, 360, key=app_commands.CooldownType.user)
@app_commands.describe(apuesta="Cantidad de dinero a apostar")
async def pavo_hambriento(interaction: discord.Interaction, apuesta: int):
    await interaction.response.defer(ephemeral=True)
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)
    
    datos = await usuarios_col.find_one({"_id": uid})
    if datos.get("dinero", 0) < apuesta or apuesta <= 0:
        return await interaction.followup.send("❌ No tienes suficiente dinero o la apuesta no es válida.", ephemeral=True)

    # El límite de cuántas veces soporta el pavo antes de estallar (por ejemplo, entre 3 y 8 veces)
    limite_explosion = random.randint(3, 8)
    
    view = VistaPavoHambriento(uid, apuesta, limite_explosion)
    
    await interaction.followup.send(
        f"🦃 **¡Comienza el juego del Pavo Hambriento!**\n"
        f"Apuesta: `{apuesta}` | Cada porción de comida sube la apuesta un **x0.3**.\n"
        f"Usa los botones de abajo con cuidado:",
        view=view,
        ephemeral=True
    )
    
