"""Cola en segundo plano para tareas secundarias de SmartStore."""

import logging
from queue import Full, Queue
from threading import Lock, Thread


_cola_busquedas = Queue(maxsize=100)
_bloqueo_inicio = Lock()
_trabajador_iniciado = False


def _procesar_busquedas_sin_resultado():
    """Consume solicitudes sin tocar la interfaz gráfica."""
    while True:
        usuario_id, termino = _cola_busquedas.get()
        try:
            import database as db

            db.registrar_busqueda_sin_resultado(usuario_id, termino)
        except Exception:
            logging.getLogger("smartstore").exception(
                "No se pudo registrar una búsqueda sin resultados"
            )
        finally:
            _cola_busquedas.task_done()


def _iniciar_trabajador():
    global _trabajador_iniciado
    if _trabajador_iniciado:
        return
    with _bloqueo_inicio:
        if _trabajador_iniciado:
            return
        Thread(
            target=_procesar_busquedas_sin_resultado,
            name="smartstore-cola-busquedas",
            daemon=True,
        ).start()
        _trabajador_iniciado = True


def encolar_busqueda_sin_resultado(usuario_id, termino):
    """Encola el registro de una búsqueda sin bloquear la pantalla."""
    termino = str(termino or "").strip()
    if not usuario_id or len(termino) < 4:
        return False

    _iniciar_trabajador()
    try:
        _cola_busquedas.put_nowait((usuario_id, termino))
        return True
    except Full:
        return False
