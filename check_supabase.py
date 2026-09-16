"""Prueba local de la conexion de SmartStore con Supabase."""

from supabase_config import SUPABASE_URL, comprobar_conexion


if __name__ == "__main__":
    print(f"Probando Supabase: {SUPABASE_URL}")
    estado, contenido = comprobar_conexion()
    print(f"Conexion correcta. HTTP {estado}")
    print(contenido[:500])
