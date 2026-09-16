-- POLITICAS TEMPORALES SOLO PARA PRUEBAS LOCALES.
-- Permiten que la app de prueba use la clave publishable/anon directamente.
-- NO usar asi en produccion: la autenticacion propia de SmartStore aun no usa JWT.

do $$
declare
    tabla text;
begin
    foreach tabla in array array['usuarios', 'tiendas', 'productos', 'reservas', 'resenas'] loop
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
grant select, insert, update, delete on public.tiendas to anon, authenticated;
grant select, insert, update, delete on public.productos to anon, authenticated;
grant select, insert, update, delete on public.reservas to anon, authenticated;
grant select, insert, update, delete on public.resenas to anon, authenticated;
grant usage, select on all sequences in schema public to anon, authenticated;

grant execute on function public.crear_reserva(bigint, bigint, integer, bigint) to anon, authenticated;
grant execute on function public.cancelar_reservas_vencidas_rpc() to anon, authenticated;
grant execute on function public.procesar_pago_reserva_rpc(bigint, numeric, bigint) to anon, authenticated;
