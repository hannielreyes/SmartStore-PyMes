"""
voz.py - Sistema de voz para SmartStore con Edge TTS
Voces disponibles:
- Jorge (Normal): es-MX-JorgeNeural
- Dalia (Diversión): es-MX-DaliaNeural  
- Tomás (Profesional): es-AR-TomasNeural
- Álvaro (Navegación): es-ES-AlvaroNeural
"""

import os
import asyncio
import threading

try:
    from flet_audio import Audio
except ModuleNotFoundError:
    Audio = None

try:
    import edge_tts
except ModuleNotFoundError:
    edge_tts = None


class VoiceService:
    # Servicio reutilizable de voz: configura audio, idioma, velocidad y tono.
    def __init__(self, page=None, voice_name="es-MX-JorgeNeural", rate="+0%", pitch="+0Hz"):
        self.rate = rate
        self.pitch = pitch
        self.voice_name = voice_name
        print(f"[INFO VOZ] Usando voz: {self.voice_name}")
        self.temp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_tts.mp3")
        self._cancelar = threading.Event()
        self._hilo_actual = None
        self.page = page
        self.audio = Audio() if page is not None and Audio is not None else None
        self.audio_disponible = self.audio is not None

        if not self.audio_disponible:
            print("[WARN AUDIO] flet-audio no está disponible. La salida de voz queda deshabilitada.")

    def stop(self):
        """Detiene la voz inmediatamente."""
        self._cancelar.set()
        if not self.audio_disponible:
            return
        self.page.run_task(self.audio.pause)

    async def _generar_audio(self, texto):
        """Genera audio con Edge TTS."""
        if edge_tts is None:
            print("[WARN TTS] edge_tts no está disponible en esta build.")
            return False
        try:
            communicate = edge_tts.Communicate(texto, self.voice_name, rate=self.rate, pitch=self.pitch)
            await communicate.save(self.temp_file)
            return True
        except Exception as e:
            print(f"[ERROR TTS] {e}")
            return False

    async def _reproducir_audio(self, audio_data, on_start=None, on_end=None):
        """Entrega el audio al reproductor nativo de Flet."""
        if not self.audio_disponible or self._cancelar.is_set():
            if on_end:
                on_end()
            return

        try:
            self.audio.src = audio_data
            if on_start:
                on_start()
            await self.audio.play()
        except Exception as e:
            print(f"[ERROR AUDIO] {e}")
        finally:
            if on_end:
                on_end()

    def _limpiar_temp(self):
        try:
            if os.path.exists(self.temp_file):
                os.remove(self.temp_file)
        except Exception:
            pass

    def _ejecutar_voz(self, texto, on_start, on_end):
        """Hilo principal de ejecución de voz."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            success = loop.run_until_complete(self._generar_audio(texto))
        finally:
            loop.close()

        if not success or self._cancelar.is_set():
            if on_end:
                on_end()
            self._limpiar_temp()
            return

        try:
            with open(self.temp_file, "rb") as audio_file:
                audio_data = audio_file.read()
            self.page.run_task(self._reproducir_audio, audio_data, on_start, on_end)
        except Exception as e:
            print(f"[ERROR AUDIO] {e}")
            if on_end:
                on_end()
        self._limpiar_temp()

    def hablar(self, texto, on_start=None, on_end=None):
        """
        Habla el texto con la voz seleccionada.
        """
        if not texto or not texto.strip():
            if on_end:
                on_end()
            return

        if not self.audio_disponible or edge_tts is None:
            print("[WARN AUDIO] La salida por voz está deshabilitada en esta build. Se continúa sin reproducir audio.")
            if on_end:
                on_end()
            return

        self.stop()
        if self._hilo_actual and self._hilo_actual.is_alive():
            self._hilo_actual.join(timeout=1.5)

        self._cancelar.clear()

        self._hilo_actual = threading.Thread(
            target=self._ejecutar_voz,
            args=(texto, on_start, on_end),
            daemon=True
        )
        self._hilo_actual.start()

    def speak(self, texto, on_start=None, on_end=None):
        """Alias de hablar."""
        self.hablar(texto, on_start, on_end)