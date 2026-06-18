"""
============================================================
SMART HOME HUB - TELEGRAM BOT
Versión 7.0 - Con botones inline + ReplyKeyboard
============================================================
"""

import os
import logging
import asyncio
import tempfile
from dotenv import load_dotenv

load_dotenv()

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from mqtt_client import MqttClient
from auth import (
    is_authorized,
    add_authorized_user,
    get_authorized_count,
    authorized_only,
    AUTH_PASSWORD,
)
from nlp import parse_natural_command, get_command_examples
from keyboards import (
    get_main_keyboard,
    get_inline_modes_keyboard,
    get_inline_quick_keyboard,
    get_inline_info_keyboard,
    get_command_from_button_text,
)

# ============================================================
# VOZ OPCIONAL
# ============================================================
ENABLE_VOICE = os.getenv("ENABLE_VOICE", "true").lower() == "true"

if ENABLE_VOICE:
    try:
        from voice import transcribe_audio, preload_model
        _voice_status_msg = "✅ Módulo de voz cargado"
    except ImportError as e:
        ENABLE_VOICE = False
        _voice_status_msg = f"⚠️ Módulo de voz no disponible: {e}"
else:
    _voice_status_msg = "ℹ️ Voz deshabilitada por configuración"


# ============================================================
# CONFIGURACIÓN
# ============================================================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    raise ValueError("ERROR: TELEGRAM_BOT_TOKEN no encontrado en .env")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

mqtt_client = MqttClient()
bot_application = None
event_loop = None
subscribed_chat_ids = set()

STATE_INFO = {
    "NIGHT":   {"emoji": "🌙", "name": "Nocturno"},
    "DAY":     {"emoji": "☀️", "name": "Día"},
    "RELAX":   {"emoji": "😌", "name": "Relax"},
    "ALARM":   {"emoji": "🚨", "name": "Alarma"},
    "PARTY":   {"emoji": "🎉", "name": "Fiesta"},
    "STANDBY": {"emoji": "⏹", "name": "Standby"},
    "OFF":     {"emoji": "⭕", "name": "Apagado"},
}

COMMAND_INFO = {
    "N": {"emoji": "🌙", "name": "Nocturno"},
    "D": {"emoji": "☀️", "name": "Día"},
    "R": {"emoji": "😌", "name": "Relax"},
    "A": {"emoji": "🚨", "name": "Alarma"},
    "P": {"emoji": "🎉", "name": "Fiesta"},
    "S": {"emoji": "⏹", "name": "Standby"},
    "T": {"emoji": "🌡", "name": "Temperatura"},
}


# ============================================================
# CALLBACKS DE MQTT
# ============================================================

def on_ack_received(payload: str):
    logger.info(f"💬 ACK recibido: {payload}")
    info = STATE_INFO.get(payload.upper(), {"emoji": "✅", "name": payload})
    message = f"{info['emoji']} *{info['name']}* activado correctamente"
    _broadcast_message(message)


def on_temp_received(payload: str):
    logger.info(f"🌡 TEMP recibida: {payload}")
    message = f"🌡 Temperatura actual: *{payload} °C*"
    _broadcast_message(message)


def _broadcast_message(message: str):
    if not bot_application or not event_loop:
        return
    if not subscribed_chat_ids:
        return
    
    for chat_id in subscribed_chat_ids:
        try:
            asyncio.run_coroutine_threadsafe(
                _send_message_async(chat_id, message),
                event_loop
            )
        except Exception as e:
            logger.error(f"❌ Error enviando a {chat_id}: {e}")


async def _send_message_async(chat_id: int, message: str):
    try:
        await bot_application.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"❌ Error en send_message_async: {e}")


# ============================================================
# HELPER PARA EJECUTAR COMANDOS
# ============================================================

async def execute_command(update: Update, command: str, matched_phrase: str = None, source: str = "text"):
    subscribed_chat_ids.add(update.effective_chat.id)
    
    info = COMMAND_INFO.get(command, {"emoji": "✅", "name": command})
    emoji = info["emoji"]
    mode_name = info["name"]
    
    if not mqtt_client.connected:
        await update.message.reply_text(
            "⚠️ *MQTT desconectado*",
            parse_mode="Markdown"
        )
        return
    
    success = mqtt_client.publish_command(command)
    
    if not success:
        await update.message.reply_text("❌ Error al enviar el comando.")
        return
    
    if source == "voice":
        prefix = f"🎤 _Escuché:_ \"{matched_phrase}\"\n"
    elif source == "natural":
        prefix = f"💬 _Entendí:_ \"{matched_phrase}\"\n"
    else:
        prefix = ""
    
    if command == "T":
        msg = f"{prefix}🌡 Consultando temperatura..."
    else:
        msg = f"{prefix}{emoji} Enviando comando *{mode_name}*..."
    
    await update.message.reply_text(msg, parse_mode="Markdown")
    
    user = update.effective_user
    logger.info(f"[{source.upper()}] Comando '{command}' por {user.username}")


async def execute_command_from_callback(query, command: str, source: str = "callback"):
    """Versión que funciona con CallbackQuery"""
    subscribed_chat_ids.add(query.message.chat.id)
    
    info = COMMAND_INFO.get(command, {"emoji": "✅", "name": command})
    emoji = info["emoji"]
    mode_name = info["name"]
    
    if not mqtt_client.connected:
        await query.message.reply_text(
            "⚠️ *MQTT desconectado*",
            parse_mode="Markdown"
        )
        return
    
    success = mqtt_client.publish_command(command)
    
    if not success:
        await query.message.reply_text("❌ Error al enviar el comando.")
        return
    
    if command == "T":
        msg = f"🌡 Consultando temperatura..."
    else:
        msg = f"{emoji} Enviando comando *{mode_name}*..."
    
    await query.message.reply_text(msg, parse_mode="Markdown")
    
    user = query.from_user
    logger.info(f"[{source.upper()}] Comando '{command}' por {user.username}")


# ============================================================
# COMANDOS PÚBLICOS
# ============================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id
    
    if is_authorized(user_id):
        subscribed_chat_ids.add(update.effective_chat.id)
        voice_info = "  - Notas de voz 🎤" if ENABLE_VOICE else ""
        welcome_msg = (
            f"👋 Hola {user.first_name}!\n\n"
            f"🏠 Bienvenido al *Smart Home Hub*\n"
            f"✅ Estás autorizado para controlar el sistema.\n\n"
            f"📡 MQTT: {'🟢 Conectado' if mqtt_client.connected else '🔴 Desconectado'}\n\n"
            f"💬 Puedes usar:\n"
            f"  - Botones del menú ⬇️\n"
            f"  - Comandos slash (/help)\n"
            f"  - Frases naturales (\"prende la luz\")\n"
            f"{voice_info}"
        )
        
        await update.message.reply_text(
            welcome_msg,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
    else:
        welcome_msg = (
            f"👋 Hola {user.first_name}!\n\n"
            f"🚫 No estás autorizado para usar este bot.\n\n"
            f"Tu ID es: `{user_id}`\n\n"
            f"Si tienes el password, escribe:\n"
            f"`/auth <password>`"
        )
        await update.message.reply_text(welcome_msg, parse_mode="Markdown")
    
    logger.info(f"Usuario {user.username} ({user_id}) inició el bot")


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = (
        f"🆔 *Tu información:*\n\n"
        f"User ID: `{user.id}`\n"
        f"Username: @{user.username if user.username else 'N/A'}\n"
        f"Nombre: {user.first_name} {user.last_name or ''}\n\n"
        f"Estado: {'✅ Autorizado' if is_authorized(user.id) else '🚫 No autorizado'}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    
    if is_authorized(user.id):
        await update.message.reply_text(
            "✅ Ya estás autorizado.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()  # Mostrar teclado
        )
        return
    
    if not context.args:
        await update.message.reply_text("❌ Uso: `/auth <password>`", parse_mode="Markdown")
        return
    
    provided_password = context.args[0]
    
    if not AUTH_PASSWORD:
        await update.message.reply_text("❌ Auto-autorización deshabilitada.")
        return
    
    if provided_password == AUTH_PASSWORD:
        add_authorized_user(user.id)
        subscribed_chat_ids.add(update.effective_chat.id)
        await update.message.reply_text(
            "✅ *Autorización exitosa!*\n\nYa puedes usar todos los comandos.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()  # Mostrar teclado al autorizar
        )
        logger.info(f"✅ Usuario autorizado: {user.username} ({user.id})")
    else:
        await update.message.reply_text("❌ Password incorrecto.")


# ============================================================
# COMANDOS PROTEGIDOS
# ============================================================

@authorized_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if ENABLE_VOICE:
        voice_section = "*🎤 Notas de voz:*\nEnvía audios y los transcribiré!\n\n"
    else:
        voice_section = "*🎤 Notas de voz:*\n_(No disponibles en este servidor)_\n\n"
    
    help_msg = (
        "📋 *Comandos disponibles:*\n\n"
        "*🎛 Menú interactivo:*\n"
        "/menu - Mostrar botones interactivos\n\n"
        "*🎛 Control de modos:*\n"
        "🌙 /night - Modo nocturno (15%)\n"
        "☀️ /day - Modo día (100%)\n"
        "😌 /relax - Modo relax\n"
        "🚨 /alarm - Modo alarma\n"
        "🎉 /party - Modo fiesta\n"
        "⏹ /standby - Modo standby (5%)\n\n"
        "*📊 Información:*\n"
        "🌡 /temp - Consultar temperatura\n"
        "ℹ️ /status - Estado del sistema\n"
        "🆔 /myid - Ver tu ID\n\n"
        "*💬 Lenguaje natural:*\n"
        "Escribe frases como _\"prende la luz\"_, _\"modo nocturno\"_\n\n"
        f"{voice_section}"
        "*❓ Ayuda:*\n"
        "/help - Mostrar esta ayuda\n"
        "/examples - Ver ejemplos de lenguaje natural"
    )
    
    # Compatibilidad con CallbackQuery
    if hasattr(update, 'message') and update.message:
        await update.message.reply_text(help_msg, parse_mode="Markdown")
    else:
        await update.reply_text(help_msg, parse_mode="Markdown")


@authorized_only
async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el menú principal con botones inline."""
    await update.message.reply_text(
        "🎛 *Menú de control:*\n\nSelecciona un modo o acción:",
        parse_mode="Markdown",
        reply_markup=get_inline_modes_keyboard()
    )


@authorized_only
async def cmd_examples(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(get_command_examples(), parse_mode="Markdown")


@authorized_only
async def cmd_night(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await execute_command(update, "N", source="command")


@authorized_only
async def cmd_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await execute_command(update, "D", source="command")


@authorized_only
async def cmd_relax(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await execute_command(update, "R", source="command")


@authorized_only
async def cmd_alarm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await execute_command(update, "A", source="command")


@authorized_only
async def cmd_party(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await execute_command(update, "P", source="command")


@authorized_only
async def cmd_standby(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await execute_command(update, "S", source="command")


@authorized_only
async def cmd_temp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await execute_command(update, "T", source="command")


@authorized_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    voice_status = "🟢 Habilitada" if ENABLE_VOICE else "🔴 Deshabilitada"
    status_msg = (
        "📊 *Estado del sistema:*\n\n"
        f"🔌 Bot: 🟢 Online\n"
        f"📡 MQTT: {'🟢 Conectado' if mqtt_client.connected else '🔴 Desconectado'}\n"
        f"🎤 Voz: {voice_status}\n"
        f"📶 Broker: {mqtt_client.broker}\n"
        f"📤 Topic CMD: `{mqtt_client.topic_cmd}`\n"
        f"👥 Usuarios autorizados: {get_authorized_count()}\n"
        f"📬 Chats suscritos: {len(subscribed_chat_ids)}"
    )
    await update.message.reply_text(status_msg, parse_mode="Markdown")


# ============================================================
# HANDLER DE TEXTO (ReplyKeyboard + NLP)
# ============================================================

async def handle_natural_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_text = update.message.text
    
    if not is_authorized(user_id):
        await update.message.reply_text(
            "🚫 No estás autorizado.\nSi tienes el password: `/auth <password>`",
            parse_mode="Markdown"
        )
        return
    
    # 1. Verificar si es un botón del ReplyKeyboard
    button_command = get_command_from_button_text(user_text)
    
    if button_command:
        if button_command == "STATUS":
            await cmd_status(update, context)
        elif button_command == "HELP":
            await cmd_help(update, context)
        else:
            await execute_command(update, button_command, source="button")
        return
    
    # 2. Si no es botón, procesar como NLP
    command, matched_phrase = parse_natural_command(user_text)
    
    if command is None:
        await update.message.reply_text(
            f"🤔 No entendí lo que quieres decir.\n\n"
            f"{get_command_examples()}\n\n"
            f"O usa los botones del menú o /help.",
            parse_mode="Markdown"
        )
        return
    
    await execute_command(update, command, matched_phrase, source="natural")


# ============================================================
# HANDLER DE BOTONES INLINE (CallbackQuery)
# ============================================================

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja clicks en botones inline."""
    query = update.callback_query
    user_id = query.from_user.id
    
    await query.answer()
    
    if not is_authorized(user_id):
        await query.message.reply_text("🚫 No estás autorizado.", parse_mode="Markdown")
        return
    
    callback_data = query.data
    logger.info(f"Callback recibido de {query.from_user.username}: {callback_data}")
    
    if callback_data.startswith("cmd_"):
        command = callback_data.replace("cmd_", "")
        
        if command == "STATUS":
            voice_status = "🟢 Habilitada" if ENABLE_VOICE else "🔴 Deshabilitada"
            status_msg = (
                "📊 *Estado del sistema:*\n\n"
                f"🔌 Bot: 🟢 Online\n"
                f"📡 MQTT: {'🟢 Conectado' if mqtt_client.connected else '🔴 Desconectado'}\n"
                f"🎤 Voz: {voice_status}\n"
                f"👥 Usuarios autorizados: {get_authorized_count()}\n"
                f"📬 Chats suscritos: {len(subscribed_chat_ids)}"
            )
            await query.message.reply_text(
                status_msg,
                parse_mode="Markdown",
                reply_markup=get_inline_info_keyboard()
            )
        
        elif command == "HELP":
            await cmd_help(update, context)
        
        elif command == "MYID":
            user = query.from_user
            msg = (
                f"🆔 *Tu información:*\n\n"
                f"User ID: `{user.id}`\n"
                f"Username: @{user.username if user.username else 'N/A'}\n"
                f"Estado: ✅ Autorizado"
            )
            await query.message.reply_text(msg, parse_mode="Markdown")
        
        elif command == "MENU":
            await query.message.reply_text(
                "🎛 *Menú de control:*\n\nSelecciona un modo:",
                parse_mode="Markdown",
                reply_markup=get_inline_modes_keyboard()
            )
        
        else:
            await execute_command_from_callback(query, command, source="inline_button")
    
    elif callback_data == "cancel":
        await query.message.edit_text("❌ Acción cancelada.")
    
    else:
        logger.warning(f"Callback desconocido: {callback_data}")


# ============================================================
# HANDLERS DE VOZ
# ============================================================

async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja notas de voz: transcribe y ejecuta."""
    user_id = update.effective_user.id
    user = update.effective_user
    
    if not is_authorized(user_id):
        await update.message.reply_text("🚫 No estás autorizado.", parse_mode="Markdown")
        return
    
    processing_msg = await update.message.reply_text(
        "🎤 _Transcribiendo nota de voz..._",
        parse_mode="Markdown"
    )
    
    audio_path = None
    
    try:
        voice = update.message.voice
        if voice is None:
            await processing_msg.edit_text("❌ No se detectó audio.")
            return
        
        file = await context.bot.get_file(voice.file_id)
        
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
            audio_path = temp_file.name
        
        await file.download_to_drive(audio_path)
        
        transcription = transcribe_audio(audio_path)
        
        if not transcription:
            await processing_msg.edit_text("❌ No pude transcribir el audio.")
            return
        
        await processing_msg.edit_text(
            f"🎤 _Escuché:_ \"{transcription}\"\n⏳ _Procesando..._",
            parse_mode="Markdown"
        )
        
        command, matched_phrase = parse_natural_command(transcription)
        
        if command is None:
            await update.message.reply_text(
                f"🤔 No entendí lo que dijiste.\n\nDijiste: _\"{transcription}\"_\n\n{get_command_examples()}",
                parse_mode="Markdown"
            )
            return
        
        await execute_command(update, command, transcription, source="voice")
        
    except Exception as e:
        logger.error(f"❌ Error procesando voz: {e}")
        try:
            await processing_msg.edit_text(f"❌ Error: {str(e)}")
        except Exception:
            pass
    
    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception:
                pass


async def handle_voice_disabled(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mensaje cuando voz está deshabilitada."""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        return
    
    await update.message.reply_text(
        "🎤 _Las notas de voz no están disponibles en este servidor._\n\n"
        "💡 Usa los botones del menú o /help.",
        parse_mode="Markdown"
    )


async def post_init(application: Application) -> None:
    global event_loop
    event_loop = asyncio.get_event_loop()
    logger.info("✅ Event loop capturado")


# ============================================================
# MAIN
# ============================================================
def main() -> None:
    global bot_application
    
    logger.info("🚀 Iniciando Smart Home Hub Bot v7.0 (con botones)...")
    logger.info(_voice_status_msg)

    if get_authorized_count() == 0:
        logger.warning("⚠️ No hay usuarios autorizados!")

    if ENABLE_VOICE:
        logger.info("🤖 Pre-cargando modelo Whisper...")
        if not preload_model():
            logger.warning("⚠️ No se pudo pre-cargar Whisper")
    else:
        logger.info("ℹ️ Saltando pre-carga de Whisper")

    bot_application = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    mqtt_client.set_ack_callback(on_ack_received)
    mqtt_client.set_temp_callback(on_temp_received)
    mqtt_client.connect()

    # Comandos públicos
    bot_application.add_handler(CommandHandler("start", cmd_start))
    bot_application.add_handler(CommandHandler("myid", cmd_myid))
    bot_application.add_handler(CommandHandler("auth", cmd_auth))
    
    # Comandos protegidos
    bot_application.add_handler(CommandHandler("help", cmd_help))
    bot_application.add_handler(CommandHandler("menu", cmd_menu))
    bot_application.add_handler(CommandHandler("examples", cmd_examples))
    bot_application.add_handler(CommandHandler("night", cmd_night))
    bot_application.add_handler(CommandHandler("day", cmd_day))
    bot_application.add_handler(CommandHandler("relax", cmd_relax))
    bot_application.add_handler(CommandHandler("alarm", cmd_alarm))
    bot_application.add_handler(CommandHandler("party", cmd_party))
    bot_application.add_handler(CommandHandler("standby", cmd_standby))
    bot_application.add_handler(CommandHandler("temp", cmd_temp))
    bot_application.add_handler(CommandHandler("status", cmd_status))
    
    # Handler de botones inline
    bot_application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Handler de texto (incluye ReplyKeyboard + NLP)
    bot_application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_natural_language)
    )
    
    # Handler de voz
    if ENABLE_VOICE:
        bot_application.add_handler(MessageHandler(filters.VOICE, handle_voice_message))
        logger.info("🎤 Handler de voz REGISTRADO")
    else:
        bot_application.add_handler(MessageHandler(filters.VOICE, handle_voice_disabled))
        logger.info("🎤 Voz en modo informativo")

    logger.info("✅ Bot listo. Escuchando mensajes...")
    bot_application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()