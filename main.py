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

# --- ACCIÓN Y RIESGO / SOLO ARRESTO CON AVISO POR DM ---

@bot.tree.command(name="crimen", description="Intenta un crimen riesgoso")
async def crimen(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)
    
    if random.choice([True, False]):
        premio = random.randint(300, 900)
        await usuarios_col.update_one({"_id": uid}, {"$inc": {"dinero": premio}})
        await interaction.response.send_message(f"🥷 ¡Robo exitoso! Conseguiste **{premio}** en mano.")
    else:
        rol_id = 1530378140923461764
        rol = interaction.guild.get_role(rol_id)
        tiempo_segundos = random.randint(30, 600) # Máximo 10 minutos (600s)
        
        mensaje = "🚨 ¡Te atraparon intentando el crimen!"
        
        if rol:
            try:
                await interaction.user.add_roles(rol)
                minutos = tiempo_segundos // 60
                segundos = tiempo_segundos % 60
                tiempo_texto = f"{minutos} min y {segundos} seg" if minutos > 0 else f"{segundos} seg"
                mensaje += f"\n🔒 Has sido arrestado y enviado a prisión por **{tiempo_texto}**."
                
                await interaction.response.send_message(mensaje)
                
                await asyncio.sleep(tiempo_segundos)
                if rol in interaction.user.roles:
                    await interaction.user.remove_roles(rol)
                    try:
                        await interaction.user.send("🔓 Tu condena terminó, puedes acceder a la economía del servidor.")
                    except:
                        pass
                return
            except Exception as e:
                if not interaction.response.is_done():
                    await interaction.response.send_message(mensaje)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message(mensaje)

@bot.tree.command(name="robar", description="Intenta robarle a otro usuario")
async def robar(interaction: discord.Interaction, usuario: discord.Member):
    uid_origen = str(interaction.user.id)
    uid_destino = str(usuario.id)
    
    if uid_origen == uid_destino:
        await interaction.response.send_message("❌ No puedes robarte a ti mismo.", ephemeral=True)
        return
        
    await asegurar_usuario(uid_origen)
    await asegurar_usuario(uid_destino)
    
    u_objetivo = await usuarios_col.find_one({"_id": uid_destino})
    dinero_objetivo = u_objetivo.get("dinero", 0)
    
    if dinero_objetivo < 100:
        await interaction.response.send_message(f"❌ {usuario.mention} no tiene suficiente dinero en mano para ser robado.", ephemeral=True)
        return
        
    if random.choice([True, False]):
        botin = random.randint(50, min(300, dinero_objetivo))
        await usuarios_col.update_one({"_id": uid_origen}, {"$inc": {"dinero": botin}})
        await usuarios_col.update_one({"_id": uid_destino}, {"$inc": {"dinero": -botin}})
        await interaction.response.send_message(f"🥷 ¡Robo exitoso! Le robaste **{botin}** a {usuario.mention}.")
    else:
        rol_id = 1530378140923461764
        rol = interaction.guild.get_role(rol_id)
        tiempo_segundos = random.randint(30, 600)
        
        mensaje = f"🚓 ¡La policía te atrapó intentando robar a {usuario.mention}!"
        
        if rol:
            try:
                await interaction.user.add_roles(rol)
                minutos = tiempo_segundos // 60
                segundos = tiempo_segundos % 60
                tiempo_texto = f"{minutos} min y {segundos} seg" if minutos > 0 else f"{segundos} seg"
                mensaje += f"\n🔒 Estás arrestado por **{tiempo_texto}**."
                
                await interaction.response.send_message(mensaje)
                
                await asyncio.sleep(tiempo_segundos)
                if rol in interaction.user.roles:
                    await interaction.user.remove_roles(rol)
                    try:
                        await interaction.user.send("🔓 Tu condena terminó, puedes acceder a la economía del servidor.")
                    except:
                        pass
                return
            except:
                if not interaction.response.is_done():
                    await interaction.response.send_message(mensaje)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message(mensaje)

@bot.tree.command(name="robarbanco", description="Atraca el banco de otro usuario")
async def robarbanco(interaction: discord.Interaction, usuario: discord.Member):
    uid_origen = str(interaction.user.id)
    uid_destino = str(usuario.id)
    
    if uid_origen == uid_destino:
        await interaction.response.send_message("❌ No puedes atracar tu propio banco.", ephemeral=True)
        return
        
    await asegurar_usuario(uid_origen)
    await asegurar_usuario(uid_destino)
    
    u_objetivo = await usuarios_col.find_one({"_id": uid_destino})
    banco_objetivo = u_objetivo.get("banco", 0)
    
    if banco_objetivo < 500:
        await interaction.response.send_message(f"❌ El banco de {usuario.mention} está muy protegido o no tiene suficiente saldo.", ephemeral=True)
        return
        
    if random.choice([True, False]):
        botin = random.randint(200, min(1000, banco_objetivo))
        await usuarios_col.update_one({"_id": uid_origen}, {"$inc": {"dinero": botin}})
        await usuarios_col.update_one({"_id": uid_destino}, {"$inc": {"banco": -botin}})
        await interaction.response.send_message(f"🏦 ¡Atraco bancario exitoso! Sustrajiste **{botin}** del banco de {usuario.mention}.")
    else:
        rol_id = 1530378140923461764
        rol = interaction.guild.get_role(rol_id)
        tiempo_segundos = random.randint(30, 600)
        
        mensaje = f"🚨 ¡Falló el atraco al banco de {usuario.mention}!"
        
        if rol:
            try:
                await interaction.user.add_roles(rol)
                minutos = tiempo_segundos // 60
                segundos = tiempo_segundos % 60
                tiempo_texto = f"{minutos} min y {segundos} seg" if minutos > 0 else f"{segundos} seg"
                mensaje += f"\n🔒 Te arrestaron y permanecerás en prisión por **{tiempo_texto}**."
                
                await interaction.response.send_message(mensaje)
                
                await asyncio.sleep(tiempo_segundos)
                if rol in interaction.user.roles:
                    await interaction.user.remove_roles(rol)
                    try:
                        await interaction.user.send("🔓 Tu condena terminó, puedes acceder a la economía del servidor.")
                    except:
                        pass
                return
            except:
                if not interaction.response.is_done():
                    await interaction.response.send_message(mensaje)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message(mensaje)

# --- ECONOMÍA Y BANCOS ---

@bot.tree.command(name="dinero", description="Consulta tu dinero en mano o el de otro usuario")
async def dinero(interaction: discord.Interaction, usuario: discord.Member = None):
    target = usuario or interaction.user
    uid = str(target.id)
    await asegurar_usuario(uid)
    
    user_data = await usuarios_col.find_one({"_id": uid})
    await interaction.response.send_message(f"💵 {target.mention} tiene **{user_data.get('dinero', 0)}** en mano.")

@bot.tree.command(name="verbanco", description="Consulta tu saldo en el banco o el de otro usuario")
async def verbanco(interaction: discord.Interaction, usuario: discord.Member = None):
    target = usuario or interaction.user
    uid = str(target.id)
    await asegurar_usuario(uid)
    
    user_data = await usuarios_col.find_one({"_id": uid})
    await interaction.response.send_message(f"🏦 {target.mention} tiene **{user_data.get('banco', 0)}** en el banco.")

@bot.tree.command(name="addbanco", description="Deposita dinero en el banco")
async def addbanco(interaction: discord.Interaction, cantidad: int):
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)
    user_data = await usuarios_col.find_one({"_id": uid})
    
    if cantidad <= 0 or user_data.get("dinero", 0) < cantidad:
        await interaction.response.send_message("❌ Cantidad inválida o no tienes suficiente dinero en mano.", ephemeral=True)
        return
        
    await usuarios_col.update_one(
        {"_id": uid},
        {"$inc": {"dinero": -cantidad, "banco": cantidad}}
    )
    await interaction.response.send_message(f"✅ Has depositado **{cantidad}** en el banco.")

@bot.tree.command(name="sacarbanco", description="Retira dinero del banco")
async def sacarbanco(interaction: discord.Interaction, cantidad: int):
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)
    user_data = await usuarios_col.find_one({"_id": uid})
    
    if cantidad <= 0 or user_data.get("banco", 0) < cantidad:
        await interaction.response.send_message("❌ Cantidad inválida o no tienes suficiente dinero en el banco.", ephemeral=True)
        return
        
    await usuarios_col.update_one(
        {"_id": uid},
        {"$inc": {"banco": -cantidad, "dinero": cantidad}}
    )
    await interaction.response.send_message(f"✅ Has retirado **{cantidad}** del banco.")

@bot.tree.command(name="balance", description="Mira tu fortuna total y nivel de mascota (o la de otro usuario)")
async def balance(interaction: discord.Interaction, usuario: discord.Member = None):
    target = usuario or interaction.user
    uid = str(target.id)
    await asegurar_usuario(uid)
    
    u = await usuarios_col.find_one({"_id": uid})
    total = u.get("dinero", 0) + u.get("banco", 0)
    await interaction.response.send_message(f"📊 **Balance de {target.name}**:\n💵 Mano: **{u.get('dinero', 0)}**\n🏦 Banco: **{u.get('banco', 0)}**\n💎 Total: **{total}**\n{u.get('mascota_emoji', '🐾')} Mascota Nivel: **{u.get('mascota_nivel', 1)}**")

@bot.tree.command(name="top", description="Ranking de los más ricos del servidor")
async def top(interaction: discord.Interaction):
    cursor = usuarios_col.find().sort([("dinero", -1), ("banco", -1)]).limit(5)
    texto = "🏆 **Top 5 más ricos del servidor:**\n\n"
    async for i, user in enumerate(cursor, 1):
        total = user.get("dinero", 0) + user.get("banco", 0)
        try:
            member = await bot.fetch_user(int(user["_id"]))
            nombre = member.name
        except:
            nombre = "Usuario desconocido"
        texto += f"{i}. {nombre}: **{total}**\n"
    await interaction.response.send_message(texto)

@bot.tree.command(name="transferir", description="Envía dinero a otro usuario (soporta cantidad o 'all')")
async def transferir(interaction: discord.Interaction, usuario: discord.Member, cantidad: str):
    uid_origen = str(interaction.user.id)
    uid_destino = str(usuario.id)
    
    if uid_origen == uid_destino:
        await interaction.response.send_message("❌ No puedes transferirte dinero a ti mismo.", ephemeral=True)
        return
        
    await asegurar_usuario(uid_origen)
    await asegurar_usuario(uid_destino)
    
    u_origen = await usuarios_col.find_one({"_id": uid_origen})
    dinero_mano = u_origen.get("dinero", 0)
    
    if cantidad.lower() == "all":
        monto = dinero_mano
    else:
        try:
            monto = int(cantidad)
        except ValueError:
            await interaction.response.send_message("❌ Debes ingresar un número válido o la palabra 'all'.", ephemeral=True)
            return
            
    if monto <= 0 or dinero_mano < monto:
        await interaction.response.send_message("❌ No tienes suficiente dinero en mano para realizar esta transferencia.", ephemeral=True)
        return
        
    await usuarios_col.update_one({"_id": uid_origen}, {"$inc": {"dinero": -monto}})
    await usuarios_col.update_one({"_id": uid_destino}, {"$inc": {"dinero": monto}})
    await interaction.response.send_message(f"💸 Has transferido exitosamente **{monto}** a {usuario.mention}.")
    

# --- CLASE PARA EL BOTÓN DE COHETE CRASH ---
class CoheteView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, uid: str, apuesta: int):
        super().__init__(timeout=60)
        self.interaction = interaction
        self.uid = uid
        self.apuesta = apuesta
        self.multiplicador = 1.0
        self.parado = False
        self.mensaje_obj = None

    @discord.ui.button(label="🚀 ¡Retirarse (Cash Out)!", style=discord.ButtonStyle.green)
    async def retirar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("❌ Este no es tu cohete.", ephemeral=True)
            return

        if self.parado:
            return

        self.parado = True
        ganancia = int(self.apuesta * self.multiplicador)
        
        await usuarios_col.update_one({"_id": self.uid}, {"$inc": {"dinero": ganancia}})
        
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=f"🎯 **¡CASH OUT EXITOSO!**\n🚀 Te retiraste con un multiplicador de **{self.multiplicador:.2f}x**.\n💰 Ganaste **{ganancia}** de dinero.",
            view=self
        )
        self.stop()


# --- CLASE PARA EL BOTÓN DE DUELO DE CARRERA ---
class DueloView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, uid_origen: str, uid_destino: str, apuesta: int, usuario_destino: discord.Member):
        super().__init__(timeout=60)
        self.interaction = interaction
        self.uid_origen = uid_origen
        self.uid_destino = uid_destino
        self.apuesta = apuesta
        self.usuario_destino = usuario_destino

    @discord.ui.button(label="Aceptar duelo", style=discord.ButtonStyle.green)
    async def aceptar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.uid_destino:
            await interaction.response.send_message("❌ Este duelo no es para ti.", ephemeral=True)
            return

        await asegurar_usuario(self.uid_origen)
        await asegurar_usuario(self.uid_destino)
        
        u_origen = await usuarios_col.find_one({"_id": self.uid_origen})
        u_destino = await usuarios_col.find_one({"_id": self.uid_destino})

        if u_origen.get("dinero", 0) < self.apuesta:
            await interaction.response.edit_message(content="❌ El creador del duelo ya no tiene suficiente dinero.", view=None)
            self.stop()
            return

        if u_destino.get("dinero", 0) < self.apuesta:
            await interaction.response.edit_message(content=f"❌ {self.usuario_destino.mention} no tiene suficiente dinero para aceptar el duelo.", view=None)
            self.stop()
            return

        ganador_id = random.choice([self.uid_origen, self.uid_destino])
        perdedor_id = self.uid_destino if ganador_id == self.uid_origen else self.uid_origen

        await usuarios_col.update_one({"_id": ganador_id}, {"$inc": {"dinero": self.apuesta}})
        await usuarios_col.update_one({"_id": perdedor_id}, {"$inc": {"dinero": -self.apuesta}})

        ganador_member = self.interaction.user if ganador_id == self.uid_origen else self.usuario_destino

        for child in self.children:
            child.disabled = True

        # Desactiva el botón del mensaje original del reto
        await interaction.response.edit_message(view=self)
        
        # Envía un mensaje NUEVO anunciando al ganador
        await interaction.followup.send(
            f"🏁 **¡Duelo aceptado y finalizado!**\n🏆 El ganador de la carrera fue {ganador_member.mention}, llevándose un premio de **{self.apuesta}**."
        )
        self.stop()


# --- APUESTAS Y RIESGO ---

@bot.tree.command(name="suerte", description="Apuesta tu dinero a cara o cruz")
async def suerte(interaction: discord.Interaction, monto: int, eleccion: str):
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)
    u = await usuarios_col.find_one({"_id": uid})
    
    if monto <= 0 or u.get("dinero", 0) < monto:
        await interaction.response.send_message("❌ No tienes suficiente dinero en mano para esa apuesta.", ephemeral=True)
        return
        
    eleccion = eleccion.lower()
    if eleccion not in ["cara", "cruz"]:
        await interaction.response.send_message("❌ Debes elegir entre 'cara' o 'cruz'.", ephemeral=True)
        return
        
    resultado = random.choice(["cara", "cruz"])
    if eleccion == resultado:
        await usuarios_col.update_one({"_id": uid}, {"$inc": {"dinero": monto}})
        await interaction.response.send_message(f"🪙 Salió **{resultado}**. ¡Ganaste la apuesta y obtuviste **{monto}**!")
    else:
        await usuarios_col.update_one({"_id": uid}, {"$inc": {"dinero": -monto}})
        await interaction.response.send_message(f"🪙 Salió **{resultado}**. Perdiste la apuesta y cediste **{monto}**.")

@bot.tree.command(name="cohete_crash", description="Sube al cohete y retírate antes de que explote")
async def cohete_crash(interaction: discord.Interaction, apuesta: int):
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)
    u = await usuarios_col.find_one({"_id": uid})
    
    if apuesta <= 0 or u.get("dinero", 0) < apuesta:
        await interaction.response.send_message("❌ No tienes suficiente dinero en mano para apostar en el cohete.", ephemeral=True)
        return

    await usuarios_col.update_one({"_id": uid}, {"$inc": {"dinero": -apuesta}})

    view = CoheteView(interaction, uid, apuesta)
    punto_crash = round(random.uniform(1.2, 5.5), 2)
    
    await interaction.response.send_message(
        f"🚀 **¡El cohete ha despegado!**\n📊 Multiplicador actual: `1.00x`\n💰 Ganancia estimada: `0`\n\n*¡Pulsa el botón antes de que explote!*",
        view=view
    )
    view.mensaje_obj = await interaction.original_response()

    while not view.parado and view.multiplicador < punto_crash:
        await asyncio.sleep(1.5)
        if view.parado:
            break
            
        view.multiplicador = round(view.multiplicador + random.uniform(0.1, 0.4), 2)
        
        if view.multiplicador >= punto_crash:
            view.parado = True
            for child in view.children:
                child.disabled = True
            try:
                await view.mensaje_obj.edit(
                    content=f"💥 **¡BOOM! El cohete explotó en {punto_crash}x**\n😭 Te arriesgaste demasiado y perdiste tu apuesta de **{apuesta}**.",
                    view=view
                )
            except:
                pass
            view.stop()
            return

        ganancia_actual = int(apuesta * view.multiplicador)
        try:
            await view.mensaje_obj.edit(
                content=f"🚀 **¡El cohete sigue subiendo!**\n📊 Multiplicador actual: `{view.multiplicador:.2f}x`\n💰 Ganancia estimada: `{ganancia_actual}`\n\n*¡Decide cuándo retirarte!*",
                view=view
            )
        except:
            break

@bot.tree.command(name="carrera", description="Reta a una carrera de velocidad contra Z6 o contra otro usuario")
async def carrera(interaction: discord.Interaction, apuesta: int, usuario_opcional: discord.Member = None):
    uid_origen = str(interaction.user.id)
    await asegurar_usuario(uid_origen)
    u_origen = await usuarios_col.find_one({"_id": uid_origen})
    
    if apuesta <= 0 or u_origen.get("dinero", 0) < apuesta:
        await interaction.response.send_message("❌ No tienes suficiente dinero en mano para cubrir esta apuesta.", ephemeral=True)
        return
        
    # --- MODO: JUGADOR VS Z6 ---
    if not usuario_opcional:
        velocidad_jugador = random.randint(150, 300)
        velocidad_z6 = random.randint(150, 300)
        
        if velocidad_jugador == velocidad_z6:
            velocidad_jugador += 5

        if velocidad_jugador > velocidad_z6:
            await usuarios_col.update_one({"_id": uid_origen}, {"$inc": {"dinero": apuesta}})
            await interaction.response.send_message(
                f"🏁 **¡Carrera contra Z6!**\n"
                f"🏎️ Tu velocidad: **{velocidad_jugador} km/h**\n"
                f"🤖 Velocidad de Z6: **{velocidad_z6} km/h**\n\n"
                f"🏆 **¡Has ganado la carrera!** Te llevaste un premio de **{apuesta}**."
            )
        else:
            await usuarios_col.update_one({"_id": uid_origen}, {"$inc": {"dinero": -apuesta}})
            await interaction.response.send_message(
                f"🏁 **¡Carrera contra Z6!**\n"
                f"🏎️ Tu velocidad: **{velocidad_jugador} km/h**\n"
                f"🤖 Velocidad de Z6: **{velocidad_z6} km/h**\n\n"
                f"💥 **¡Has perdido!** Z6 te superó y perdiste **{apuesta}**."
            )
        return

    # --- MODO: JUGADOR VS JUGADOR (Con botón de aceptar y mensaje nuevo al terminar) ---
    uid_destino = str(usuario_opcional.id)
    if uid_origen == uid_destino:
        await interaction.response.send_message("❌ No puedes competir contra ti mismo.", ephemeral=True)
        return
        
    await asegurar_usuario(uid_destino)
    u_destino = await usuarios_col.find_one({"_id": uid_destino})
    
    if u_destino.get("dinero", 0) < apuesta:
        await interaction.response.send_message(f"❌ {usuario_opcional.mention} no tiene suficiente dinero para igualar la apuesta.", ephemeral=True)
        return

    view = DueloView(interaction, uid_origen, uid_destino, apuesta, usuario_opcional)
    await interaction.response.send_message(
        f"🏁 {usuario_opcional.mention}, {interaction.user.mention} te ha retado a una carrera por una apuesta de **{apuesta}**.\n*Pulsa el botón de abajo para aceptar el duelo:*",
        view=view
        )

    # --- CLASES PARA EL SISTEMA DE MINERÍA Y TRADE ---

class MinarView(discord.ui.View):
    def __init__(self, uid: str, mineral_nombre: str, valor_venta: int):
        super().__init__(timeout=60)
        self.uid = uid
        self.mineral_nombre = mineral_nombre
        self.valor_venta = valor_venta

    @discord.ui.button(label="💰 Vender", style=discord.ButtonStyle.green)
    async def vender(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("❌ Esta mena no es tuya.", ephemeral=True)
            return

        await usuarios_col.update_one(
            {"_id": self.uid},
            {"$inc": {"dinero": self.valor_venta}}
        )

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=f"💰 **¡Venta exitosa!** Vendiste **{self.mineral_nombre}** por **{self.valor_venta}** de dinero.",
            view=self
        )
        self.stop()

    @discord.ui.button(label="🛡️ Mantener", style=discord.ButtonStyle.blurple)
    async def mantener(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("❌ Esta mena no es tuya.", ephemeral=True)
            return

        await usuarios_col.update_one(
            {"_id": self.uid},
            {"$inc": {f"inventario_minerales.{self.mineral_nombre}": 1}}
        )

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=f"🛡️ **¡Guardado!** Has guardado **{self.mineral_nombre}** en tu colección de minerales.",
            view=self
        )
        self.stop()


class MenuElegirMineralPropio(discord.ui.Select):
    def __init__(self, inventario_origen: dict, uid_origen: str, uid_destino: str, usuario_destino: discord.Member):
        options = []
        for mineral, cantidad in inventario_origen.items():
            if cantidad > 0:
                options.append(discord.SelectOption(label=mineral, description=f"Tienes: {cantidad} unidades", emoji="💎"))
        
        if not options:
            options.append(discord.SelectOption(label="No tienes minerales", description="Vacío", value="none"))

        super().__init__(placeholder="Selecciona el mineral que quieres ofrecer...", min_values=1, max_values=1, options=options)
        self.uid_origen = uid_origen
        self.uid_destino = uid_destino
        self.usuario_destino = usuario_destino

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.uid_origen:
            await interaction.response.send_message("❌ Este menú no es para ti.", ephemeral=True)
            return

        mineral_elegido = self.values[0]
        if mineral_elegido == "none":
            await interaction.response.send_message("❌ No tienes minerales para tradear.", ephemeral=True)
            return

        u_destino = await usuarios_col.find_one({"_id": self.uid_destino})
        inv_destino = u_destino.get("inventario_minerales", {})
        
        view_destino = ViewElegirMineralDestino(self.uid_origen, self.uid_destino, self.usuario_destino, mineral_elegido, inv_destino)
        await interaction.response.edit_message(
            content=f"🤝 {interaction.user.mention} ofreció **{mineral_elegido}**.\nAhora {self.usuario_destino.mention}, selecciona en el menú de abajo qué mineral deseas dar a cambio:",
            view=view_destino
        )


class ViewElegirMineralPropio(discord.ui.View):
    def __init__(self, inv_origen: dict, uid_origen: str, uid_destino: str, usuario_destino: discord.Member):
        super().__init__(timeout=60)
        self.add_item(MenuElegirMineralPropio(inv_origen, uid_origen, uid_destino, usuario_destino))


class MenuElegirMineralDestino(discord.ui.Select):
    def __init__(self, uid_origen: str, uid_destino: str, usuario_destino: discord.Member, mineral_ofrecido: str, inv_destino: dict):
        options = []
        for mineral, cantidad in inv_destino.items():
            if cantidad > 0:
                options.append(discord.SelectOption(label=mineral, description=f"Tienes: {cantidad} unidades", emoji="🛡️"))
        
        if not options:
            options.append(discord.SelectOption(label="No tienes minerales", description="Vacío", value="none"))

        super().__init__(placeholder="Selecciona el mineral que darás a cambio...", min_values=1, max_values=1, options=options)
        self.uid_origen = uid_origen
        self.uid_destino = uid_destino
        self.usuario_destino = usuario_destino
        self.mineral_ofrecido = mineral_ofrecido

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.uid_destino:
            await interaction.response.send_message("❌ Este menú no es para ti.", ephemeral=True)
            return

        mineral_cambio = self.values[0]
        if mineral_cambio == "none":
            await interaction.response.send_message("❌ No tienes minerales para ofrecer a cambio.", ephemeral=True)
            return

        view_confirmar = ViewConfirmarTrade(self.uid_origen, self.uid_destino, self.mineral_ofrecido, mineral_cambio)
        
        try:
            user_orig_obj = await interaction.client.fetch_user(int(self.uid_origen))
            mencion_orig = user_orig_obj.mention
        except:
            mencion_orig = "Usuario 1"

        await interaction.response.edit_message(
            content=f"⚖️ **Resumen del Intercambio Propuesto:**\n\n"
                    f"• {mencion_orig} da: **{self.mineral_ofrecido}**\n"
                    f"• {self.usuario_destino.mention} da: **{mineral_cambio}**\n\n"
                    f"*Ambos usuarios deben presionar aceptar para completar el trade:*",
            view=view_confirmar
        )


class ViewElegirMineralDestino(discord.ui.View):
    def __init__(self, uid_origen: str, uid_destino: str, usuario_destino: discord.Member, mineral_ofrecido: str, inv_destino: dict):
        super().__init__(timeout=60)
        self.add_item(MenuElegirMineralDestino(uid_origen, uid_destino, usuario_destino, mineral_ofrecido, inv_destino))


class ViewConfirmarTrade(discord.ui.View):
    def __init__(self, uid_origen: str, uid_destino: str, mineral1: str, mineral2: str):
        super().__init__(timeout=60)
        self.uid_origen = uid_origen
        self.uid_destino = uid_destino
        self.mineral1 = mineral1
        self.mineral2 = mineral2
        self.aceptaron = set()

    @discord.ui.button(label="✅ Aceptar Trade", style=discord.ButtonStyle.green)
    async def aceptar(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if uid not in [self.uid_origen, self.uid_destino]:
            await interaction.response.send_message("❌ No participas en este intercambio.", ephemeral=True)
            return

        self.aceptaron.add(uid)

        if len(self.aceptaron) < 2:
            await interaction.response.send_message(f"👍 Has aceptado el trade. Falta que el otro usuario acepte.", ephemeral=True)
            return

        await asegurar_usuario(self.uid_origen)
        await asegurar_usuario(self.uid_destino)

        await usuarios_col.update_one({"_id": self.uid_origen}, {"$inc": {f"inventario_minerales.{self.mineral1}": -1, f"inventario_minerales.{self.mineral2}": 1}})
        await usuarios_col.update_one({"_id": self.uid_destino}, {"$inc": {f"inventario_minerales.{self.mineral2}": -1, f"inventario_minerales.{self.mineral1}": 1}})

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content="🎉 **¡Intercambio completado con éxito!**",
            view=self
        )

        valores_venta = {"Carbón": 50, "Hierro": 120, "Oro": 300, "Diamante": 750, "Netherita": 1500}
        
        val1 = valores_venta.get(self.mineral2, 100)
        val2 = valores_venta.get(self.mineral1, 100)

        try:
            user1 = await interaction.client.fetch_user(int(self.uid_origen))
            view_ephemeral_1 = MinarView(self.uid_origen, self.mineral2, val1)
            await user1.send(f"📦 Has recibido **{self.mineral2}** por el trade. ¿Qué deseas hacer?", view=view_ephemeral_1)
        except:
            pass

        try:
            user2 = await interaction.client.fetch_user(int(self.uid_destino))
            view_ephemeral_2 = MinarView(self.uid_destino, self.mineral1, val2)
            await user2.send(f"📦 Has recibido **{self.mineral1}** por el trade. ¿Qué deseas hacer?", view=view_ephemeral_2)
        except:
            pass

        self.stop()

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.red)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if uid not in [self.uid_origen, self.uid_destino]:
            await interaction.response.send_message("❌ No participas en este intercambio.", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content="❌ **Intercambio cancelado** por uno de los usuarios.",
            view=self
        )
        self.stop()


# --- MINERÍA Y COLECCIÓN ---

@bot.tree.command(name="minar", description="Explora las profundidades en busca de valiosos minerales")
async def minar(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)

    lista_minerales = [
        ("Carbón", 50),
        ("Hierro", 120),
        ("Oro", 300),
        ("Diamante", 750),
        ("Netherita", 1500)
    ]
    
    mineral_nombre, valor_venta = random.choice(lista_minerales)
    
    view = MinarView(uid, mineral_nombre, valor_venta)
    await interaction.response.send_message(
        f"⛏️ ¡Has minado con éxito y encontrado: **{mineral_nombre}**!\n💵 Valor de venta rápida: **{valor_venta}**\n\n*¿Qué deseas hacer con este mineral?*",
        view=view
    )

@bot.tree.command(name="indice_minerales", description="Revisa tus minerales guardados en la colección (o la de otro usuario)")
async def indice_minerales(interaction: discord.Interaction, usuario: discord.Member = None):
    target = usuario or interaction.user
    uid = str(target.id)
    await asegurar_usuario(uid)

    u = await usuarios_col.find_one({"_id": uid})
    inventario = u.get("inventario_minerales", {})

    if not inventario or not any(cant > 0 for cant in inventario.values()):
        await interaction.response.send_message(f"🎒 {target.mention} aún no tiene ningún mineral guardado en su colección.")
        return

    texto = f"🎒 **Colección de Minerales de {target.name}:**\n\n"
    for mineral, cantidad in inventario.items():
        if cantidad > 0:
            texto += f"• **{mineral}**: x{cantidad}\n"

    await interaction.response.send_message(texto)

@bot.tree.command(name="tradear_minerales", description="Inicia un intercambio interactivo de minerales con otro usuario")
async def tradear_minerales(interaction: discord.Interaction, usuario: discord.Member):
    uid_origen = str(interaction.user.id)
    uid_destino = str(usuario.id)

    if uid_origen == uid_destino:
        await interaction.response.send_message("❌ No puedes tradear contigo mismo.", ephemeral=True)
        return

    await asegurar_usuario(uid_origen)
    await asegurar_usuario(uid_destino)

    u_origen = await usuarios_col.find_one({"_id": uid_origen})
    inv_origen = u_origen.get("inventario_minerales", {})

    if not any(cant > 0 for cant in inv_origen.values()):
        await interaction.response.send_message("❌ No tienes ningún mineral en tu inventario para iniciar un trade.", ephemeral=True)
        return

    view = ViewElegirMineralPropio(inv_origen, uid_origen, uid_destino, usuario)
    await interaction.response.send_message(
        f"🤝 {interaction.user.mention} ha iniciado una solicitud de intercambio con {usuario.mention}.\n*Selecciona en el menú de abajo qué mineral deseas ofrecer:*",
        view=view,
        ephemeral=True
                      )
    # --- CLASE PARA EL BOTÓN DE DUELO DE MASCOTAS ENTRE JUGADORES ---
class DueloMascotaView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, uid_origen: str, uid_destino: str, apuesta: int, usuario_destino: discord.Member, nivel_origen: int, emoji_origen: str, nombre_origen: str):
        super().__init__(timeout=60)
        self.interaction = interaction
        self.uid_origen = uid_origen
        self.uid_destino = uid_destino
        self.apuesta = apuesta
        self.usuario_destino = usuario_destino
        self.nivel_origen = nivel_origen
        self.emoji_origen = emoji_origen
        self.nombre_origen = nombre_origen

    @discord.ui.button(label="Aceptar duelo de mascotas", style=discord.ButtonStyle.green)
    async def aceptar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.uid_destino:
            await interaction.response.send_message("❌ Este duelo de mascotas no es para ti.", ephemeral=True)
            return

        await asegurar_usuario(self.uid_origen)
        await asegurar_usuario(self.uid_destino)
        
        u_origen = await usuarios_col.find_one({"_id": self.uid_origen})
        u_destino = await usuarios_col.find_one({"_id": self.uid_destino})

        # Verificar que el retador siga teniendo la mascota y dinero
        mascota_orig = u_origen.get("mascota")
        if not mascota_orig or u_origen.get("dinero", 0) < self.apuesta:
            await interaction.response.edit_message(content="❌ El creador del duelo ya no tiene suficiente dinero o su mascota ya no está disponible.", view=None)
            self.stop()
            return

        # Verificar que el rival tenga mascota y dinero
        mascota_dest = u_destino.get("mascota")
        if not mascota_dest:
            await interaction.response.edit_message(content=f"❌ {self.usuario_destino.mention} ya no tiene ninguna mascota registrada para competir.", view=None)
            self.stop()
            return

        if u_destino.get("dinero", 0) < self.apuesta:
            await interaction.response.edit_message(content=f"❌ {self.usuario_destino.mention} no tiene suficiente dinero para aceptar el duelo.", view=None)
            self.stop()
            return

        # Calcular velocidades basadas en los niveles respectivos de cada mascota
        nivel_destino = mascota_dest.get("nivel", 1)
        bonus_orig = self.nivel_origen * 8
        bonus_dest = nivel_destino * 8

        vel_orig = random.randint(140 + bonus_orig, 240 + bonus_orig)
        vel_dest = random.randint(140 + bonus_dest, 240 + bonus_dest)

        if vel_orig == vel_dest:
            vel_orig += 5

        ganador_id = self.uid_origen if vel_orig > vel_dest else self.uid_destino
        perdedor_id = self.uid_destino if ganador_id == self.uid_origen else self.uid_origen

        await usuarios_col.update_one({"_id": ganador_id}, {"$inc": {"dinero": self.apuesta}})
        await usuarios_col.update_one({"_id": perdedor_id}, {"$inc": {"dinero": -self.apuesta}})

        ganador_member = self.interaction.user if ganador_id == self.uid_origen else self.usuario_destino

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(view=self)
        
        await interaction.followup.send(
            f"🏁 **¡Duelo de Mascotas Finalizado!**\n"
            f"🐾 Mascota de {self.interaction.user.name} (Nv. {self.nivel_origen}): **{vel_orig} km/h**\n"
            f"🐾 Mascota de {self.usuario_destino.name} (Nv. {nivel_destino}): **{vel_dest} km/h**\n\n"
            f"🏆 El ganador de la carrera fue {ganador_member.mention}, llevándose un premio de **{self.apuesta}**."
        )
        self.stop()


# --- SISTEMA DE MASCOTAS ---

@bot.tree.command(name="comprar_mascota", description="Crea y personaliza tu propia mascota por 8,000 de dinero")
async def comprar_mascota(interaction: discord.Interaction, nombre: str, emoji: str):
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)
    
    u = await usuarios_col.find_one({"_id": uid})
    
    if u.get("mascota"):
        await interaction.response.send_message("❌ Ya cuentas con una mascota registrada. ¡Cuídala bien!", ephemeral=True)
        return

    costo = 8000
    if u.get("dinero", 0) < costo:
        await interaction.response.send_message(f"❌ No tienes suficiente dinero. Comprar una mascota cuesta **{costo}**.", ephemeral=True)
        return

    await usuarios_col.update_one(
        {"_id": uid},
        {"$inc": {"dinero": -costo}}
    )

    datos_mascota = {
        "nombre": nombre,
        "emoji": emoji,
        "nivel": 1
    }

    await usuarios_col.update_one(
        {"_id": uid},
        {"$set": {"mascota": datos_mascota}}
    )

    await interaction.response.send_message(
        f"🐾 **¡Felicidades!** Has comprado a tu compañero por **{costo}** de dinero:\n\n"
        f"• **Mascota:** {emoji} **{nombre}**\n"
        f"• **Nivel:** `1`\n\n*¡Usa /ver_mascota para ver su estado actual!*"
    )

@bot.tree.command(name="mejorar_mascota", description="Sube de nivel a tu compañero para potenciar sus estadísticas")
async def mejorar_mascota(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    await asegurar_usuario(uid)
    
    u = await usuarios_col.find_one({"_id": uid})
    mascota = u.get("mascota")
    
    if not mascota:
        await interaction.response.send_message("❌ No tienes ninguna mascota comprada. Usa `/comprar_mascota` primero.", ephemeral=True)
        return

    nivel_actual = mascota.get("nivel", 1)
    costo_mejora = nivel_actual * 1000

    if u.get("dinero", 0) < costo_mejora:
        await interaction.response.send_message(f"❌ No tienes suficiente dinero. Necesitas **{costo_mejora}** para subir de nivel a tu mascota.", ephemeral=True)
        return

    await usuarios_col.update_one(
        {"_id": uid},
        {
            "$inc": {
                "dinero": -costo_mejora,
                "mascota.nivel": 1
            }
        }
    )

    nuevo_nivel = nivel_actual + 1
    await interaction.response.send_message(
        f"⭐ **¡Mejora exitosa!** Tu mascota **{mascota.get('nombre')}** ha subido al **nivel {nuevo_nivel}** 🎉\n*(Costo de mejora pagado: {costo_mejora} de dinero)*"
    )

@bot.tree.command(name="ver_mascota", description="Revisa el estado, nivel y nombre de tu mascota actual")
async def ver_mascota(interaction: discord.Interaction, usuario: discord.Member = None):
    target = usuario or interaction.user
    uid = str(target.id)
    await asegurar_usuario(uid)

    u = await usuarios_col.find_one({"_id": uid})
    mascota = u.get("mascota")

    if not mascota:
        await interaction.response.send_message(
            f"🐾 **Estado de Mascota de {target.name}:**\n\n"
            f"• **Mascota:** 🔒 **Predeterminado**\n"
            f"• **Nivel:** 🔒 `Bloqueado`\n\n"
            f"*Este usuario aún no ha adoptado ninguna mascota con `/comprar_mascota`.*"
        )
        return

    await interaction.response.send_message(
        f"🐾 **Estado de Mascota de {target.name}:**\n\n"
        f"• **Mascota:** {mascota.get('emoji', '🐶')} **{mascota.get('nombre')}**\n"
        f"• **Nivel:** ⭐ `{mascota.get('nivel', 1)}`"
    )

@bot.tree.command(name="carrera_mascota", description="Pon a correr a tu mascota contra Z6 o reta a otro usuario con botones interactivos")
async def carrera_mascota(interaction: discord.Interaction, apuesta: int, usuario_opcional: discord.Member = None):
    uid_origen = str(interaction.user.id)
    await asegurar_usuario(uid_origen)
    
    u_origen = await usuarios_col.find_one({"_id": uid_origen})
    mascota_origen = u_origen.get("mascota")
    
    if not mascota_origen:
        await interaction.response.send_message("❌ Necesitas comprar una mascota con `/comprar_mascota` (8,000 de dinero) para participar en carreras de mascotas.", ephemeral=True)
        return

    if apuesta <= 0 or u_origen.get("dinero", 0) < apuesta:
        await interaction.response.send_message("❌ No tienes suficiente dinero en mano para cubrir esta apuesta.", ephemeral=True)
        return

    nivel_origen = mascota_origen.get("nivel", 1)
    emoji_origen = mascota_origen.get("emoji", "🐶")
    nombre_origen = mascota_origen.get("nombre", "Mascota")

    # --- MODO: JUGADOR VS Z6 ---
    if not usuario_opcional:
        bonus_minimo = nivel_origen * 8
        bonus_maximo = nivel_origen * 12
        
        velocidad_mascota = random.randint(140 + bonus_minimo, 240 + bonus_maximo)
        velocidad_z6 = random.randint(150, 250)

        if velocidad_mascota == velocidad_z6:
            velocidad_mascota += 5

        if velocidad_mascota > velocidad_z6:
            premio = int(apuesta * (1 + (nivel_origen * 0.15)))
            await usuarios_col.update_one({"_id": uid_origen}, {"$inc": {"dinero": premio - apuesta}})
            
            await interaction.response.send_message(
                f"🏁 **¡Carrera de Mascotas contra Z6 ({emoji_origen} {nombre_origen})!**\n"
                f"🐾 Velocidad de tu mascota (Nv. {nivel_origen}): **{velocidad_mascota} km/h**\n"
                f"🤖 Velocidad de Z6: **{velocidad_z6} km/h**\n\n"
                f"🏆 **¡Victoria gracias a tu nivel!** Tu mascota se lució y ganaste un premio de **{premio}**."
            )
        else:
            await usuarios_col.update_one({"_id": uid_origen}, {"$inc": {"dinero": -apuesta}})
            await interaction.response.send_message(
                f"🏁 **¡Carrera de Mascotas contra Z6 ({emoji_origen} {nombre_origen})!**\n"
                f"🐾 Velocidad de tu mascota (Nv. {nivel_origen}): **{velocidad_mascota} km/h**\n"
                f"🤖 Velocidad de Z6: **{velocidad_z6} km/h**\n\n"
                f"💥 **¡Derrota!** A pesar de su experiencia, Z6 fue más rápido y perdiste **{apuesta}**."
            )
        return

    # --- MODO: JUGADOR VS JUGADOR (Con botón interactivo de aceptar) ---
    uid_destino = str(usuario_opcional.id)
    if uid_origen == uid_destino:
        await interaction.response.send_message("❌ No puedes competir contra ti mismo.", ephemeral=True)
        return
        
    await asegurar_usuario(uid_destino)
    u_destino = await usuarios_col.find_one({"_id": uid_destino})
    
    mascota_destino = u_destino.get("mascota")
    if not mascota_destino:
        await interaction.response.send_message(f"❌ {usuario_opcional.mention} no tiene ninguna mascota comprada para aceptar el duelo.", ephemeral=True)
        return

    if u_destino.get("dinero", 0) < apuesta:
        await interaction.response.send_message(f"❌ {usuario_opcional.mention} no tiene suficiente dinero para igualar la apuesta.", ephemeral=True)
        return

    view = DueloMascotaView(interaction, uid_origen, uid_destino, apuesta, usuario_opcional, nivel_origen, emoji_origen, nombre_origen)
    await interaction.response.send_message(
        f"🏁 {usuario_opcional.mention}, {interaction.user.mention} te ha retado a una carrera de mascotas con **{emoji_origen} {nombre_origen}** por una apuesta de **{apuesta}**.\n*Pulsa el botón de abajo para aceptar el duelo:*",
        view=view
        )

    # --- LISTA DE DUEÑOS AUTORIZADOS ---
DUENOS_IDS = [
    1439675836746829986,
    1209982260892409920,
    1491476806203740373
]

def es_dueno(interaction: discord.Interaction) -> bool:
    return interaction.user.id in DUENOS_IDS

async def asegurar_usuario(uid: str):
    user = await usuarios_col.find_one({"_id": uid})
    if not user:
        await usuarios_col.insert_one({
            "_id": uid,
            "dinero": 1000,
            "inventario_minerales": {},
            "mascota": None
        })


# --- CLASE PARA EL BOTÓN DE CLAIM DEL SORTEO (Con caducidad automática) ---
class SorteoClaimView(discord.ui.View):
    def __init__(self, ganador_id: int, premio: str, tiempo_claim: int):
        super().__init__(timeout=tiempo_claim)
        self.ganador_id = ganador_id
        self.premio = premio
        self.reclamado = False

    @discord.ui.button(label="🎉 Claim Premio", style=discord.ButtonStyle.green)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ganador_id:
            await interaction.response.send_message("❌ Este botón de reclamación no es para ti.", ephemeral=True)
            return

        if self.reclamado:
            await interaction.response.send_message("⚠️ Este premio ya ha sido reclamado.", ephemeral=True)
            return

        self.reclamado = True
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"🎉 ¡{interaction.user.mention} ha reclamado exitosamente su premio: **{self.premio}**!")
        self.stop()

    async def on_timeout(self):
        if not self.reclamado:
            for child in self.children:
                child.disabled = True
            try:
                if self.message:
                    await self.message.edit(content="⏰ **El tiempo para reclamar el premio ha expirado.** El ganador no lo reclamó a tiempo.", view=self)
            except:
                pass


# --- CLASE PARA PARTICIPAR EN EL SORTEO ---
class SorteoParticiparView(discord.ui.View):
    def __init__(self, autor_id: int, premio: str, tiempo_segundos: int, tiempo_reroll: int, cantidad_reroll: int, tiempo_claim: int, imagen_url: str = None):
        super().__init__(timeout=tiempo_segundos)
        self.participantes = set()
        self.premio = premio
        self.tiempo_reroll = tiempo_reroll
        self.cantidad_reroll = cantidad_reroll
        self.tiempo_claim = tiempo_claim
        self.imagen_url = imagen_url

    @discord.ui.button(label="🎁 Participar en el Sorteo", style=discord.ButtonStyle.blurple)
    async def participar(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid in self.participantes:
            await interaction.response.send_message("⚠️ Ya estás participando en este sorteo.", ephemeral=True)
            return

        self.participantes.add(uid)
        await interaction.response.send_message("✅ ¡Te has inscrito correctamente en el sorteo!", ephemeral=True)


# --- FUNCIÓN AUXILIAR PARA CONVERTIR TIEMPO (ej. 10s, 5m, 2h) ---
def convertir_tiempo(tiempo_str: str) -> int:
    tiempo_str = tiempo_str.lower().strip()
    total_segundos = 0
    
    numero = ""
    for char in tiempo_str:
        if char.isdigit():
            numero += char
        else:
            if not numero:
                continue
            val = int(numero)
            if char == 's':
                total_segundos += val
            elif char == 'm':
                total_segundos += val * 60
            elif char == 'h':
                total_segundos += val * 3600
            elif char == 'd':
                total_segundos += val * 86400
            numero = ""
            
    return total_segundos if total_segundos > 0 else 60


# --- EVENTOS Y ADMINISTRACIÓN (SOLO DUEÑOS) ---

@bot.tree.command(name="sorteo_economia", description="Crea un sorteo interactivo avanzado (Solo Dueños)")
async def sorteo_economia(
    interaction: discord.Interaction, 
    premio: str, 
    tiempo: str, 
    tiempo_reroll: str, 
    cantidad_reroll: int, 
    tiempo_claim: str, 
    imagen: str = None
):
    if not es_dueno(interaction):
        await interaction.response.send_message("❌ No tienes permisos para usar este comando. Es exclusivo para los dueños del bot.", ephemeral=True)
        return

    segundos_duracion = convertir_tiempo(tiempo)
    segundos_reroll = convertir_tiempo(tiempo_reroll)
    segundos_claim = convertir_tiempo(tiempo_claim)

    view = SorteoParticiparView(
        interaction.user.id, 
        premio, 
        segundos_duracion, 
        segundos_reroll, 
        cantidad_reroll, 
        segundos_claim, 
        imagen
    )

    embed = discord.Embed(
        title="🎁 ¡NUEVO SORTEO DE ECONOMÍA! 🎁",
        description=f"• **Premio:** {premio}\n• **Duración:** {tiempo}\n• **Tiempo de Reroll:** {tiempo_reroll}\n• **Intentos de Reroll:** {cantidad_reroll}\n• **Tiempo de Claim:** {tiempo_claim}\n\n*¡Haz clic en el botón de abajo para participar!*",
        color=discord.Color.gold()
    )
    if imagen:
        embed.set_image(url=imagen)

    await interaction.response.send_message(embed=embed, view=view)
    mensaje_sorteo = await interaction.original_response()

    await asyncio.sleep(segundos_duracion)

    for child in view.children:
        child.disabled = True
    try:
        await mensaje_sorteo.edit(view=view)
    except:
        pass

    participantes_lista = list(view.participantes)
    if not participantes_lista:
        await interaction.followup.send("❌ El sorteo ha terminado, pero nadie participó.")
        return

    ganador_id = random.choice(participantes_lista)
    ganador_member = interaction.guild.get_member(ganador_id) or await interaction.client.fetch_user(ganador_id)

    claim_view = SorteoClaimView(ganador_id, premio, segundos_claim)
    mensaje_claim = await interaction.followup.send(
        f"🎊 **¡Tenemos un ganador para el sorteo de {premio}!**\n"
        f"🏆 El ganador provisional es {ganador_member.mention}.\n"
        f"⏰ Tienes **{tiempo_claim}** para presionar el botón de abajo y reclamar tu premio:",
        view=claim_view
    )
    claim_view.message = mensaje_claim


@bot.tree.command(name="dar", description="Da dinero a un usuario (Solo Dueños)")
async def dar(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    if not es_dueno(interaction):
        await interaction.response.send_message("❌ Comando exclusivo para dueños.", ephemeral=True)
        return

    if cantidad <= 0:
        await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
        return

    uid = str(usuario.id)
    await asegurar_usuario(uid)

    await usuarios_col.update_one({"_id": uid}, {"$inc": {"dinero": cantidad}})
    await interaction.response.send_message(f"✅ Se han entregado **{cantidad}** de dinero a {usuario.mention}.")


@bot.tree.command(name="quitar", description="Retira dinero a un usuario, acepta 'all' (Solo Dueños)")
async def quitar(interaction: discord.Interaction, usuario: discord.Member, cantidad: str):
    if not es_dueno(interaction):
        await interaction.response.send_message("❌ Comando exclusivo para dueños.", ephemeral=True)
        return

    uid = str(usuario.id)
    await asegurar_usuario(uid)
    u = await usuarios_col.find_one({"_id": uid})

    if cantidad.lower() == "all":
        retirado = u.get("dinero", 0)
        await usuarios_col.update_one({"_id": uid}, {"$set": {"dinero": 0}})
        await interaction.response.send_message(f"✅ Se ha retirado todo el dinero (**{retirado}**) a {usuario.mention}.")
        return

    try:
        monto = int(cantidad)
    except ValueError:
        await interaction.response.send_message("❌ Debes ingresar una cantidad válida o la palabra 'all'.", ephemeral=True)
        return

    if monto <= 0:
        await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
        return

    dinero_actual = u.get("dinero", 0)
    a_retirar = min(monto, dinero_actual)

    await usuarios_col.update_one({"_id": uid}, {"$inc": {"dinero": -a_retirar}})
    await interaction.response.send_message(f"✅ Se han retirado **{a_retirar}** de dinero a {usuario.mention}.")


@bot.tree.command(name="reset-eco", description="Resetea la economía completa del servidor (Solo Dueños)")
async def reset_eco(interaction: discord.Interaction):
    if not es_dueno(interaction):
        await interaction.response.send_message("❌ Comando exclusivo para dueños.", ephemeral=True)
        return

    await usuarios_col.update_many({}, {"$set": {"dinero": 0, "inventario_minerales": {}, "mascota": None}})
    await interaction.response.send_message("⚠️ **¡Economía reseteada!** Se han vaciado los saldos, inventarios y mascotas de todos los usuarios registrados.")

# Ejecución del bot con variables de entorno
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ Error: No se encontró la variable DISCORD_TOKEN en las variables de entorno.")
        
                                                    
