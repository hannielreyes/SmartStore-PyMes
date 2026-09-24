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

# Reexportar funciones desde los módulos temáticos
from .usuarios import *
from .sesiones import *
from .tiendas import *
from .productos import *
from .reservas import *
from .pagos import *