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
            "carreras_gratis": 5,
            "tiene_mascota_propia": False
        }
    else:
        if "mascota_nombre" not in datos[uid]:
            datos[uid]["mascota_nombre"] = "Rayo"
            datos[uid]["mascota_emoji"] = "🐶"
            datos[uid]["carreras_gratis"] = 5
            datos[uid]["tiene_mascota_propia"] = False

# --- VISTA PARA EL SORTEO ---
class SorteoView(View):
    def __init__(self, premio: int, permitidos: list):
        super().__init__(timeout=None)
        self.premio = premio
        self.permitidos = permitidos
        self.participantes = set()

    @discord.ui.button(label="Participar 🎉", style=discord.ButtonStyle.green, custom_id="sorteo_participar_btn")
    async def participar(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        asegurar_usuario(uid)
        if interaction.user.id in self.participantes:
            self.participantes.remove(interaction.user.id)
            await interaction.response.send_message("❌ Te has salido del sorteo.", ephemeral=True)
        else:
            self.participantes.add(interaction.user.id)
            await interaction.response.send_message("✅ ¡Te has unido al sorteo correctamente!", ephemeral=True)

    @discord.ui.button(label="Terminar Sorteo 🏆", style=discord.ButtonStyle.red, custom_id="sorteo_terminar_btn")
    async def terminar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.permitidos:
            await interaction.response.send_message("❌ No tienes permisos para finalizar este sorteo.", ephemeral=True)
            return

        if not self.participantes:
            await interaction.response.send_message("❌ No hay participantes registrados en el sorteo.", ephemeral=True)
            return

        uid_ganador = random.choice(list(self.participantes))
        str_uid = str(uid_ganador)
        asegurar_usuario(str_uid)

        datos[str_uid]["dinero"] += self.premio
        guardar_datos()

        try:
            usuario_ganador = await interaction.guild.fetch_member(uid_ganador)
            nombre_ganador = usuario_ganador.mention
        except:
            nombre_ganador = f"<@{uid_ganador}>"

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=f"🎉 **¡SORTEO FINALIZADO!** 🎉\n\n"
                    f"💰 Premio entregado: **{self.premio}**\n"
                    f"👑 ¡El ganador afortunado es {nombre_ganador}!",
            view=self
        )
        self.stop()

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
        asegurar_usuario(uid_retador)
        asegurar_usuario(uid_oponente)

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

# --- COMANDO CARRERA ---
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

# --- COMANDO AYUDA ACTUALIZADO ---
@bot.tree.command(name="ayuda", description="Muestra la lista completa de todos los comandos disponibles")
async def ayuda(interaction: discord.Interaction):
    mensaje = (
        "📜 **Lista Completa de Comandos del Bot**\n\n"
        "🐾 **Sistema de Mascotas:**\n"
        "• `/comprar_mascota [nombre] [emoji]` - Crea y personaliza tu mascota propia (Desbloquea carreras ilimitadas).\n"
        "• `/mejorar_mascota` - Sube de nivel a tu compañero para potenciar tus ganancias.\n\n"
        "💼 **Trabajos:**\n"
        "• `/trabajar` - Gana dinero trabajando honestamente (Bonus por mascota | Cooldown: 3m).\n\n"
        "⚖️ **Acción, Riesgo y Apuestas:**\n"
        "• `/crimen` - Intenta un crimen riesgoso (Cooldown: 8m).\n"
        "• `/robar [usuario]` - Intenta robarle a otro usuario (Cooldown: 6m).\n"
        "• `/robarbanco [usuario]` - Atraca el banco de otro usuario (Cooldown: 10m).\n"
        "• `/suerte [monto] [cara/cruz]` - Apuesta tu dinero (Cooldown: 3m).\n"
        "• `/carrera [apuesta] [usuario_opcional]` - Compite contra la IA (primeras 5 gratis) o reta a un jugador.\n\n"
        "💰 **Economía y Bancos:**\n"
        "• `/dinero` - Consulta tu dinero en mano.\n"
        "• `/verbanco` - Consulta tu saldo en el banco.\n"
        "• `/addbanco [cantidad]` - Deposita dinero.\n"
        "• `/sacarbanco [cantidad]` - Retira dinero del banco.\n"
        "• `/balance` - Mira tu fortuna total y nivel de mascota.\n"
        "• `/top` - Ranking de los más ricos del servidor.\n"
        "• `/transferir [usuario] [cantidad/all]` - Envía dinero (soporta 'all' | Cooldown: 2m).\n\n"
        "🎁 **Eventos y Administración:**\n"
        "• `/sorteo_economia [premio]` - Sorteo interactivo con botón (Solo Dueños).\n"
        "• `/dar [usuario] [cantidad]` - Da dinero (Solo Dueños).\n"
        "• `/quitar [usuario] [cantidad/all]` - Retira dinero, acepta 'all' (Solo Dueños).\n"
        "• `/reset-eco` - Resetea la economía completa del servidor (Solo Dueños)."
    )
    await interaction.response.send_message(mensaje, ephemeral=False)

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

@bot.tree.command(name="sorteo_economia", description="Crea un sorteo interactivo donde los usuarios participan con un botón")
async def sorteo_economia(interaction: discord.Interaction, premio: int):
    if interaction.user.id not in USUARIOS_PERMITIDOS:
        await interaction.response.send_message("❌ No tienes permisos para usar este comando.", ephemeral=True)
        return

    if premio <= 0:
        await interaction.response.send_message("❌ El premio del sorteo debe ser mayor a 0.", ephemeral=True)
        return

    view = SorteoView(premio=premio, permitidos=USUARIOS_PERMITIDOS)
    
    await interaction.response.send_message(
        f"🎁 **¡NUEVO SORTEO DE ECONOMÍA!** 🎁\n\n"
        f"💰 Premio en juego: **{premio}**\n"
        f"👇 Haz clic en el botón **Participar** para unirte. ¡Si vuelves a hacer clic te saldrás del sorteo!",
        view=view
    )

bot.run(os.environ['DISCORD_TOKEN'])
