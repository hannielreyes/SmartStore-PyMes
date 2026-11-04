"""
Paquete principal de Base de Datos para SmartStore PyMEs.
Exporta las funciones principales para mantener compatibilidad con las vistas.
"""

from .conexion import (
    _supabase_activo,
    verificar_conexion_remota,
    USAR_SUPABASE,
    get_db_connection,
)
from .esquema import inicializar_bd

# Reexportar funciones desde los módulos temáticos
from .usuarios import *
from .sesiones import *
from .tiendas import *
from .productos import *
from .reservas import *
from .pagos import *
from .estadisticas import *
from .offline import (
    contar_cambios_pendientes,
    contar_conflictos_offline,
    guardar_sesion_offline,
    marcar_catalogo_conocido,
    obtener_sesion_offline,
    sincronizar_cambios_offline,
    tiene_catalogo_conocido,
)