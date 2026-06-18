"""
============================================================
VOICE MODULE - Smart Home Hub Bot
============================================================
Transcripción de notas de voz usando whisper.cpp.
Implementación C++ más ligera que openai-whisper.
============================================================
"""

import os
import logging
from pywhispercpp.model import Model

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURACIÓN DEL MODELO
# ============================================================
# Modelos disponibles (se descargan automáticamente):
#   "tiny"     →  75 MB,  más rápido,  menor precisión
#   "base"     → 142 MB,  rápido,      buena precisión
#   "small"    → 466 MB,  medio,       muy buena precisión
#   "medium"   → 1.5 GB,  lento,       excelente precisión
#   "large"    → 3.0 GB,  muy lento,   máxima precisión
MODEL_SIZE = os.getenv("WHISPER_MODEL", "tiny")

# Idioma esperado
# "es" = español, "en" = inglés
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "es")

# Número de threads para inferencia (Railway free tiene CPU limitado)
N_THREADS = int(os.getenv("WHISPER_THREADS", "2"))


# ============================================================
# INSTANCIA GLOBAL DEL MODELO (lazy loading)
# ============================================================
_model = None


def _get_model():
    """Carga el modelo solo cuando se necesita (lazy)"""
    global _model
    
    if _model is None:
        logger.info(f"🤖 Cargando modelo whisper.cpp '{MODEL_SIZE}'...")
        logger.info(f"   (Primera vez tarda más por la descarga)")
        logger.info(f"   Threads: {N_THREADS}, Idioma: {WHISPER_LANGUAGE}")
        
        _model = Model(
            MODEL_SIZE,
            n_threads=N_THREADS,
        )
        
        logger.info(f"✅ Modelo whisper.cpp cargado: {MODEL_SIZE}")
    
    return _model


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe un archivo de audio a texto.
    
    Args:
        audio_path: Ruta al archivo de audio (mp3, wav, ogg, opus, etc.)
    
    Returns:
        Texto transcrito (string vacío si falla)
    """
    if not os.path.exists(audio_path):
        logger.error(f"❌ Archivo no encontrado: {audio_path}")
        return ""
    
    try:
        logger.info(f"🎤 Transcribiendo audio: {audio_path}")
        
        model = _get_model()
        
        # Transcribir
        segments = model.transcribe(
            audio_path,
            language=WHISPER_LANGUAGE,
        )
        
        # Concatenar todos los segmentos
        transcription = " ".join(segment.text for segment in segments).strip()
        
        logger.info(f"✅ Transcripción: '{transcription}'")
        
        return transcription
        
    except Exception as e:
        logger.error(f"❌ Error transcribiendo audio: {e}")
        return ""


# ============================================================
# FUNCIÓN PARA INICIALIZAR EL MODELO AL ARRANQUE
# ============================================================

def preload_model():
    """
    Pre-carga el modelo al arrancar el bot.
    Útil para que la primera transcripción no sea lenta.
    """
    try:
        _get_model()
        return True
    except Exception as e:
        logger.error(f"❌ Error pre-cargando modelo: {e}")
        return False