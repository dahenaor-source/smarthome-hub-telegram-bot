"""
============================================================
KEYBOARDS MODULE - Smart Home Hub Bot
============================================================
Definiciones de teclados (Reply e Inline) para el bot.
============================================================
"""

from telegram import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


# ============================================================
# REPLY KEYBOARD (menú principal persistente)
# ============================================================

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Teclado principal que aparece debajo del input del usuario.
    Siempre disponible.
    """
    keyboard = [
        [
            KeyboardButton("🌙 Night"),
            KeyboardButton("☀️ Day"),
        ],
        [
            KeyboardButton("😌 Relax"),
            KeyboardButton("🚨 Alarm"),
        ],
        [
            KeyboardButton("🎉 Party"),
            KeyboardButton("⏹ Standby"),
        ],
        [
            KeyboardButton("🌡 Temperatura"),
            KeyboardButton("ℹ️ Estado"),
        ],
        [
            KeyboardButton("❓ Ayuda"),
        ],
    ]
    
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,        # Botones del tamaño correcto
        one_time_keyboard=False,     # No se oculta al usar
        input_field_placeholder="Elige una opción o escribe..."
    )


# ============================================================
# INLINE KEYBOARDS (botones dentro de mensajes)
# ============================================================

def get_inline_modes_keyboard() -> InlineKeyboardMarkup:
    """
    Teclado inline con todos los modos.
    Para usar en /menu.
    """
    keyboard = [
        [
            InlineKeyboardButton("🌙 Night", callback_data="cmd_N"),
            InlineKeyboardButton("☀️ Day", callback_data="cmd_D"),
        ],
        [
            InlineKeyboardButton("😌 Relax", callback_data="cmd_R"),
            InlineKeyboardButton("🚨 Alarm", callback_data="cmd_A"),
        ],
        [
            InlineKeyboardButton("🎉 Party", callback_data="cmd_P"),
            InlineKeyboardButton("⏹ Standby", callback_data="cmd_S"),
        ],
        [
            InlineKeyboardButton("🌡 Temperatura", callback_data="cmd_T"),
        ],
        [
            InlineKeyboardButton("ℹ️ Estado del sistema", callback_data="cmd_STATUS"),
        ],
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_inline_confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    """
    Teclado de confirmación Sí/No para acciones críticas.
    
    Args:
        action: Identificador de la acción (ej. "alarm", "party")
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ Sí, hacerlo", callback_data=f"confirm_{action}"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel"),
        ],
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_inline_quick_keyboard() -> InlineKeyboardMarkup:
    """
    Teclado rápido con los modos más usados.
    Más compacto.
    """
    keyboard = [
        [
            InlineKeyboardButton("🌙 Night", callback_data="cmd_N"),
            InlineKeyboardButton("☀️ Day", callback_data="cmd_D"),
            InlineKeyboardButton("⏹ Standby", callback_data="cmd_S"),
        ],
        [
            InlineKeyboardButton("🌡 Temperatura", callback_data="cmd_T"),
        ],
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_inline_info_keyboard() -> InlineKeyboardMarkup:
    """
    Teclado con opciones de información.
    """
    keyboard = [
        [
            InlineKeyboardButton("🌡 Ver temperatura", callback_data="cmd_T"),
            InlineKeyboardButton("ℹ️ Estado", callback_data="cmd_STATUS"),
        ],
        [
            InlineKeyboardButton("🆔 Mi ID", callback_data="cmd_MYID"),
            InlineKeyboardButton("❓ Ayuda", callback_data="cmd_HELP"),
        ],
        [
            InlineKeyboardButton("◀️ Volver al menú", callback_data="cmd_MENU"),
        ],
    ]
    
    return InlineKeyboardMarkup(keyboard)


# ============================================================
# MAPEO DE TEXTOS DE BOTONES A COMANDOS
# ============================================================

# Mapea el texto del botón (ReplyKeyboard) al comando que envía
BUTTON_TEXT_TO_COMMAND = {
    "🌙 Night":       "N",
    "☀️ Day":         "D",
    "😌 Relax":       "R",
    "🚨 Alarm":       "A",
    "🎉 Party":       "P",
    "⏹ Standby":     "S",
    "🌡 Temperatura": "T",
    "ℹ️ Estado":      "STATUS",
    "❓ Ayuda":       "HELP",
}


def get_command_from_button_text(text: str) -> str:
    """
    Convierte el texto de un botón al comando correspondiente.
    
    Returns:
        Comando o "" si no es un botón conocido
    """
    return BUTTON_TEXT_TO_COMMAND.get(text, "")