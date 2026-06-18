"""
============================================================
VOICE MODULE - Smart Home Hub Bot
============================================================
Transcripción usando whisper.cpp con conversión manual a WAV.
Busca FFmpeg en múltiples ubicaciones para máxima compatibilidad.
============================================================
"""

import os
import logging
import subprocess
import shutil
from pywhispercpp.model import Model

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURACIÓN
# ============================================================
MODEL_SIZE = os.getenv("WHISPER_MODEL", "tiny")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "es")
N_THREADS = int(os.getenv("WHISPER_THREADS", "2"))

_model = None
_ffmpeg_path = None


def _find_ffmpeg() -> str:
    """
    Busca el ejecutable de FFmpeg en ubicaciones comunes.
    Retorna la ruta completa o "" si no lo encuentra.
    """
    global _ffmpeg_path
    
    if _ffmpeg_path:
        return _ffmpeg_path
    
    # 1. Buscar en PATH
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        _ffmpeg_path = ffmpeg
        logger.info(f"✅ FFmpeg encontrado en PATH: {ffmpeg}")
        return ffmpeg
    
    # 2. Buscar en ubicaciones comunes
    common_paths = [
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/opt/homebrew/bin/ffmpeg",
        "/nix/store/*/bin/ffmpeg",  # Nix
        "/app/.apt/usr/bin/ffmpeg",  # Heroku style
    ]
    
    for path in common_paths:
        # Manejar wildcards
        if "*" in path:
            import glob
            matches = glob.glob(path)
            if matches:
                _ffmpeg_path = matches[0]
                logger.info(f"✅ FFmpeg encontrado: {_ffmpeg_path}")
                return _ffmpeg_path
        elif os.path.exists(path):
            _ffmpeg_path = path
            logger.info(f"✅ FFmpeg encontrado: {path}")
            return path
    
    logger.error("❌ FFmpeg NO encontrado en ninguna ubicación común")
    return ""


def _get_model():
    """Carga el modelo solo cuando se necesita (lazy)"""
    global _model
    
    if _model is None:
        logger.info(f"🤖 Cargando modelo whisper.cpp '{MODEL_SIZE}'...")
        _model = Model(MODEL_SIZE, n_threads=N_THREADS)
        logger.info(f"✅ Modelo whisper.cpp cargado: {MODEL_SIZE}")
    
    return _model


def _convert_to_wav(input_path: str) -> str:
    """
    Convierte un archivo de audio a WAV 16kHz mono usando FFmpeg.
    
    Args:
        input_path: Ruta al audio original
    
    Returns:
        Ruta al WAV temporal (o "" si falla)
    """
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        logger.error("❌ No se puede convertir: FFmpeg no disponible")
        return ""
    
    try:
        wav_path = input_path + ".wav"
        
        cmd = [
            ffmpeg,
            "-i", input_path,
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            "-y",
            wav_path
        ]
        
        logger.info(f"🔄 Convirtiendo audio con FFmpeg...")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.error(f"❌ FFmpeg error (code {result.returncode}): {result.stderr[:500]}")
            return ""
        
        if not os.path.exists(wav_path):
            logger.error("❌ Archivo WAV no se creó")
            return ""
        
        size = os.path.getsize(wav_path)
        logger.info(f"✅ Convertido a WAV: {size} bytes")
        return wav_path
        
    except subprocess.TimeoutExpired:
        logger.error("❌ FFmpeg timeout (>30s)")
        return ""
    except Exception as e:
        logger.error(f"❌ Error convirtiendo: {e}")
        return ""


def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe un archivo de audio a texto.
    Convierte primero a WAV para compatibilidad con whisper.cpp.
    """
    if not os.path.exists(audio_path):
        logger.error(f"❌ Archivo no encontrado: {audio_path}")
        return ""
    
    wav_path = ""
    
    try:
        original_size = os.path.getsize(audio_path)
        logger.info(f"🎤 Audio recibido: {audio_path} ({original_size} bytes)")
        
        # 1. Convertir a WAV
        wav_path = _convert_to_wav(audio_path)
        if not wav_path:
            return ""
        
        # 2. Transcribir el WAV
        logger.info(f"🎤 Transcribiendo WAV...")
        model = _get_model()
        
        segments = model.transcribe(
            wav_path,
            language=WHISPER_LANGUAGE,
        )
        
        # 3. Concatenar
        transcription = " ".join(s.text for s in segments).strip()
        
        if transcription:
            logger.info(f"✅ Transcripción: '{transcription}'")
        else:
            logger.warning("⚠️ Transcripción vacía (¿audio sin voz?)")
        
        return transcription
        
    except Exception as e:
        logger.error(f"❌ Error transcribiendo audio: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return ""
    
    finally:
        # Limpiar WAV temporal
        if wav_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception as e:
                logger.warning(f"⚠️ No se pudo eliminar WAV: {e}")


def preload_model():
    """Pre-carga el modelo + verifica FFmpeg"""
    try:
        # Verificar FFmpeg primero
        ffmpeg = _find_ffmpeg()
        if not ffmpeg:
            logger.error("❌ FFmpeg no disponible - las transcripciones fallarán")
        
        _get_model()
        return True
    except Exception as e:
        logger.error(f"❌ Error pre-cargando modelo: {e}")
        return False