-- ================================================================
-- RLS DE PRODUCCION. NO EJECUTAR TODAVIA SIN LEER TODO EL ARCHIVO.
-- ================================================================
--
-- Este archivo es el objetivo final de seguridad. Requiere que la app use
-- Supabase Auth y envie el JWT del usuario en cada consulta REST.
--
-- PRERREQUISITOS OBLIGATORIOS:
--   1. Ejecutar supabase_security_migration.sql.
--   2. Confirmar que los registros nuevos tienen auth_user_id.
--   3. Probar login, registro, cierre y reapertura de la app.
--   4. Migrar la recuperacion de contraseña a Supabase Auth.
--   5. Revisar las politicas con una cuenta de prueba compradora y otra
--      vendedora; comprobar que ninguna puede modificar datos ajenos.
--   6. Hacer una copia de seguridad antes de ejecutar este archivo.
--   7. Ejecutar supabase_checkout_retiro_migration.sql para crear las RPC
--      de pago directo, disponibilidad y canje antes de aplicar estos grants.
--
-- EFECTO PRINCIPAL:
--   * Revoca el acceso directo de anon a las tablas.
--   * Permite operaciones solo cuando auth.uid() coincide con
--     usuarios.auth_user_id.
--   * Si se ejecuta antes de terminar la migracion, el login o varias vistas
--     dejaran de funcionar. Eso es esperado y no significa que haya internet
--     caido: significa que falta completar la migracion.
--
-- NO EJECUTAR JUNTO CON supabase_test_policies.sql. El archivo de pruebas
-- vuelve a conceder acceso amplio y anula el objetivo de este archivo.

alter table public.usuarios enable row level security;
alter table public.sesiones_dispositivo enable row level security;
alter table public.tiendas enable row level security;
alter table public.productos enable row level security;
alter table public.reservas enable row level security;
alter table public.solicitudes_productos enable row level security;

drop policy if exists smartstore_test_all on public.usuarios;
drop policy if exists smartstore_test_all on public.sesiones_dispositivo;
drop policy if exists smartstore_test_all on public.tiendas;
drop policy if exists smartstore_test_all on public.productos;
drop policy if exists smartstore_test_all on public.reservas;
drop policy if exists smartstore_test_all on public.solicitudes_productos;

drop policy if exists usuarios_propios_select on public.usuarios;
drop policy if exists usuarios_propios_insert on public.usuarios;
drop policy if exists usuarios_propios_update on public.usuarios;
create policy usuarios_propios_select on public.usuarios
    for select to authenticated using (auth_user_id = auth.uid());
create policy usuarios_propios_insert on public.usuarios
    for insert to authenticated with check (auth_user_id = auth.uid());
create policy usuarios_propios_update on public.usuarios
    for update to authenticated
    using (auth_user_id = auth.uid())
    with check (auth_user_id = auth.uid());

drop policy if exists sesiones_propias on public.sesiones_dispositivo;
create policy sesiones_propias on public.sesiones_dispositivo
    for all to authenticated
    using (usuario_id in (select id from public.usuarios where auth_user_id = auth.uid()))
    with check (usuario_id in (select id from public.usuarios where auth_user_id = auth.uid()));

drop policy if exists tiendas_propias on public.tiendas;
create policy tiendas_propias on public.tiendas
    for all to authenticated
    using (usuario_id in (select id from public.usuarios where auth_user_id = auth.uid()))
    with check (usuario_id in (select id from public.usuarios where auth_user_id = auth.uid()));

drop policy if exists productos_autenticados_select on public.productos;
drop policy if exists productos_propios_write on public.productos;
create policy productos_autenticados_select on public.productos
    for select to authenticated using (true);
create policy productos_propios_write on public.productos
    for all to authenticated
    using (tienda_id in (
        select t.id from public.tiendas t
        join public.usuarios u on u.id = t.usuario_id
        where u.auth_user_id = auth.uid()
    ))
    with check (tienda_id in (
        select t.id from public.tiendas t
        join public.usuarios u on u.id = t.usuario_id
        where u.auth_user_id = auth.uid()
    ));

drop policy if exists reservas_participantes on public.reservas;
create policy reservas_participantes on public.reservas
    for select to authenticated
    using (
        usuario_id in (select id from public.usuarios where auth_user_id = auth.uid())
        or tienda_id in (
            select t.id from public.tiendas t
            join public.usuarios u on u.id = t.usuario_id
            where u.auth_user_id = auth.uid()
        )
    );
drop policy if exists reservas_comprador_insert on public.reservas;
create policy reservas_comprador_insert on public.reservas
    for insert to authenticated
    with check (usuario_id in (select id from public.usuarios where auth_user_id = auth.uid()));
drop policy if exists reservas_participantes_update on public.reservas;
create policy reservas_participantes_update on public.reservas
    for update to authenticated
    using (
        usuario_id in (select id from public.usuarios where auth_user_id = auth.uid())
        or tienda_id in (
            select t.id from public.tiendas t
            join public.usuarios u on u.id = t.usuario_id
            where u.auth_user_id = auth.uid()
        )
    );

drop policy if exists solicitudes_autenticadas on public.solicitudes_productos;
create policy solicitudes_autenticadas on public.solicitudes_productos
    for all to authenticated
    using (usuario_id in (select id from public.usuarios where auth_user_id = auth.uid()))
    with check (usuario_id in (select id from public.usuarios where auth_user_id = auth.uid()));

revoke all on public.usuarios from anon;
revoke all on public.sesiones_dispositivo from anon;
revoke all on public.tiendas from anon;
revoke all on public.productos from anon;
revoke all on public.reservas from anon;
revoke all on public.solicitudes_productos from anon;
grant select on public.top_productos to anon, authenticated;
grant select, insert, update on public.usuarios to authenticated;
grant select, insert, update, delete on public.sesiones_dispositivo, public.tiendas, public.productos, public.reservas, public.solicitudes_productos to authenticated;
revoke execute on function public.crear_reserva(bigint, bigint, integer, bigint) from anon;
revoke execute on function public.cancelar_reservas_vencidas_rpc() from anon;
revoke execute on function public.procesar_pago_reserva_rpc(bigint, numeric, bigint, text) from anon;
revoke execute on function public.obtener_estado_disponibilidad_producto_rpc(bigint) from anon;
revoke execute on function public.cancelar_reserva_compra_rpc(bigint) from anon;
revoke execute on function public.canjear_codigo_retiro_rpc(bigint, text) from anon;
grant execute on function public.crear_reserva(bigint, bigint, integer, bigint) to authenticated;
grant execute on function public.cancelar_reservas_vencidas_rpc() to authenticated;
grant execute on function public.procesar_pago_reserva_rpc(bigint, numeric, bigint, text) to authenticated;
grant execute on function public.obtener_estado_disponibilidad_producto_rpc(bigint) to authenticated;
grant execute on function public.cancelar_reserva_compra_rpc(bigint) to authenticated;
grant execute on function public.canjear_codigo_retiro_rpc(bigint, text) to authenticated;
