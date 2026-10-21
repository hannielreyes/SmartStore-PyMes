-- ================================================================
-- SOLO PRUEBAS CONTROLADAS. NO ES CONFIGURACION DE PRODUCCION.
-- ================================================================
--
-- Este archivo existe para que la version de desarrollo pueda probar el
-- flujo actual mientras termina la migracion a Supabase Auth.
--
-- QUE HACE:
--   * Activa RLS, pero crea una politica que permite TODO a anon y
--     authenticated usando `using (true)` y `with check (true)`.
--   * Concede a la APK permisos de leer, insertar, modificar y borrar
--     filas de todas las tablas principales.
--   * Permite probar el login propio, registro, tokens y pantallas de la app.
--
-- POR QUE ES PELIGROSO:
--   * Una APK puede ser inspeccionada o modificada por un usuario.
--   * La clave anon es publica y no identifica de forma confiable al usuario.
--   * Un cliente podria intentar leer o modificar datos de otro usuario si
--     se deja esta politica activa.
--
-- CUANDO SE PUEDE USAR:
--   * Solo en el proyecto de desarrollo/pruebas.
--   * Solo mientras se prueba la migracion a Supabase Auth.
--   * Nunca antes de confirmar que no contiene datos reales sensibles.
--
-- NO EJECUTAR ESTE ARCHIVO:
--   * En el proyecto de produccion.
--   * Antes de publicar la APK.
--   * Como solucion permanente a errores de RLS.
--
-- PARA PRODUCCION se debe ejecutar supabase_production_rls.sql, pero solo
-- despues de completar todos los pendientes indicados en ese archivo y en
-- README.md. Ese cambio revoca el acceso directo de anon.

do $$
declare
    tabla text;
begin
    foreach tabla in array array['usuarios', 'sesiones_dispositivo', 'tiendas', 'productos', 'reservas'] loop
        execute format('alter table public.%I enable row level security', tabla);
        execute format('drop policy if exists smartstore_test_all on public.%I', tabla);
        execute format(
            'create policy smartstore_test_all on public.%I for all to anon, authenticated using (true) with check (true)',
            tabla
        );
    end loop;
end
$$;

grant usage on schema public to anon, authenticated;
grant select, insert, update, delete on public.usuarios to anon, authenticated;
grant select, insert, update, delete on public.sesiones_dispositivo to anon, authenticated;
grant select, insert, update, delete on public.tiendas to anon, authenticated;
grant select, insert, update, delete on public.productos to anon, authenticated;
grant select, insert, update, delete on public.reservas to anon, authenticated;
grant select on public.top_productos to anon, authenticated;
grant usage, select on all sequences in schema public to anon, authenticated;

grant execute on function public.crear_reserva(bigint, bigint, integer, bigint) to anon, authenticated;
grant execute on function public.cancelar_reservas_vencidas_rpc() to anon, authenticated;
grant execute on function public.procesar_pago_reserva_rpc(bigint, numeric, bigint) to anon, authenticated;
