import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from database import offline, productos, sesiones, tiendas
from database import conexion
from database.conexion import SupabaseNoDisponible


class OfflinePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path_patch = patch.object(
            conexion,
            "DB_PATH",
            str(Path(self.temp_dir.name) / "offline-test.db"),
        )
        self.db_path_patch.start()
        offline.inicializar_almacen_offline()

    def tearDown(self):
        self.db_path_patch.stop()
        self.temp_dir.cleanup()

    def test_offline_session_is_local_and_revocable(self):
        offline.guardar_sesion_offline("session-token", 17, "user@example.com", "User")

        usuario = sesiones.obtener_sesion_offline("session-token")
        self.assertEqual((usuario.id, usuario.correo), (17, "user@example.com"))
        with (
            patch.object(sesiones, "_supabase_activo", return_value=True),
            patch.object(
                sesiones,
                "_supabase_unico",
                side_effect=SupabaseNoDisponible("offline"),
            ),
        ):
            usuario_validado = sesiones.obtener_usuario_por_token("session-token")
        self.assertEqual(usuario_validado.id, 17)

        offline.revocar_sesion_offline("session-token")
        self.assertIsNone(sesiones.obtener_sesion_offline("session-token"))

    def test_unverified_session_is_not_treated_as_revoked(self):
        with (
            patch.object(sesiones, "_supabase_activo", return_value=True),
            patch.object(
                sesiones,
                "_supabase_unico",
                side_effect=SupabaseNoDisponible("offline"),
            ),
        ):
            with self.assertRaises(SupabaseNoDisponible):
                sesiones.obtener_usuario_por_token("not-cached")

    def test_recovery_requeues_only_stale_sync_operations(self):
        offline.encolar_creacion(17, "tiendas", -1, {"nombre": "Tienda vieja"})
        offline.encolar_creacion(17, "tiendas", -2, {"nombre": "Tienda activa"})
        conn = conexion.get_db_connection()
        try:
            conn.execute(
                """
                UPDATE cola_offline
                SET estado = 'sincronizando', sincronizando_en = ?
                WHERE entidad_id = '-1'
                """,
                ("2000-01-01T00:00:00",),
            )
            conn.execute(
                """
                UPDATE cola_offline
                SET estado = 'sincronizando', sincronizando_en = ?
                WHERE entidad_id = '-2'
                """,
                (datetime.now().isoformat(),),
            )
            conn.commit()
        finally:
            conn.close()

        offline.recuperar_sincronizacion_interrumpida()

        conn = conexion.get_db_connection()
        try:
            estados = dict(
                conn.execute(
                    "SELECT entidad_id, estado FROM cola_offline"
                ).fetchall()
            )
        finally:
            conn.close()
        self.assertEqual(estados, {"-1": "pendiente", "-2": "sincronizando"})

    def test_store_and_product_queue_sync_once_with_mapped_store_id(self):
        with (
            patch.object(tiendas, "_supabase_activo", return_value=True),
            patch.object(
                tiendas,
                "_supabase_unico",
                side_effect=SupabaseNoDisponible("offline"),
            ),
        ):
            tienda_id = tiendas.guardar_tienda(
                "Mi tienda", "88888888", 36.5, 17, "Dirección", None
            )

        self.assertLess(tienda_id, 0)
        with patch.object(productos, "_supabase_activo", return_value=True):
            guardado = productos.registrar_producto(
                "Camisa", "Marca", "M", 100, 2.7, 4, tienda_id, usuario_id=17
            )
        self.assertTrue(guardado)

        with (
            patch.object(tiendas, "_supabase_activo", return_value=True),
            patch.object(
                tiendas,
                "_supabase_lista",
                side_effect=SupabaseNoDisponible("offline"),
            ),
        ):
            tienda_local = tiendas.obtener_tiendas_usuario(17)
        with (
            patch.object(productos, "_supabase_activo", return_value=True),
            patch.object(
                productos,
                "_supabase_lista",
                side_effect=SupabaseNoDisponible("offline"),
            ),
        ):
            productos_locales = productos.obtener_productos_usuario(17)
        self.assertEqual(tienda_local[0].id, tienda_id)
        self.assertEqual(productos_locales[0].nombre, "Camisa")
        self.assertTrue(
            tiendas.actualizar_tienda(
                tienda_id, 17, "Tienda editada", "88888888", 37, "Nueva dirección", None
            )
        )
        self.assertTrue(
            productos.actualizar_producto(
                productos_locales[0].id, 17, "Camisa editada", "Marca", "M", 100, 2.7, 3
            )
        )

        remoto = {"tiendas": [], "productos": []}

        def buscar_remoto(tabla, parametros=""):
            offline_uuid = None
            if "offline_uuid=eq." in parametros:
                offline_uuid = parametros.split("offline_uuid=eq.", 1)[1].split("&", 1)[0]
                return next(
                    (
                        fila
                        for fila in remoto[tabla]
                        if fila.get("offline_uuid") == offline_uuid
                    ),
                    None,
                )
            if tabla == "tiendas" and "usuario_id=eq." in parametros:
                usuario_id = parametros.split("usuario_id=eq.", 1)[1].split("&", 1)[0]
                return next(
                    (
                        fila
                        for fila in remoto["tiendas"]
                        if str(fila.get("usuario_id")) == usuario_id
                    ),
                    None,
                )
            return None

        def insertar_remoto(tabla, datos):
            registro = dict(datos)
            registro["id"] = len(remoto[tabla]) + (101 if tabla == "tiendas" else 201)
            remoto[tabla].append(registro)
            return registro

        with (
            patch.object(offline, "_supabase_activo", return_value=True),
            patch.object(offline, "_supabase_unico", side_effect=buscar_remoto),
            patch.object(offline, "_supabase_insertar", side_effect=insertar_remoto),
        ):
            primera = offline.sincronizar_cambios_offline(17)
            segunda = offline.sincronizar_cambios_offline(17)

        self.assertEqual(primera["sincronizados"], 2)
        self.assertEqual(segunda["sincronizados"], 0)
        self.assertEqual(len(remoto["tiendas"]), 1)
        self.assertEqual(len(remoto["productos"]), 1)
        self.assertEqual(remoto["tiendas"][0]["nombre"], "Tienda editada")
        self.assertEqual(remoto["productos"][0]["nombre"], "Camisa editada")
        self.assertEqual(remoto["productos"][0]["tienda_id"], remoto["tiendas"][0]["id"])

    def test_remote_values_win_when_edited_fields_changed(self):
        offline.guardar_catalogo(
            17,
            "productos",
            [{"id": 9, "tienda_id": 3, "nombre": "Camisa", "stock": 5}],
        )
        self.assertTrue(
            offline.encolar_actualizacion(17, "productos", 9, {"stock": 2})
        )
        remoto = {
            "id": 9,
            "tienda_id": 3,
            "nombre": "Camisa",
            "marca": None,
            "talla": None,
            "precio_cordobas": None,
            "precio_dolares": None,
            "stock": 4,
        }

        def buscar_remoto(tabla, parametros=""):
            return remoto if tabla == "productos" else None

        with (
            patch.object(offline, "_supabase_activo", return_value=True),
            patch.object(offline, "_supabase_unico", side_effect=buscar_remoto),
            patch.object(offline, "_supabase_actualizar") as actualizar,
        ):
            resultado = offline.sincronizar_cambios_offline(17)

        self.assertEqual(resultado["conflictos"], 1)
        self.assertEqual(remoto["stock"], 4)
        actualizar.assert_not_called()
        self.assertEqual(offline.contar_conflictos_offline(17), 1)

    def test_global_product_search_uses_local_catalog_when_offline(self):
        offline.guardar_catalogo(
            offline.PUBLIC_CACHE_USER_ID,
            "productos",
            [
                {
                    "id": 31,
                    "nombre": "Camisa global",
                    "marca": "Marca",
                    "talla": "M",
                    "precio_cordobas": 100,
                    "precio_dolares": 2.7,
                    "stock": 4,
                    "tienda_id": 8,
                    "imagen": None,
                    "imagen_2": None,
                    "categoria": "Ropa",
                    "descripcion": None,
                    "estado_producto": "Nuevo",
                    "etiquetas": None,
                    "estilo": None,
                    "color_principal": None,
                    "material": None,
                    "garantia": None,
                    "especificacion": None,
                }
            ],
        )

        with (
            patch.object(productos, "_supabase_activo", return_value=True),
            patch.object(
                productos,
                "_supabase_lista",
                side_effect=SupabaseNoDisponible("offline"),
            ),
        ):
            resultados = productos.obtener_productos_por_nombre(
                "camisa",
                cache_usuario_id=17,
            )

        self.assertEqual([producto.nombre for producto in resultados], ["Camisa global"])

    def test_edit_during_sync_is_queued_for_the_next_pass(self):
        offline.guardar_catalogo(
            17,
            "productos",
            [{"id": 9, "tienda_id": 3, "nombre": "Camisa", "stock": 5}],
        )
        self.assertTrue(
            offline.encolar_actualizacion(17, "productos", 9, {"stock": 4})
        )
        remoto = {
            "id": 9,
            "tienda_id": 3,
            "nombre": "Camisa",
            "marca": None,
            "talla": None,
            "precio_cordobas": None,
            "precio_dolares": None,
            "stock": 5,
        }
        encolo_en_vuelo = False

        def buscar_remoto(tabla, parametros=""):
            nonlocal encolo_en_vuelo
            if not encolo_en_vuelo:
                encolo_en_vuelo = True
                self.assertTrue(
                    offline.encolar_actualizacion(
                        17,
                        "productos",
                        9,
                        {"stock": 3},
                    )
                )
            return remoto

        def actualizar_remoto(tabla, cambios, parametros):
            remoto.update(cambios)
            return [dict(remoto)]

        with (
            patch.object(offline, "_supabase_activo", return_value=True),
            patch.object(offline, "_supabase_unico", side_effect=buscar_remoto),
            patch.object(offline, "_supabase_actualizar", side_effect=actualizar_remoto),
        ):
            primera = offline.sincronizar_cambios_offline(17)
            segunda = offline.sincronizar_cambios_offline(17)

        self.assertEqual(primera["sincronizados"], 1)
        self.assertEqual(offline.contar_cambios_pendientes(17), 0)
        self.assertEqual(segunda["sincronizados"], 1)
        self.assertEqual(remoto["stock"], 3)


if __name__ == "__main__":
    unittest.main()
