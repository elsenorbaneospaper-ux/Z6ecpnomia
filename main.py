import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Modal, TextInput
import aiofiles
import random
import json
import os
import asyncio
from flask import Flask
from threading import Thread

# Configuración
intents = discord.Intents.default()
intents.message_content = True  # <--- ESTA LÍNEA ES LA CLAVE

# Ahora sí, el bot usará esos permisos
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

# --- COMANDOS DE BANCO ---
@bot.tree.command(name="verbanco", description="Mira cuánto tienes guardado")
async def verbanco(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    saldo = datos.get(uid, {}).get("banco", 0)
    await interaction.response.send_message(f"🏦 Tu saldo seguro es: **{saldo}**")

@bot.tree.command(name="addbanco", description="Deposita en el banco")
async def addbanco(interaction: discord.Interaction, cantidad: int):
    uid = str(interaction.user.id)
    if uid not in datos: datos[uid] = {"dinero": 1000, "banco": 0}
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
    if cantidad > datos.get(uid, {}).get("banco", 0):
        await interaction.response.send_message("❌ Fondos insuficientes en banco.")
    else:
        datos[uid]["banco"] -= cantidad
        datos[uid]["dinero"] += cantidad
        guardar_datos()
        await interaction.response.send_message(f"✅ Retiraste {cantidad}.")




@bot.tree.command(name="suerte", description="Prueba tu suerte apostando a cara o cruz")
@app_commands.choices(caraocruz=[
    app_commands.Choice(name="Cara", value="cara"),
    app_commands.Choice(name="Cruz", value="cruz")
])
@app_commands.checks.cooldown(1, 180.0, key=lambda i: i.user.id)
async def suerte(interaction: discord.Interaction, cantidad: int, caraocruz: str):
    # --- MÉTODO DE SEGURIDAD (EVITAR NEGATIVOS Y VALORES EXTRAÑOS) ---
    if cantidad <= 0:
        await interaction.response.send_message("❌ No puedes apostar cantidades negativas o cero.", ephemeral=True)
        return

    # --- VALIDACIÓN DE LÍMITE MÁXIMO ---
    if cantidad > 1000:
        await interaction.response.send_message("❌ El límite máximo de apuesta es 1000.", ephemeral=True)
        return

    # --- LÓGICA DEL JUEGO ---
    uid = str(interaction.user.id)
    eleccion_usuario = caraocruz.lower()
    
    if eleccion_usuario not in ["cara", "cruz"]:
        await interaction.response.send_message("❌ Debes elegir entre 'cara' o 'cruz'.", ephemeral=True)
        return

    resultado = random.choice(["cara", "cruz"])

    # Procesar apuesta
    if eleccion_usuario == resultado:
        ganancia = cantidad * 2
        # datos[uid]["dinero"] += cantidad  # Ajusta según tu estructura
        msg = f"🪙 ¡Salió **{resultado}**! Ganaste **{cantidad}**."
    else:
        # datos[uid]["dinero"] -= cantidad  # Ajusta según tu estructura
        msg = f"🪙 ¡Salió **{resultado}**! Perdiste **{cantidad}**."

    # guardar_datos()
    await interaction.response.send_message(msg)

# Manejador de errores para avisar del tiempo de espera restante si intentan usarlo antes de tiempo
@suerte.error
async def suerte_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        minutos = round(error.retry_after / 60, 1)
        segundos = round(error.retry_after)
        await interaction.response.send_message(f"⏳ Estás en cooldown. Debes esperar {segundos} segundos (aprox. {minutos} minutos) antes de volver a apostar.", ephemeral=True)
    else:
        raise error
		
    # -----------------------------------------------

    # Aquí sigue tu código de saldo y lógica de juego...
	
    # Procesar apuesta
    eleccion_usuario = caraocruz.lower()
    resultado = random.choice(["cara", "cruz"])
    
    # Respondemos al usuario
    if eleccion_usuario == resultado:
        ganancia = monto * 2
        datos[uid]["dinero"] += monto # Recupera lo apostado + lo ganado
        msg = f"🎲 ¡Salió **{resultado}**! Ganaste **{monto}**."
    else:
        datos[uid]["dinero"] -= monto
        msg = f"🎲 ¡Salió **{resultado}**! Perdiste **{monto}**."
    
    guardar_datos()
    await interaction.response.send_message(msg)
	
@bot.tree.command(name="ayuda", description="Muestra la lista de todos los comandos disponibles")
async def ayuda(interaction: discord.Interaction):
    mensaje = (
        "📜 **Lista de Comandos del Bot**\n\n"
        "💰 **Economía:**\n"
        "• `/dinero` - Consulta tu dinero en mano.\n"
        "• `/verbanco` - Consulta tu saldo en el banco.\n"
        "• `/addbanco [cantidad]` - Deposita dinero.\n"
        "• `/sacarbanco [cantidad]` - Retira dinero.\n"
        "• `/balance` - Mira tu fortuna total.\n"
        "• `/top` - Mira el ranking de los más ricos.\n"
        "• `/transferir [usuario] [cantidad]` - Envía dinero a alguien.\n\n"
        "⚖️ **Acción y Riesgo (¡Cuidado con la prisión!):**\n"
        "• `/trabajar` - Gana dinero trabajando.\n"
        "• `/crimen` - Intenta un robo arriesgado.\n"
        "• `/robar [usuario]` - Intenta robarle a otro usuario.\n"
        "• `/robarbanco [usuario]` - Atraca el banco de otro usuario.\n"
        "• `/suerte [cara/cruz] [monto]` - Apuesta tu dinero.\n\n"
        "👑 **Administración:**\n"
        "• `/dar [usuario] [cantidad]` - Entrega dinero (Solo dueño).\n"
        "• `/quitar [usuario] [cantidad]` - Retira dinero (Solo dueño)."
    )
    await interaction.response.send_message(mensaje, ephemeral=False)
										
	
# --- COMANDOS DE ADMINISTRACIÓN (Solo Dueño) ---
@bot.tree.command(name="dar", description="Da dinero a un usuario (Dueño)")
async def dar(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    # Verificación de ID de dueño
    if interaction.user.id != 1491476806203740373:
        await interaction.response.send_message("❌ No tienes permiso para usar este comando.", ephemeral=True)
        return

    uid = str(usuario.id)
    if uid not in datos: datos[uid] = {"dinero": 1000, "banco": 0}
    
    datos[uid]["dinero"] += cantidad
    guardar_datos()
    await interaction.response.send_message(f"✅ Se le han dado {cantidad} a {usuario.name}.")

@bot.tree.command(name="quitar", description="Quita dinero a un usuario (Dueño)")
async def quitar(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    # Verificación de ID de dueño
    if interaction.user.id != 1491476806203740373:
        await interaction.response.send_message("❌ No tienes permiso para usar este comando.", ephemeral=True)
        return

    uid = str(usuario.id)
    if uid in datos:
        datos[uid]["dinero"] -= cantidad
        guardar_datos()
        await interaction.response.send_message(f"✅ Se le han quitado {cantidad} a {usuario.name}.")
    else:
        await interaction.response.send_message("❌ Ese usuario no tiene registro de dinero.")
# --- COMANDOS DE ACCIÓN ---

@bot.tree.command(name="dinero", description="Mira cuánto dinero tienes en mano")
async def dinero(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    # Si el usuario no existe, le damos el saldo inicial
    if uid not in datos: datos[uid] = {"dinero": 1000, "banco": 0}
    saldo = datos[uid]["dinero"]
    await interaction.response.send_message(f"💵 Tienes **{saldo}** en mano.")

@bot.tree.command(name="trabajar", description="Gana dinero trabajando honestamente")
async def trabajar(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    if uid not in datos: datos[uid] = {"dinero": 1000, "banco": 0}
    
    ganancia = random.randint(100, 500)
    datos[uid]["dinero"] += ganancia
    guardar_datos()
    await interaction.response.send_message(f"✅ ¡Buen trabajo! Ganaste **{ganancia}**.")


    # --- LÓGICA DE ARRESTO COMÚN ---
async def procesar_arresto(interaction: discord.Interaction):
    duracion = random.randint(1, 3) # Condena random
    ROL_PRISIONERO_ID = 1530378140923461764
    rol_prisionero = interaction.guild.get_role(ROL_PRISIONERO_ID)
    
    await interaction.user.add_roles(rol_prisionero)
    await interaction.followup.send(f"🚨 ¡Te atraparon! Serás arrestado por **{duracion} minutos**.")
    
    # Tiempo en segundo plano
    await asyncio.sleep(duracion * 60)
    
    await interaction.user.remove_roles(rol_prisionero)
    try:
        await interaction.user.send("🔓 Tu condena terminó. Ya puedes acceder a la economía del servidor.")
    except:
        pass
# --- COMANDO /CRIMEN CORREGIDO Y FUNCIONAL ---
@bot.tree.command(name="crimen", description="Comete un crimen (Riesgoso)")
async def crimen(interaction: discord.Interaction):
    await interaction.response.defer() # Necesario para procesar el arresto luego
    
    uid = str(interaction.user.id)
    if uid not in datos: datos[uid] = {"dinero": 1000, "banco": 0}
    
    # 50% de probabilidad
    if random.random() < 0.50:
        # Éxito: calcular cantidad aleatoria
        ganancia = random.randint(500, 1500)
        datos[uid]["dinero"] += ganancia
        guardar_datos() # ¡IMPORTANTE: Esto guarda el dinero en el archivo!
        
        await interaction.followup.send(f"😈 ¡Éxito! Lograste robar **{ganancia}**.")
    else:
        # Fallo: activar el arresto
        await procesar_arresto(interaction)
		
# --- COMANDO /ROBAR --- 
@bot.tree.command(name="robar", description="Intenta robar a otro usuario")
async def robar(interaction: discord.Interaction, usuario: discord.Member):
    await interaction.response.defer()
    if random.random() < 0.40:
        await interaction.followup.send(f"💰 ¡Éxito! Robaste a {usuario.name}.")
    else:
        await procesar_arresto(interaction)

# --- COMANDO /ROBARBANCO ---
@bot.tree.command(name="robarbanco", description="Atraca el banco")
async def robarbanco(interaction: discord.Interaction, usuario: discord.Member):
    await interaction.response.defer()
    if random.random() < 0.20:
        await interaction.followup.send(f"🏦 ¡BOOM! Robaste el banco de {usuario.name}.")
    else:
        await procesar_arresto(interaction)
		
    guardar_datos()
# --- COMANDO /BALANCE ---
@bot.tree.command(name="balance", description="Mira tu fortuna total (Mano + Banco)")
async def balance(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    if uid not in datos: datos[uid] = {"dinero": 1000, "banco": 0}
    
    total = datos[uid]["dinero"] + datos[uid]["banco"]
    await interaction.response.send_message(f"💰 Tu fortuna total es de **{total}**.")

# --- COMANDO /TOP ---
@bot.tree.command(name="top", description="Mira quién es el más rico del servidor")
async def top(interaction: discord.Interaction):
    # Ordenamos los usuarios por dinero de mayor a menor
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

# --- FUNCIONES DE BASE DE DATOS (ASÍNCRONAS) ---
async def load_data():
    try:
        async with aiofiles.open('eco.json', mode='r') as f:
            content = await f.read()
            return json.loads(content)
    except FileNotFoundError:
        return {}

async def save_data(data):
    async with aiofiles.open('eco.json', mode='w') as f:
        await f.write(json.dumps(data, indent=4))



# --- COMANDO /TRANSFERIR ---
@bot.tree.command(name="transferir", description="Transfiere dinero a otro usuario")
async def transferir(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    uid_emisor = str(interaction.user.id)
    uid_receptor = str(usuario.id)
    
    # Validaciones
    if cantidad <= 0:
        await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
        return
        
    if uid_emisor not in datos or datos[uid_emisor]["dinero"] < cantidad:
        await interaction.response.send_message("❌ No tienes suficiente dinero en mano.", ephemeral=True)
        return
        
    # Realizar transferencia
    datos[uid_emisor]["dinero"] -= cantidad
    if uid_receptor not in datos: datos[uid_receptor] = {"dinero": 1000, "banco": 0}
    datos[uid_receptor]["dinero"] += cantidad
    
    guardar_datos()
    await interaction.response.send_message(f"💸 Has transferido **{cantidad}** a {usuario.name}.")


bot.run(os.environ['DISCORD_TOKEN'])
