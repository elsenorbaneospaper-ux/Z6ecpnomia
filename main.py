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

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("Bot listo con todos los comandos.")

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
            "carreras_gratis": 5, # Límite inicial de 5 carreras gratuitas con mascota por defecto
            "tiene_mascota_propia": False
        }
    else:
        # Asegurar compatibilidad con datos anteriores
        if "mascota_nombre" not in datos[uid]:
            datos[uid]["mascota_nombre"] = "Rayo"
            datos[uid]["mascota_emoji"] = "🐶"
            datos[uid]["carreras_gratis"] = 5
            datos[uid]["tiene_mascota_propia"] = False

# --- VISTA PARA LA CARRERA MULTIJUGADOR ---
class CarreraView(View):
    def __init__(self, retador: discord.Member, oponente: discord.Member, apuesta: int):
        super().__init__(timeout=30)
        self.retador = retador
        self.oponente = oponente
        self.apuesta = apuesta
        self.aceptado = False

    @discord.ui.button(label="Aceptar Reto 🏁", style=discord.ButtonStyle.green)
    async def aceptar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.oponente.id:
            await interaction.response.send_message("❌ ¡Este reto no es para ti!", ephemeral=True)
            return

        uid_retador = str(self.retador.id)
        uid_oponente = str(self.oponente.id)

        if datos[uid_retador]["dinero"] < self.apuesta:
            await interaction.response.send_message("❌ El retador ya no tiene suficiente dinero.", ephemeral=True)
            self.stop()
            return
        if datos[uid_oponente]["dinero"] < self.apuesta:
            await interaction.response.send_message("❌ No tienes suficiente dinero para aceptar.", ephemeral=True)
            self.stop()
            return

        self.aceptado = True
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(content=f"🏎️ **¡{self.oponente.name} aceptó el reto!** ¡Comienza la carrera...", view=self)

        datos[uid_retador]["dinero"] -= self.apuesta
        datos[uid_oponente]["dinero"] -= self.apuesta
        guardar_datos()

        await asyncio.sleep(2)
        ganador = random.choice([self.retador, self.oponente])
        uid_ganador = str(ganador.id)

        pozo_total = self.apuesta * 2
        datos[uid_ganador]["dinero"] += pozo_total
        guardar_datos()

        await interaction.followup.send(
            f"🏁 **¡RESULTADOS DE LA CARRERA!** 🏁\n\n"
            f"⚡ Motores a fondo... ¡y el ganador cruzando la meta es **{ganador.name}**!\n"
            f"💰 Se lleva el pozo total de **{pozo_total}** monedas."
        )
        self.stop()

    async def on_timeout(self):
        if not self.aceptado:
            for child in self.children:
                child.disabled = True

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

# --- APUESTAS ---
@bot.tree.command(name="suerte", description="Prueba tu suerte apostando a cara o cruz")
@app_commands.choices(caraocruz=[
    app_commands.Choice(name="Cara", value="cara"),
    app_commands.Choice(name="Cruz", value="cruz")
])
@app_commands.checks.cooldown(1, 180.0, key=lambda i: i.user.id)
async def suerte(interaction: discord.Interaction, cantidad: int, caraocruz: str):
    if cantidad <= 0 or cantidad > 1000:
        await interaction.response.send_message("❌ Apuesta inválida (Límite: 1 a 1000).", ephemeral=True)
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
        msg = f"🪙 ¡Salió **{resultado}**! Ganaste **{ganancia}**."
    else:
        datos[uid]["dinero"] -= cantidad
        msg = f"🪙 ¡Salió **{resultado}**! Perdiste **{cantidad}**."

    guardar_datos()
    await interaction.response.send_message(msg)

@suerte.error
async def suerte_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"⏳ Espera {round(error.retry_after)} segundos para volver a apostar.", ephemeral=True)

# --- NUEVO COMANDO: COMPRAR MASCOTA ---
@bot.tree.command(name="comprar_mascota", description="Compra y personaliza tu propia mascota con nombre y emoji")
async def comprar_mascota(interaction: discord.Interaction, nombre: str, emoji: str):
    uid = str(interaction.user.id)
    asegurar_usuario(uid)
    
    costo = 2500 # Precio por comprar tu propia mascota personalizada
    if datos[uid]["dinero"] < costo:
        await interaction.response.send_message(f"❌ Necesitas **{costo}** monedas en mano para comprar y registrar tu propia mascota.", ephemeral=True)
        return

    datos[uid]["dinero"] -= costo
    datos[uid]["mascota_nombre"] = nombre
    datos[uid]["mascota_emoji"] = emoji
    datos[uid]["tiene_mascota_propia"] = True
    datos[uid]["carreras_gratis"] = 99999 # Acceso ilimitado a carreras
    guardar_datos()

    await interaction.response.send_message(
        f"🎉 **¡FELICIDADES!** 🎉\n\n"
        f"Has adoptado y registrado a tu nueva mascota:\n"
        f"🐾 {emoji} **{nombre}** (Costo: {costo} monedas).\n"
        f"¡Ahora tienes carreras ilimitadas y listas para la acción!"
    )

# --- COMANDO CARRERA ACTUALIZADO (RIVAL OPCIONAL) ---
@bot.tree.command(name="carrera", description="Reta a un usuario o compite contra la máquina")
@app_commands.describe(apuesta="Cantidad a apostar", usuario="Opcional: Reta a otro jugador")
@app_commands.checks.cooldown(1, 180.0, key=lambda i: i.user.id)
async def carrera(interaction: discord.Interaction, apuesta: int, usuario: discord.Member = None):
    uid = str(interaction.user.id)
    asegurar_usuario(uid)

    if apuesta <= 0:
        await interaction.response.send_message("❌ La apuesta debe ser mayor a 0.", ephemeral=True)
        return

    if datos[uid]["dinero"] < apuesta:
        await interaction.response.send_message("❌ No tienes suficiente dinero en mano para esta apuesta.", ephemeral=True)
        return

    # Validar límite de carreras gratis si no tiene mascota propia
    if not datos[uid]["tiene_mascota_propia"]:
        if datos[uid]["carreras_gratis"] <= 0:
            await interaction.response.send_message(
                "❌ Se te han agotado tus **5 carreras gratuitas** con la mascota temporal.\n"
                "Usa `/comprar_mascota [nombre] [emoji]` para conseguir una propia y desbloquear carreras ilimitadas.", 
                ephemeral=True
            )
            return
        datos[uid]["carreras_gratis"] -= 1

    mascota_str = f"{datos[uid]['mascota_emoji']} {datos[uid]['mascota_nombre']}"

    # CASO 1: Carrera contra la máquina (Solitaria)
    if usuario is None:
        datos[uid]["dinero"] -= apuesta
        guardar_datos()

        await interaction.response.send_message(f"🏁 Tu mascota **{mascota_str}** ha entrado a la pista contra la IA. ¡Acelerando...")
        await asyncio.sleep(2)

        if random.random() < 0.50:
            premio = apuesta * 2
            datos[uid]["dinero"] += premio
            guardar_datos()
            await interaction.followup.send(f"🏆 ¡Victoria! **{mascota_str}** ganó la carrera. Te llevas **{premio}** monedas.")
        else:
            guardar_datos()
            await interaction.followup.send(f"❌ ¡Derrota! **{mascota_str}** se tropezó en la pista y perdiste **{apuesta}** monedas.")
        return

    # CASO 2: Carrera contra otro jugador
    if interaction.user.id == usuario.id:
        await interaction.response.send_message("❌ No puedes retarte a ti mismo.", ephemeral=True)
        return

    if usuario.bot:
        await interaction.response.send_message("❌ No puedes retar a un bot de Discord.", ephemeral=True)
        return

    view = CarreraView(retador=interaction.user, oponente=usuario, apuesta=apuesta)
    await interaction.response.send_message(
        f"🏎️ **¡DUELO DE CARRERA PROPUESTO!** 🏎️\n\n"
        f"👤 {interaction.user.mention} (con su mascota {mascota_str}) ha retado a {usuario.mention} por **{apuesta}** monedas.\n"
        f"👇 ¡{usuario.mention}, haz clic en el botón de abajo para aceptar!",
        view=view
    )

@carrera.error
async def carrera_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"⏳ Estás en cooldown. Espera {round(error.retry_after)} segundos.", ephemeral=True)

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

# --- AYUDA Y OTROS ---
@bot.tree.command(name="ayuda", description="Muestra la lista de comandos")
async def ayuda(interaction: discord.Interaction):
    mensaje = (
        "📜 **Lista de Comandos Actualizada**\n\n"
        "🐾 **Mascotas:**\n"
        "• `/comprar_mascota [nombre] [emoji]` - Crea tu mascota propia (Desbloquea carreras ilimitadas).\n"
        "• `/mejorar_mascota` - Sube de nivel a tu compañero.\n\n"
        "⚖️ **Apuestas y Carreras:**\n"
        "• `/carrera [apuesta] [usuario_opcional]` - Compite contra la IA (gratis las primeras 5 veces) o reta a un jugador.\n"
        "• `/suerte [monto] [cara/cruz]` - Apuesta dinero.\n"
        "• `/trabajar` - Gana dinero.\n\n"
        "💰 **Economía básica:** `/dinero`, `/balance`, `/verbanco`, `/addbanco`, `/sacarbanco`, `/top`, `/transferir`"
    )
    await interaction.response.send_message(mensaje)

bot.run(os.environ['DISCORD_TOKEN'])
	
