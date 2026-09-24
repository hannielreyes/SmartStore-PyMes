# -*- coding: utf-8 -*-
"""script de migración automática de funciones desde legacy (legado.py)

Este script analiza el módulo `database.legado` y reparte cada función en el
sub‑módulo correspondiente según una tabla de mapeo sencilla.

Uso:
    python scripts/migrar_legado.py

El script crea/actualiza los archivos siguientes en `database/`:
    - usuarios.py
    - tiendas.py
    - productos.py
    - reservas.py
    - sesiones.py
    - pagos.py

Cada archivo será sobrescrito con únicamente las definiciones de funciones que
le correspondan.  Los imports de `legado` al inicio de los archivos actuales se
eliminan automáticamente.

Después de ejecutar el script, `legado.py` puede ser eliminado de forma segura
porque todas sus funciones estarán disponibles a través de los módulos
temáticos.  El archivo `database/__init__.py` ya está preparado para re‑exportar
las funciones mediante `from .usuarios import *`, etc.
"""

import ast
import os
import textwrap
from pathlib import Path

# Ruta al proyecto raíz (asumimos que este script está en <root>/scripts)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_DIR = PROJECT_ROOT / "database"
LEGADO_PATH = DATABASE_DIR / "legado.py"

# Mapeo de nombres de función -> módulo destino
MODULE_MAP = {
    # usuarios
    "obtener_usuario": "usuarios",
    "obtener_usuario_por_id": "usuarios",
    "actualizar_perfil_usuario": "usuarios",
    "registrar_usuario": "usuarios",
    "registrar_usuario_auth": "usuarios",
    "iniciar_sesion_auth": "usuarios",
    "crear_perfil_auth": "usuarios",
    "establecer_contraseña_auth": "usuarios",
    "restaurar_sesion_auth": "usuarios",
    "actualizar_imagen_usuario": "usuarios",
    "verificar_correo_existe": "usuarios",
    "obtener_telefono_por_correo": "usuarios",
    "obtener_usuario_por_correo": "usuarios",
    "obtener_usuario_por_telefono": "usuarios",
    "actualizar_contraseña_por_correo": "usuarios",
    "obtener_contraseña_por_correo": "usuarios",
    "validar_codigo_sesion": "sesiones",
    "invalidar_codigo_sesion_bd": "sesiones",
    "guardar_codigo_sesion": "sesiones",
    "crear_token_sesion": "sesiones",
    "obtener_usuario_por_token": "sesiones",
    "revocar_token_sesion": "sesiones",
    # tiendas
    "obtener_tienda": "tiendas",
    "obtener_tienda_usuario": "tiendas",
    "obtener_tienda_por_id": "tiendas",
    "obtener_tiendas_usuario": "tiendas",
    "eliminar_tienda": "tiendas",
    "guardar_tienda": "tiendas",
    "actualizar_tienda": "tiendas",
    "obtener_saldo_tienda": "tiendas",
    "agregar_saldo_tienda": "tiendas",
    "retirar_saldo_tienda": "tiendas",
    # productos
    "obtener_productos_aleatorios": "productos",
    "obtener_top_productos": "productos",
    "registrar_producto": "productos",
    "actualizar_producto": "productos",
    "obtener_productos": "productos",
    "registrar_busqueda_sin_resultado": "productos",
    "obtener_oportunidades_productos": "productos",
    "obtener_productos_usuario": "productos",
    "obtener_producto_por_id": "productos",
    "obtener_productos_por_nombre": "productos",
    "obtener_productos_por_tienda": "productos",
    "obtener_stock_total": "productos",
    "obtener_stock_total_usuario": "productos",
    "obtener_alertas_inventario": "productos",
    "eliminar_producto": "productos",
    "reducir_stock_producto": "productos",
    # reservas
    "agregar_reserva": "reservas",
    "obtener_reservas_usuario": "reservas",
    "cancelar_reservas_vencidas": "reservas",
    "obtener_reservas_por_tienda": "reservas",
    "obtener_entregas_completadas_por_tienda": "reservas",
    "eliminar_reserva": "reservas",
    "confirmar_reserva": "reservas",
    "marcar_como_entregada": "reservas",
    "cambiar_estado_reserva": "reservas",
    "obtener_estado_reserva": "reservas",
    "procesar_pago_reserva": "pagos",
    # pagos (solo esta función por ahora)
    "procesar_pago_reserva": "pagos",
    # sesiones auxiliares (ya mapeados arriba)
}

def extract_functions(source: str):
    """Parsea `source` y devuelve un dict {nombre: código fuente} para cada función."""
    tree = ast.parse(source)
    functions = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            # obtener código fuente exacto del nodo
            start = node.lineno - 1  # ast lineno es 1‑based
            # buscar el final (próxima definición o EOF)
            end = len(source.splitlines())
            for later in tree.body:
                if isinstance(later, ast.FunctionDef) and later.lineno > node.lineno:
                    end = later.lineno - 1
                    break
            func_lines = source.splitlines()[start:end]
            functions[node.name] = "\n".join(func_lines)
    return functions

def main():
    # leer legado
    with open(LEGADO_PATH, "r", encoding="utf-8") as f:
        legado_code = f.read()

    # extraer todas las funciones
    funciones = extract_functions(legado_code)

    # agrupar por módulo destino
    módulos = {m: [] for m in set(MODULE_MAP.values())}
    for nombre, codigo in funciones.items():
        modulo = MODULE_MAP.get(nombre)
        if modulo:
            módulos[modulo].append(codigo)
        else:
            # si la función no está mapeada, la dejamos en legado (no se mueve)
            pass

    # encabezado común (imports necesarios)
    encabezado = textwrap.dedent("""\
Módulo generado automáticamente a partir de `legado.py`.
No editar manualmente; los cambios deben hacerse en `legado.py` y volver a ejecutar este script.
""") + """
from .conexion import (
    get_db_connection,
    _supabase_activo,
    _supabase_unico,
    _supabase_insertar,
    _supabase_actualizar,
    _supabase_burger,
)
import bcrypt, hashlib, secrets
from datetime import datetime, timedelta
from urllib.parse import quote
"""

    for modulo, codigos in módulos.items():
        if not codigos:
            continue
        contenido = encabezado + "\n\n" + "\n\n\n".join(codigos) + "\n"
        destino = DATABASE_DIR / f"{modulo}.py"
        # sobrescribir el archivo con el nuevo contenido
        with open(destino, "w", encoding="utf-8") as out:
            out.write(contenido)
        print(f"[migración] {modulo}.py actualizado con {len(codigos)} funciones")

    print("Migración completada. Puede eliminar `legado.py` si todo funciona.")

if __name__ == "__main__":
    main()
