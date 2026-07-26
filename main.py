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

DB_FILE = "eco.json"
datos = {}

if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f: datos = json.load(f)

def guardar_datos():
    with open(DB_FILE, "w") as f: json.dump(datos, f)

# --- ESTRUCTURA BASE DE USUARIO ---
def asegurar_usuario(uid):
    if uid not in datos:
        nombres_azar = ["Rayo", "Veloz", "Centella", "Fogonazo", "Turbo"]
        emojis_azar = ["🐶", "🐱", "🐰", "🦊", "🐼"]
        datos[uid] = {
            "dinero": 1000,
            "banco": 0,
            "mascota_nivel": 1,
            "mascota_nombre": random.choice(nombres_azar),
            "mascota_emoji": random.choice(emojis_azar),
            "carreras_gratis": 5,
            "tiene_mascota_propia": False,
            "minerales_descubiertos": []  # <-- AQUÍ DEBE IR CORRECTAMENTE
        }
    else:
        if "mascota_nombre" not in datos[uid]:
            datos[uid]["mascota_nombre"] = "Rayo"
            datos[uid]["mascota_emoji"] = "🐶"
            datos[uid]["carreras_gratis"] = 5
            datos[uid]["tiene_mascota_propia"] = False
        
        # Y aseguramos que los usuarios antiguos también tengan la lista si no la tienen
        if "minerales_descubiertos" not in datos[uid]:
            datos[uid]["minerales_descubiertos"] = []
            

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("Bot listo con todos los comandos.")







# --- VISTA SECUNDARIA PARA SALIR DEL SORTEO ---
class ConfirmarSalidaView(View):
    def __init__(self, sorteo_view, user_id):
        super().__init__(timeout=30)
        self.sorteo_view = sorteo_view
        self.user_id = user_id

    @discord.ui.button(label="Salir del sorteo ❌", style=discord.ButtonStyle.red)
    async def salir(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.sorteo_view.participantes:
            self.sorteo_view.participantes.remove(interaction.user.id)
            
            total_participantes = len(self.sorteo_view.participantes)
            contenido = (
                f"🎁 **¡NUEVO SORTEO DE ECONOMÍA!** 🎁\n\n"
                f"💰 Premio en juego: **{self.sorteo_view.premio}**\n"
                f"👥 Participantes actuales: **{total_participantes}**\n"
                f"⏱️ Termina: <t:{self.sorteo_view.timestamp_fin}:R>\n"
                f"👇 Haz clic en el botón **Participar** para unirte."
            )
            try:
                await self.sorteo_view.message.edit(content=contenido, view=self.sorteo_view)
            except:
                pass

            await interaction.response.edit_message(content="✅ Te has salido del sorteo correctamente.", view=None)
        else:
            await interaction.response.edit_message(content="❌ Ya no estabas participando en este sorteo.", view=None)

    @discord.ui.button(label="Seguir participando ✨", style=discord.ButtonStyle.grey)
    async def quedar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="✨ Has decidido seguir participando en el sorteo. ¡Mucha suerte!", view=None)

# --- VISTA PRINCIPAL PARA EL SORTEO ---
class SorteoView(View):
    def __init__(self, premio: int, duracion_segundos: int, timestamp_fin: int):
        super().__init__(timeout=duracion_segundos)
        self.premio = premio
        self.participantes = set()
        self.duracion_segundos = duracion_segundos
        self.timestamp_fin = timestamp_fin
        self.message = None

    async def actualizar_mensaje(self, interaction: discord.Interaction):
        total_participantes = len(self.participantes)
        contenido = (
            f"🎁 **¡NUEVO SORTEO DE ECONOMÍA!** 🎁\n\n"
            f"💰 Premio en juego: **{self.premio}**\n"
            f"👥 Participantes actuales: **{total_participantes}**\n"
            f"⏱️ Termina: <t:{self.timestamp_fin}:R>\n"
            f"👇 Haz clic en el botón **Participar** para unirte."
        )
        await interaction.response.edit_message(content=contenido, view=self)

    @discord.ui.button(label="Participar 🎉", style=discord.ButtonStyle.green, custom_id="sorteo_participar_btn")
    async def participar(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        asegurar_usuario(uid)
        
        if interaction.user.id in self.participantes:
            vista_salida = ConfirmarSalidaView(self, interaction.user.id)
            await interaction.response.send_message(
                "⚠️ Ya estás participando en este sorteo. ¿Qué deseas hacer?",
                view=vista_salida,
                ephemeral=True
            )
        else:
            self.participantes.add(interaction.user.id)
            await self.actualizar_mensaje(interaction)
            await interaction.followup.send("✅ ¡Te has unido al sorteo correctamente!", ephemeral=True)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

        if not self.participantes:
            try:
                await self.message.edit(content="🎉 **¡SORTEO FINALIZADO!** 🎉\n\n❌ El tiempo ha terminado, pero no hubo participantes registrados.", view=self)
            except:
                pass
            return

        uid_ganador = random.choice(list(self.participantes))
        str_uid = str(uid_ganador)
        asegurar_usuario(str_uid)

        datos[str_uid]["dinero"] += self.premio
        guardar_datos()

        try:
            guild = self.message.guild
            usuario_ganador = await guild.fetch_member(uid_ganador)
            nombre_ganador = usuario_ganador.mention
        except:
            nombre_ganador = f"<@{uid_ganador}>"

        try:
            await self.message.edit(
                content=f"🎉 **¡SORTEO FINALIZADO!** 🎉\n\n"
                        f"💰 Premio entregado: **{self.premio}**\n"
                        f"👥 Total de participantes: **{len(self.participantes)}**\n"
                        f"👑 ¡El ganador afortunado es {nombre_ganador}!",
                view=self
            )
        except:
            pass
        self.stop()

# --- COMANDO SORTEO RESTRINGIDO A ADMINISTRADORES ---
@bot.tree.command(name="sorteo_economia", description="Crea un sorteo con tiempo límite (Solo administradores)")
@app_commands.describe(premio="Cantidad de monedas a sortear", tiempo="Duración (Ejemplo: 30s, 5m, 1h)")
async def sorteo_economia(interaction: discord.Interaction, premio: int, tiempo: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ No tienes permisos de administrador para usar este comando.", ephemeral=True)
        return

    if premio <= 0:
        await interaction.response.send_message("❌ El premio del sorteo debe ser mayor a 0.", ephemeral=True)
        return

    tiempo = tiempo.lower()
    multiplicador = 1
    if tiempo.endswith('s'):
        multiplicador = 1
    elif tiempo.endswith('m'):
        multiplicador = 60
    elif tiempo.endswith('h'):
        multiplicador = 3600
    else:
        await interaction.response.send_message("❌ Formato inválido. Usa 's', 'm' o 'h' (Ej: `30s`, `5m`, `1h`).", ephemeral=True)
        return

    try:
        cantidad_tiempo = int(tiempo[:-1])
        duracion_segundos = cantidad_tiempo * multiplicador
    except ValueError:
        await interaction.response.send_message("❌ Número de tiempo inválido. Asegúrate de poner un número seguido de s, m o h.", ephemeral=True)
        return

    if duracion_segundos <= 0:
        await interaction.response.send_message("❌ El tiempo del sorteo debe ser mayor a 0.", ephemeral=True)
        return

    timestamp_fin = int(time.time()) + duracion_segundos

    view = SorteoView(premio=premio, duracion_segundos=duracion_segundos, timestamp_fin=timestamp_fin)
    
    await interaction.response.send_message(
        f"🎁 **¡NUEVO SORTEO DE ECONOMÍA!** 🎁\n\n"
        f"💰 Premio en juego: **{premio}**\n"
        f"👥 Participantes actuales: **0**\n"
        f"⏱️ Termina: <t:{timestamp_fin}:R>\n"
        f"👇 Haz clic en el botón **Participar** para unirte.",
        view=view
    )
    view.message = await interaction.original_response()
        


# --- COMANDOS DE BANCO ---
@bot.tree.command(name="verbanco", description="Mira cuánto tienes guardado")
async def verbanco(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    asegurar_usuario(uid)
    saldo = datos[uid].get("banco", 0)
    await interaction.response.send_message(f"🏦 Tu saldo seguro es: **{saldo}**")

@bot.tree.command(name="addbanco", description="Deposita en el banco")
async def addbanco(interaction: discord.Interaction, cantidad: int):
    uid = str(interaction.user.id)
    asegurar_usuario(uid)
    if cantidad > datos[uid]["dinero"]:
        await interaction.response.send_message("❌ No tienes suficiente dinero en mano.")
    else:
        datos[uid]["dinero"] -= cantidad
        datos[uid]["banco"] += cantidad
        guardar_datos()
        await interaction.response.send_message(f"✅ Depositaste {cantidad}.")

@bot.tree.command(name="sacarbanco", description="Retira del banco")
async def sacarbanco(interaction: discord.Interaction, cantidad: int):
    uid = str(interaction.user.id)
    asegurar_usuario(uid)
    if cantidad > datos[uid]["banco"]:
        await interaction.response.send_message("❌ Fondos insuficientes en banco.")
    else:
        datos[uid]["banco"] -= cantidad
        datos[uid]["dinero"] += cantidad
        guardar_datos()
        await interaction.response.send_message(f"✅ Retiraste {cantidad}.")



# --- COMANDO: COMPRAR MASCOTA ---
@bot.tree.command(name="comprar_mascota", description="Compra y personaliza tu propia mascota con nombre y emoji")
async def comprar_mascota(interaction: discord.Interaction, nombre: str, emoji: str):
    uid = str(interaction.user.id)
    asegurar_usuario(uid)
    
    costo = 2500
    if datos[uid]["dinero"] < costo:
        await interaction.response.send_message(f"❌ Necesitas **{costo}** monedas en mano para comprar y registrar tu propia mascota.", ephemeral=True)
        return

    datos[uid]["dinero"] -= costo
    datos[uid]["mascota_nombre"] = nombre
    datos[uid]["mascota_emoji"] = emoji
    datos[uid]["tiene_mascota_propia"] = True
    datos[uid]["carreras_gratis"] = 99999
    guardar_datos()

    await interaction.response.send_message(
        f"🎉 **¡FELICIDADES!** 🎉\n\n"
        f"Has adoptado y registrado a tu nueva mascota:\n"
        f"🐾 {emoji} **{nombre}** (Costo: {costo} monedas).\n"
        f"¡Ahora tienes carreras ilimitadas y listas para la acción!"
    )

# ==========================================
# 1. COMANDO CARRERA
# ==========================================
from discord.ui import View

# --- VISTA PARA EL DUELO DE CARRERAS MULTIJUGADOR ---
class CarreraView(View):
    def __init__(self, retador: discord.Member, oponente: discord.Member, apuesta: int):
        super().__init__(timeout=60) # 60 segundos para aceptar
        self.retador = retador
        self.oponente = oponente
        self.apuesta = apuesta
        self.message = None

    @discord.ui.button(label="Aceptar Duelo 🏎️", style=discord.ButtonStyle.green)
    async def aceptar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Solo el oponente retado puede dar clic
        if interaction.user.id != self.oponente.id:
            await interaction.response.send_message("❌ Este reto no es para ti.", ephemeral=True)
            return

        uid_retador = str(self.retador.id)
        uid_oponente = str(self.oponente.id)
        
        asegurar_usuario(uid_retador)
        asegurar_usuario(uid_oponente)

        # Validar fondos actualizados
        if datos[uid_retador]["dinero"] < self.apuesta:
            await interaction.response.send_message(f"❌ {self.retador.mention} ya no tiene suficiente dinero para la apuesta.", ephemeral=True)
            return

        if datos[uid_oponente]["dinero"] < self.apuesta:
            await interaction.response.send_message("❌ No tienes suficiente dinero en mano para aceptar la apuesta.", ephemeral=True)
            return

        # Deshabilitar botón para evitar múltiples clics
        button.disabled = True
        await interaction.response.edit_message(
            content=f"🏁 **¡Duelo aceptado!** {self.retador.mention} VS {self.oponente.mention}.\n\n🏎️ ¡Las mascotas están acelerando en la pista!...", 
            view=self
        )

        # Cobrar apuesta a ambos jugadores
        datos[uid_retador]["dinero"] -= self.apuesta
        datos[uid_oponente]["dinero"] -= self.apuesta
        guardar_datos()

        await asyncio.sleep(3)

        # Elegir ganador al azar
        ganador, perdedor, uid_ganador = random.choice([
            (self.retador, self.oponente, uid_retador),
            (self.oponente, self.retador, uid_oponente)
        ])

        pozo_total = self.apuesta * 2
        datos[uid_ganador]["dinero"] += pozo_total
        guardar_datos()

        mascota_ganador = f"{datos[uid_ganador]['mascota_emoji']} {datos[uid_ganador]['mascota_nombre']}"

        await interaction.message.edit(
            content=(
                f"🏆 **¡FIN DE LA CARRERA!** 🏆\n\n"
                f"🥇 ¡El ganador es {ganador.mention} con su mascota **{mascota_ganador}**!\n"
                f"💰 Se lleva el premio total de **{pozo_total:,}** monedas.\n"
                f"💀 {perdedor.mention} ha perdido **{self.apuesta:,}** monedas."
            ),
            view=None
        )

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(content="⏱️ El tiempo para aceptar la carrera ha expirado.", view=self)
        except:
            pass

# --- COMANDO CARRERA ACTUALIZADO ---
@bot.tree.command(name="carrera", description="Reta a un usuario o compite contra la máquina")
@app_commands.describe(apuesta="Cantidad a apostar", usuario="Opcional: Reta a otro jugador")
@app_commands.checks.cooldown(1, 180.0, key=lambda i: i.user.id)
async def carrera(interaction: discord.Interaction, apuesta: int, usuario: discord.Member = None):
    await interaction.response.defer()

    uid = str(interaction.user.id)
    asegurar_usuario(uid)

    if apuesta <= 0:
        await interaction.followup.send("❌ La apuesta debe ser mayor a 0.", ephemeral=True)
        return

    if datos[uid]["dinero"] < apuesta:
        await interaction.followup.send("❌ No tienes suficiente dinero en mano para esta apuesta.", ephemeral=True)
        return

    if not datos[uid]["tiene_mascota_propia"]:
        if datos[uid]["carreras_gratis"] <= 0:
            await interaction.followup.send(
                "❌ Se te han agotado tus **5 carreras gratuitas** con la mascota temporal.\n"
                "Usa `/comprar_mascota [nombre] [emoji]` para conseguir una propia y desbloquear carreras ilimitadas.", 
                ephemeral=True
            )
            return
        datos[uid]["carreras_gratis"] -= 1

    mascota_str = f"{datos[uid]['mascota_emoji']} {datos[uid]['mascota_nombre']}"

    # Modo contra la IA (sin mencionar usuario)
    if usuario is None:
        datos[uid]["dinero"] -= apuesta
        guardar_datos()

        await interaction.followup.send(f"🏁 Tu mascota **{mascota_str}** ha entrado a la pista contra la IA. ¡Acelerando...")
        await asyncio.sleep(2)

        if random.random() < 0.50:
            premio = apuesta * 2
            datos[uid]["dinero"] += premio
            guardar_datos()
            await interaction.followup.send(f"🏆 ¡Victoria! **{mascota_str}** ganó la carrera. Te llevas **{premio:,}** monedas.")
        else:
            guardar_datos()
            await interaction.followup.send(f"❌ ¡Derrota! **{mascota_str}** se tropezó en la pista y perdiste **{apuesta:,}** monedas.")
        return

    # Validaciones para multijugador
    if interaction.user.id == usuario.id:
        await interaction.followup.send("❌ No puedes retarte a ti mismo.", ephemeral=True)
        return

    if usuario.bot:
        await interaction.followup.send("❌ No puedes retar a un bot de Discord.", ephemeral=True)
        return

    # Modo Duelo contra otro usuario
    view = CarreraView(retador=interaction.user, oponente=usuario, apuesta=apuesta)
    msg = await interaction.followup.send(
        f"🏎️ **¡DUELO DE CARRERA PROPUESTO!** 🏎️\n\n"
        f"👤 {interaction.user.mention} (con su mascota {mascota_str}) ha retado a {usuario.mention} por **{apuesta:,}** monedas.\n"
        f"👇 ¡{usuario.mention}, haz clic en el botón de abajo para aceptar!",
        view=view
    )
    view.message = msg

@carrera.error
async def carrera_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        if interaction.response.is_done():
            await interaction.followup.send(f"⏳ Estás en cooldown. Espera {round(error.retry_after)} segundos.", ephemeral=True)
        else:
            await interaction.response.send_message(f"⏳ Estás en cooldown. Espera {round(error.retry_after)} segundos.", ephemeral=True)
            
# ==========================================
# 2. COMANDO SUERTE (SIN LÍMITES)
# ==========================================
@bot.tree.command(name="suerte", description="Prueba tu suerte apostando a cara o cruz sin límites")
@app_commands.choices(caraocruz=[
    app_commands.Choice(name="Cara", value="cara"),
    app_commands.Choice(name="Cruz", value="cruz")
])
@app_commands.checks.cooldown(1, 180.0, key=lambda i: i.user.id)
async def suerte(interaction: discord.Interaction, cantidad: int, caraocruz: str):
    if cantidad <= 0:
        await interaction.response.send_message("❌ La cantidad a apostar debe ser mayor a 0.", ephemeral=True)
        return

    uid = str(interaction.user.id)
    asegurar_usuario(uid)
    
    if datos[uid]["dinero"] < cantidad:
        await interaction.response.send_message("❌ No tienes suficiente dinero en mano.", ephemeral=True)
        return

    resultado = random.choice(["cara", "cruz"])
    if caraocruz.lower() == resultado:
        ganancia = cantidad * 2
        datos[uid]["dinero"] += cantidad
        msg = f"🪙 ¡Salió **{resultado}**! Ganaste **{ganancia}** monedas."
    else:
        datos[uid]["dinero"] -= cantidad
        msg = f"🪙 ¡Salió **{resultado}**! Perdiste **{cantidad}** monedas."

    guardar_datos()
    await interaction.response.send_message(msg)

@suerte.error
async def suerte_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"⏳ Espera {round(error.retry_after)} segundos para volver a apostar.", ephemeral=True)


# ==========================================
# 3. COMANDOS DE MINERÍA E ÍNDICE DE MINERALES
# ==========================================
MINERALES_DATA = [
    # Comunes
    {"nombre": "Piedra", "emoji": "🪨", "valor": 3000, "prob": 10.0},
    {"nombre": "Carbón", "emoji": "⬛", "valor": 3500, "prob": 6.0},
    {"nombre": "Arcilla", "emoji": "🧱", "valor": 4000, "prob": 4.0},
    {"nombre": "Grava", "emoji": "🪨", "valor": 4500, "prob": 3.0},
    {"nombre": "Sal gema", "emoji": "🧂", "valor": 5000, "prob": 2.0},
    
    # Poco comunes
    {"nombre": "Cobre", "emoji": "🟠", "valor": 6500, "prob": 1.5},
    {"nombre": "Hierro", "emoji": "⛓️", "valor": 8000, "prob": 1.0},
    {"nombre": "Estaño", "emoji": "🥫", "valor": 9500, "prob": 0.8},
    {"nombre": "Zinc", "emoji": "🔋", "valor": 11000, "prob": 0.6},
    {"nombre": "Plomo", "emoji": "🛢️", "valor": 13000, "prob": 0.5},

    # Raros
    {"nombre": "Aluminio", "emoji": "✈️", "valor": 16000, "prob": 0.4},
    {"nombre": "Níquel", "emoji": "🪙", "valor": 20000, "prob": 0.3},
    {"nombre": "Azufre", "emoji": "🟡", "valor": 25000, "prob": 0.25},
    {"nombre": "Cuarzo", "emoji": "🧊", "valor": 30000, "prob": 0.2},
    {"nombre": "Salitre", "emoji": "🧪", "valor": 36000, "prob": 0.18},

    # Muy raros
    {"nombre": "Plata", "emoji": "🥈", "valor": 45000, "prob": 0.15},
    {"nombre": "Oro", "emoji": "🥇", "valor": 55000, "prob": 0.12},
    {"nombre": "Platino", "emoji": "💠", "valor": 70000, "prob": 0.10},
    {"nombre": "Titanio", "emoji": "🛡️", "valor": 90000, "prob": 0.08},
    {"nombre": "Cobalto", "emoji": "🔹", "valor": 115000, "prob": 0.06},

    # Épicos
    {"nombre": "Litio", "emoji": "⚡", "valor": 150000, "prob": 0.05},
    {"nombre": "Uranio", "emoji": "☢️", "valor": 200000, "prob": 0.04},
    {"nombre": "Jade", "emoji": "🟢", "valor": 270000, "prob": 0.03},
    {"nombre": "Rubí", "emoji": "🔴", "valor": 350000, "prob": 0.025},
    {"nombre": "Zafiro", "emoji": "🔵", "valor": 450000, "prob": 0.02},

    # Legendarios (~3% o menos para los más altos)
    {"nombre": "Esmeralda", "emoji": "💚", "valor": 600000, "prob": 0.015},
    {"nombre": "Diamante", "emoji": "💎", "valor": 800000, "prob": 0.01},
    {"nombre": "Aleandrita", "emoji": "🔮", "valor": 1100000, "prob": 0.007},
    {"nombre": "Bovedita", "emoji": "🕳️", "valor": 1500000, "prob": 0.004},
    {"nombre": "Estrella del Vacío", "emoji": "🌟", "valor": 2500000, "prob": 0.003},
]

@bot.tree.command(name="minar", description="Explora las profundidades en busca de minerales valiosos")
@app_commands.checks.cooldown(1, 600.0, key=lambda i: i.user.id) # 10 minutos de cooldown
async def minar(interaction: discord.Interaction):
    await interaction.response.defer()
    
    uid = str(interaction.user.id)
    asegurar_usuario(uid)
    
    if "minerales_descubiertos" not in datos[uid]:
        datos[uid]["minerales_descubiertos"] = []

    # 70% de probabilidad de fallo, 30% de acierto
    if random.random() > 0.30:
        guardar_datos()
        await interaction.followup.send("⛏️ Te pusiste a cavar con fuerza, pero la roca cedió y **no encontraste nada útil** esta vez. ¡Sigue intentándolo!")
        return

    pesos = [m["prob"] for m in MINERALES_DATA]
    mineral_encontrado = random.choices(MINERALES_DATA, weights=pesos, k=1)[0]

    datos[uid]["dinero"] += mineral_encontrado["valor"]

    nombre_mineral = mineral_encontrado["nombre"]
    completado_ahora = False
    if nombre_mineral not in datos[uid]["minerales_descubiertos"]:
        datos[uid]["minerales_descubiertos"].append(nombre_mineral)
        if len(datos[uid]["minerales_descubiertos"]) == len(MINERALES_DATA):
            datos[uid]["dinero"] += 800000 # Bono por completar el índice
            completado_ahora = True

    guardar_datos()

    mensaje = (
        f"⛏️ **¡Has minado con éxito!**\n"
        f"Encontraste: {mineral_encontrado['emoji']} **{mineral_encontrado['nombre']}**\n"
        f"💰 Valor de venta: **{mineral_encontrado['valor']:,}** monedas añadidas a tu bolsillo."
    )

    if completado_ahora:
        mensaje += "\n\n🎉 **¡INCREÍBLE!** ¡Has descubierto los 30 minerales y completado tu `/indice_minerales`! Has ganado un bono extra de **800,000** monedas."

    await interaction.followup.send(mensaje)

@minar.error
async def minar_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        minutos = math.ceil(error.retry_after / 60) if 'math' in globals() else round(error.retry_after / 60, 1)
        if interaction.response.is_done():
            await interaction.followup.send(f"⏳ Estás cansado. Debes descansar y esperar unos **{minutos} minutos** antes de volver a minar.", ephemeral=True)
        else:
            await interaction.response.send_message(f"⏳ Estás cansado. Debes descansar y esperar unos **{minutos} minutos** antes de volver a minar.", ephemeral=True)

@bot.tree.command(name="indice_minerales", description="Muestra tu progreso completando la colección de los 30 minerales")
async def indice_minerales(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    asegurar_usuario(uid)

    if "minerales_descubiertos" not in datos[uid]:
        datos[uid]["minerales_descubiertos"] = []

    descubiertos = datos[uid]["minerales_descubiertos"]
    total = len(MINERALES_DATA)
    propios_encontrados = len(descubiertos)

    lista_visual = []
    for m in MINERALES_DATA:
        if m["nombre"] in descubiertos:
            lista_visual.append(f"{m['emoji']} **{m['nombre']}**")
        else:
            lista_visual.append(f"❓ `??????`")

    bloque_1 = " | ".join(lista_visual[:15])
    bloque_2 = " | ".join(lista_visual[15:])

    embed = discord.Embed(
        title="📜 Índice Geológico de Minerales",
        description=f"Progreso de colección: **{propios_encontrados}/{total}**\n*¡Completa los 30 para ganar 800,000 monedas!*\n",
        color=discord.Color.gold()
    )
    embed.add_field(name="Minerales (1 al 15)", value=bloque_1, inline=False)
    embed.add_field(name="Minerales (16 al 30)", value=bloque_2, inline=False)

    if propios_encontrados == total:
        embed.set_footer(text="✨ ¡Índice completado al 100%! Has reclamado tu recompensa.")
    else:
        embed.set_footer(text=f"Te faltan {total - propios_encontrados} minerales por descubrir minando.")

    await interaction.response.send_message(embed=embed, ephemeral=True)
        

# --- COMANDO MEJORAR MASCOTA ---
@bot.tree.command(name="mejorar_mascota", description="Sube de nivel a tu mascota")
async def mejorar_mascota(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    asegurar_usuario(uid)

    nivel_actual = datos[uid]["mascota_nivel"]
    costo_mejora = nivel_actual * 1000

    if datos[uid]["dinero"] < costo_mejora:
        await interaction.response.send_message(f"❌ Necesitas **{costo_mejora}** monedas para subir al Nivel {nivel_actual + 1}.", ephemeral=True)
        return

    datos[uid]["dinero"] -= costo_mejora
    datos[uid]["mascota_nivel"] += 1
    guardar_datos()

    m_nombre = datos[uid]["mascota_nombre"]
    m_emoji = datos[uid]["mascota_emoji"]

    await interaction.response.send_message(
        f"🐾 **¡MEJORA EXITOSA!** 🎉\n\n"
        f"✨ Tu mascota **{m_emoji} {m_nombre}** ha subido al **Nivel {datos[uid]['mascota_nivel']}**.\n"
        f"💸 Costo: **{costo_mejora}** monedas."
    )

# --- COMANDOS DE TRABAJO ---
@bot.tree.command(name="trabajar", description="Gana dinero trabajando honestamente con ayuda de tu mascota")
@app_commands.checks.cooldown(1, 180.0, key=lambda i: i.user.id)
async def trabajar(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    asegurar_usuario(uid)
    
    nivel_mascota = datos[uid].get("mascota_nivel", 1)
    ganancia_base = random.randint(100, 500)
    ganancia = int(ganancia_base * (1 + (nivel_mascota - 1) * 0.1))

    datos[uid]["dinero"] += ganancia
    guardar_datos()

    m_nombre = datos[uid]["mascota_nombre"]
    m_emoji = datos[uid]["mascota_emoji"]

    await interaction.response.send_message(
        f"✅ ¡Fuiste a trabajar junto a tu mascota **{m_emoji} {m_nombre}** (Nvl {nivel_mascota})!\n"
        f"💵 Ganaste **{ganancia}** monedas."
    )

@trabajar.error
async def trabajar_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        segundos = round(error.retry_after)
        await interaction.response.send_message(f"⏳ Estás cansado. Debes esperar {segundos} segundos para volver a trabajar.", ephemeral=True)

async def procesar_arresto(interaction: discord.Interaction):
    duracion = random.randint(1, 3)
    ROL_PRISIONERO_ID = 1530378140923461764
    rol_prisionero = interaction.guild.get_role(ROL_PRISIONERO_ID)
    
    if rol_prisionero:
        await interaction.user.add_roles(rol_prisionero)
    
    await interaction.followup.send(f"🚨 ¡Te atraparon! Serás arrestado por **{duracion} minutos**.")
    
    await asyncio.sleep(duracion * 60)
    
    if rol_prisionero:
        await interaction.user.remove_roles(rol_prisionero)
    try:
        await interaction.user.send("🔓 Tu condena terminó. Ya puedes acceder a la economía del servidor.")
    except:
        pass

@bot.tree.command(name="crimen", description="Comete un crimen riesgoso (Cooldown: 8 minutos)")
@app_commands.checks.cooldown(1, 480.0, key=lambda i: i.user.id)
async def crimen(interaction: discord.Interaction):
    await interaction.response.defer()
    uid = str(interaction.user.id)
    asegurar_usuario(uid)
    
    if random.random() < 0.50:
        ganancia = random.randint(500, 1500)
        datos[uid]["dinero"] += ganancia
        guardar_datos()
        await interaction.followup.send(f"😈 ¡Éxito! Lograste cometer el crimen y ganaste **{ganancia}** monedas.")
    else:
        await procesar_arresto(interaction)

@crimen.error
async def crimen_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        segundos = round(error.retry_after)
        await interaction.response.send_message(f"⏳ Estás bajo perfil policial. Espera {segundos} segundos para otro crimen.", ephemeral=True)
        
@bot.tree.command(name="robar", description="Intenta robar a otro usuario (Cooldown: 6 minutos)")
@app_commands.checks.cooldown(1, 360.0, key=lambda i: i.user.id)
async def robar(interaction: discord.Interaction, usuario: discord.Member):
    await interaction.response.defer()
    if random.random() < 0.40:
        await interaction.followup.send(f"💰 ¡Éxito! Lograste robarle una parte a {usuario.name}.")
    else:
        await procesar_arresto(interaction)

@robar.error
async def robar_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        segundos = round(error.retry_after)
        await interaction.response.send_message(f"⏳ Debes esconderte un rato. Espera {segundos} segundos para volver a robar.", ephemeral=True)

@bot.tree.command(name="robarbanco", description="Atraca el banco (Cooldown: 10 minutos)")
@app_commands.checks.cooldown(1, 600.0, key=lambda i: i.user.id)
async def robarbanco(interaction: discord.Interaction, usuario: discord.Member):
    await interaction.response.defer()
    if random.random() < 0.20:
        await interaction.followup.send(f"🏦 ¡BOOM! Atracaste con éxito el banco de {usuario.name}.")
    else:
        await procesar_arresto(interaction)

@robarbanco.error
async def robarbanco_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        segundos = round(error.retry_after)
        minutos = round(segundos / 60, 1)
        await interaction.response.send_message(f"⏳ Planificar otro golpe al banco requiere tiempo. Espera {segundos} segundos (aprox. {minutos} min).", ephemeral=True)

# --- COMANDOS BÁSICOS Y ADMINISTRACIÓN ---
@bot.tree.command(name="dinero", description="Mira cuánto dinero tienes en mano")
async def dinero(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    asegurar_usuario(uid)
    saldo = datos[uid]["dinero"]
    await interaction.response.send_message(f"💵 Tienes **{saldo}** en mano.")

@bot.tree.command(name="balance", description="Mira tu fortuna total (Mano + Banco)")
async def balance(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    asegurar_usuario(uid)
    total = datos[uid]["dinero"] + datos[uid]["banco"]
    mascota_nvl = datos[uid].get("mascota_nivel", 1)
    await interaction.response.send_message(f"💰 Tu fortuna total es de **{total}** (Mascota Nivel: {mascota_nvl}).")

@bot.tree.command(name="top", description="Mira quién es el más rico del servidor")
async def top(interaction: discord.Interaction):
    ranking = sorted(datos.items(), key=lambda x: x[1]["dinero"] + x[1]["banco"], reverse=True)[:5]
    texto = "🏆 **Top 5 más ricos del servidor:**\n\n"
    for i, (uid, info) in enumerate(ranking, 1):
        total = info["dinero"] + info["banco"]
        try:
            usuario = await bot.fetch_user(int(uid))
            texto += f"{i}. {usuario.name}: **{total}**\n"
        except:
            texto += f"{i}. Usuario desconocido: **{total}**\n"
    await interaction.response.send_message(texto)

@bot.tree.command(name="transferir", description="Transfiere dinero a otro usuario (cantidad o 'all')")
@app_commands.describe(cantidad="Escribe un número o la palabra 'all' para transferir todo")
@app_commands.checks.cooldown(1, 120.0, key=lambda i: i.user.id)
async def transferir(interaction: discord.Interaction, usuario: discord.Member, cantidad: str):
    uid_emisor = str(interaction.user.id)
    uid_receptor = str(usuario.id)
    asegurar_usuario(uid_emisor)
    
    if uid_emisor == uid_receptor:
        await interaction.response.send_message("❌ No puedes transferirte dinero a ti mismo.", ephemeral=True)
        return

    if cantidad.lower() == "all":
        monto = datos[uid_emisor]["dinero"]
        if monto <= 0:
            await interaction.response.send_message("❌ No tienes dinero en mano para transferir.", ephemeral=True)
            return
    else:
        try:
            monto = int(cantidad)
            if monto <= 0:
                await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
                return
            if datos[uid_emisor]["dinero"] < monto:
                await interaction.response.send_message("❌ No tienes suficiente dinero en mano.", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Por favor ingresa un número válido o la palabra 'all'.", ephemeral=True)
            return
        
    datos[uid_emisor]["dinero"] -= monto
    asegurar_usuario(uid_receptor)
    datos[uid_receptor]["dinero"] += monto
    
    guardar_datos()
    await interaction.response.send_message(f"💸 Has transferido **{monto}** a {usuario.name}.")

@transferir.error
async def transferir_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"⏳ Estás en cooldown de transferencias. Espera {round(error.retry_after)} segundos.", ephemeral=True)

@bot.tree.command(name="ayuda", description="Muestra la lista completa de comandos disponibles en el bot")
async def ayuda(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Menú de Ayuda - Z6 Economy",
        description="Aquí tienes la lista completa de todos los comandos organizados por categoría:",
        color=discord.Color.blue()
    )

    # Economía y Bancos
    embed.add_field(
        name="💰 Economía y Bancos",
        value=(
            "`/dinero` - Consulta tu dinero en mano.\n"
            "`/verbanco` - Consulta tu saldo en el banco.\n"
            "`/addbanco [cantidad]` - Deposita dinero en el banco.\n"
            "`/sacarbanco [cantidad]` - Retira dinero del banco.\n"
            "`/balance` - Mira tu fortuna total y nivel de mascota.\n"
            "`/top` - Ranking de los más ricos del servidor.\n"
            "`/transferir [usuario] [cantidad/all]` - Envía dinero (soporta 'all' | Cooldown: 2m)."
        ),
        inline=False
    )

    # Trabajos
    embed.add_field(
        name="💼 Trabajos",
        value=(
            "`/trabajar` - Gana dinero trabajando honestamente (Bonus por mascota | Cooldown: 3m)."
        ),
        inline=False
    )

    # Acción, Riesgo y Apuestas
    embed.add_field(
        name="⚖️ Acción, Riesgo y Apuestas",
        value=(
            "`/crimen` - Intenta un crimen riesgoso (Cooldown: 8m).\n"
            "`/robar [usuario]` - Intenta robarle a otro usuario (Cooldown: 6m).\n"
            "`/robarbanco [usuario]` - Atraca el banco de otro usuario (Cooldown: 10m).\n"
            "`/suerte [monto] [cara/cruz]` - Apuesta tu dinero sin límites (Cooldown: 3m).\n"
            "`/carrera [apuesta] [usuario_opcional]` - Compite contra la IA (primeras 5 gratis) o reta a un jugador."
        ),
        inline=False
    )

    # Minería y Colección
    embed.add_field(
        name="⛏️ Minería y Colección",
        value=(
            "`/minar` - Explora las profundidades en busca de valiosos minerales (Cooldown: 10m).\n"
            "`/indice_minerales` - Revisa tu progreso descubriendo los 30 minerales raros."
        ),
        inline=False
    )

    # Sistema de Mascotas
    embed.add_field(
        name="🐾 Sistema de Mascotas",
        value=(
            "`/comprar_mascota [nombre] [emoji]` - Crea y personaliza tu mascota propia (Desbloquea carreras ilimitadas).\n"
            "`/mejorar_mascota` - Sube de nivel a tu compañero para potenciar tus ganancias."
        ),
        inline=False
    )

    # Eventos y Administración
    embed.add_field(
        name="🎁 Eventos y Administración",
        value=(
            "`/sorteo_economia [premio]` - Sorteo interactivo con botón (Solo Dueños).\n"
            "`/dar [usuario] [cantidad]` - Da dinero (Solo Dueños).\n"
            "`/quitar [usuario] [cantidad/all]` - Retira dinero, acepta 'all' (Solo Dueños).\n"
            "`/reset-eco` - Resetea la economía completa del servidor (Solo Dueños)."
        ),
        inline=False
    )

    embed.set_footer(text="¡Usa los comandos correctamente y diviértete en el servidor!")
    await interaction.response.send_message(embed=embed, ephemeral=True)
    

# --- ADMINISTRACIÓN DUEÑOS ---
USUARIOS_PERMITIDOS = [1491476806203740373, 1439675836746829986]

@bot.tree.command(name="dar", description="Da dinero a un usuario")
async def dar(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    if interaction.user.id not in USUARIOS_PERMITIDOS:
        await interaction.response.send_message("❌ No tienes permisos para usar este comando.", ephemeral=True)
        return
        
    uid = str(usuario.id)
    asegurar_usuario(uid)
    datos[uid]["dinero"] += cantidad
    guardar_datos()
    await interaction.response.send_message(f"✅ Se le han dado {cantidad} a {usuario.name}.")

@bot.tree.command(name="quitar", description="Quita dinero a un usuario (ingresa cantidad o 'all')")
@app_commands.describe(cantidad="Escribe un número o la palabra 'all' para quitar todo")
async def quitar(interaction: discord.Interaction, usuario: discord.Member, cantidad: str):
    if interaction.user.id not in USUARIOS_PERMITIDOS:
        await interaction.response.send_message("❌ No tienes permisos para usar este comando.", ephemeral=True)
        return

    uid = str(usuario.id)
    if uid not in datos:
        await interaction.response.send_message("❌ Ese usuario no tiene registro de dinero.")
        return

    if cantidad.lower() == "all":
        retirado = datos[uid]["dinero"] + datos[uid]["banco"]
        datos[uid]["dinero"] = 0
        datos[uid]["banco"] = 0
        guardar_datos()
        await interaction.response.send_message(f"✅ Se le ha quitado TODO el dinero ({retirado}) a {usuario.name}.")
    else:
        try:
            monto = int(cantidad)
            if monto <= 0:
                await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
                return
            
            total_disponible = datos[uid]["dinero"] + datos[uid]["banco"]
            if monto > total_disponible:
                datos[uid]["dinero"] = 0
                datos[uid]["banco"] = 0
            else:
                if datos[uid]["dinero"] >= monto:
                    datos[uid]["dinero"] -= monto
                else:
                    restante = monto - datos[uid]["dinero"]
                    datos[uid]["dinero"] = 0
                    datos[uid]["banco"] -= restante
            
            guardar_datos()
            await interaction.response.send_message(f"✅ Se le han quitado {monto} a {usuario.name}.")
        except ValueError:
            await interaction.response.send_message("❌ Por favor ingresa un número válido o la palabra 'all'.", ephemeral=True)

@bot.tree.command(name="reset-eco", description="Resetea completamente la economía de todo el servidor")
async def reset_eco(interaction: discord.Interaction):
    if interaction.user.id not in USUARIOS_PERMITIDOS:
        await interaction.response.send_message("❌ No tienes permisos para usar este comando.", ephemeral=True)
        return
    
    global datos
    datos = {}
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    
    await interaction.response.send_message("🔄 **¡Economía reseteada con éxito!** Todos los saldos y cuentas han sido borrados.")


bot.run(os.environ['DISCORD_TOKEN'])
