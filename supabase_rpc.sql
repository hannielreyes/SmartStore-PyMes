-- Funciones transaccionales para reservas y pagos compartidos.
-- Ejecutar despues de supabase_schema.sql en Supabase SQL Editor.

create or replace function public.crear_reserva(
    p_usuario_id bigint,
    p_producto_id bigint,
    p_cantidad integer,
    p_tienda_id bigint
) returns jsonb language plpgsql security definer set search_path = public as $$
declare
    v_tienda_id bigint;
    v_reserva_id bigint;
begin
    if p_cantidad <= 0 then
        return jsonb_build_object('ok', false, 'message', 'La cantidad debe ser positiva');
    end if;

    select tienda_id into v_tienda_id
    from productos where id = p_producto_id for update;
    if v_tienda_id is null or v_tienda_id <> p_tienda_id then
        return jsonb_build_object('ok', false, 'message', 'El producto no pertenece a esa tienda');
    end if;

    update productos set stock = stock - p_cantidad
    where id = p_producto_id and stock >= p_cantidad;
    if not found then
        return jsonb_build_object('ok', false, 'message', 'No hay suficiente stock disponible');
    end if;

    insert into reservas (usuario_id, producto_id, cantidad, estado, tienda_id, fecha_expiracion)
    values (p_usuario_id, p_producto_id, p_cantidad, 'Reservado', p_tienda_id, now() + interval '10 minutes')
    returning id into v_reserva_id;

    return jsonb_build_object('ok', true, 'message', 'Reserva creada', 'id', v_reserva_id);
end;
$$;

create or replace function public.cancelar_reservas_vencidas_rpc()
returns integer language plpgsql security definer set search_path = public as $$
declare v_total integer;
begin
    with vencidas as (
        select id, producto_id, cantidad from reservas
        where estado = 'Reservado' and fecha_expiracion is not null and fecha_expiracion <= now()
        for update
    ), devuelto as (
        update productos p set stock = p.stock + v.cantidad
        from vencidas v where p.id = v.producto_id returning v.id
    )
    update reservas r set estado = 'Vencido'
    where r.id in (select id from vencidas) and r.estado = 'Reservado';
    get diagnostics v_total = row_count;
    return coalesce(v_total, 0);
end;
$$;

create or replace function public.procesar_pago_reserva_rpc(
    p_reserva_id bigint, p_monto numeric, p_tienda_id bigint
) returns jsonb language plpgsql security definer set search_path = public as $$
declare v_tienda_id bigint; v_estado text;
begin
    select estado, tienda_id into v_estado, v_tienda_id from reservas where id = p_reserva_id for update;
    if v_estado is null then return jsonb_build_object('ok', false, 'message', 'Reserva no encontrada'); end if;
    if v_estado <> 'Reservado' then return jsonb_build_object('ok', false, 'message', 'La reserva ya fue procesada'); end if;
    if v_tienda_id <> p_tienda_id then return jsonb_build_object('ok', false, 'message', 'La tienda no coincide'); end if;
    update reservas set estado = 'Pagado' where id = p_reserva_id;
    update tiendas set saldo = saldo + p_monto where id = p_tienda_id;
    return jsonb_build_object('ok', true, 'message', 'Pago procesado');
end;
$$;
-- Actualiza checkout directo y retiro. Idempotente junto al archivo de migración.

-- SmartStore: checkout directo, apartados breves y códigos de retiro.
-- Ejecutar una vez en Supabase SQL Editor después del esquema base.

alter table public.reservas add column if not exists codigo_retiro text;
alter table public.reservas add column if not exists codigo_retiro_usado_en timestamptz;
alter table public.reservas add column if not exists fecha_expiracion timestamptz;
create unique index if not exists idx_reservas_codigo_retiro
    on public.reservas(codigo_retiro) where codigo_retiro is not null;
create index if not exists idx_reservas_expiracion on public.reservas(fecha_expiracion);

-- Los apartados activos anteriores a esta migración también vencen en diez minutos.
update public.reservas
set fecha_expiracion = least(coalesce(fecha_expiracion, fecha + interval '10 minutes'), fecha + interval '10 minutes')
where estado = 'Reservado';

create or replace function public.crear_reserva(
    p_usuario_id bigint, p_producto_id bigint, p_cantidad integer, p_tienda_id bigint
) returns jsonb language plpgsql security definer set search_path = public as $$
declare v_tienda_id bigint; v_id bigint;
begin
    if p_cantidad <= 0 then return jsonb_build_object('ok', false, 'message', 'La cantidad debe ser positiva'); end if;
    if not exists (select 1 from usuarios where id = p_usuario_id and auth_user_id = auth.uid()) then
        return jsonb_build_object('ok', false, 'message', 'No se pudo validar la sesión.');
    end if;
    perform public.cancelar_reservas_vencidas_rpc();
    select tienda_id into v_tienda_id from productos where id = p_producto_id for update;
    if v_tienda_id is null or v_tienda_id <> p_tienda_id then
        return jsonb_build_object('ok', false, 'message', 'El producto no pertenece a esa tienda');
    end if;
    update productos set stock = stock - p_cantidad where id = p_producto_id and stock >= p_cantidad;
    if not found then
        if exists (select 1 from reservas where producto_id = p_producto_id and estado = 'Reservado' and fecha_expiracion > now()) then
            return jsonb_build_object('ok', false, 'message', 'Otra persona está completando su pago. Te avisaremos si el producto vuelve a estar disponible.');
        end if;
        return jsonb_build_object('ok', false, 'message', 'El producto ya no tiene suficiente stock disponible.');
    end if;
    insert into reservas(usuario_id, producto_id, cantidad, estado, tienda_id, fecha_expiracion)
    values(p_usuario_id, p_producto_id, p_cantidad, 'Reservado', p_tienda_id, now() + interval '10 minutes') returning id into v_id;
    return jsonb_build_object('ok', true, 'message', 'Reserva creada', 'id', v_id);
end $$;

create or replace function public.cancelar_reservas_vencidas_rpc()
returns integer language plpgsql security definer set search_path = public as $$
declare v_total integer;
begin
    with vencidas as (
        select id, producto_id, cantidad from reservas
        where estado = 'Reservado' and fecha_expiracion <= now() for update skip locked
    ), devuelto as (
        update productos p set stock = p.stock + v.cantidad from vencidas v
        where p.id = v.producto_id returning v.id
    )
    update reservas r set estado = 'Vencido' where r.id in (select id from vencidas) and r.estado = 'Reservado';
    get diagnostics v_total = row_count;
    return coalesce(v_total, 0);
end $$;

drop function if exists public.procesar_pago_reserva_rpc(bigint, numeric, bigint);
create or replace function public.procesar_pago_reserva_rpc(
    p_reserva_id bigint, p_monto numeric, p_tienda_id bigint, p_codigo_retiro text
) returns jsonb language plpgsql security definer set search_path = public as $$
declare v_reserva reservas%rowtype; v_usuario bigint;
begin
    select id into v_usuario from usuarios where auth_user_id = auth.uid();
    select * into v_reserva from reservas where id = p_reserva_id for update;
    if v_reserva.id is null or v_reserva.usuario_id is distinct from v_usuario then
        return jsonb_build_object('ok', false, 'message', 'Compra no encontrada.');
    end if;
    if v_reserva.estado <> 'Reservado' or v_reserva.fecha_expiracion <= now() then
        if v_reserva.estado = 'Reservado' then
            update productos set stock = stock + v_reserva.cantidad where id = v_reserva.producto_id;
            update reservas set estado = 'Vencido' where id = p_reserva_id;
        end if;
        return jsonb_build_object('ok', false, 'message', 'El apartado venció; el producto volvió a estar disponible.');
    end if;
    if v_reserva.tienda_id is distinct from p_tienda_id or length(p_codigo_retiro) < 10 then
        return jsonb_build_object('ok', false, 'message', 'Los datos de la compra no coinciden.');
    end if;
    update reservas set estado = 'Pagado', codigo_retiro = p_codigo_retiro where id = p_reserva_id;
    update tiendas set saldo = saldo + p_monto where id = p_tienda_id;
    return jsonb_build_object('ok', true, 'message', 'Pago procesado');
end $$;

create or replace function public.obtener_estado_disponibilidad_producto_rpc(p_producto_id bigint)
returns jsonb language plpgsql security definer set search_path = public as $$
declare v_stock integer;
begin
    perform public.cancelar_reservas_vencidas_rpc();
    select stock into v_stock from productos where id = p_producto_id;
    if v_stock is null then return jsonb_build_object('estado', 'no_disponible'); end if;
    if v_stock > 0 then return jsonb_build_object('estado', 'disponible'); end if;
    if exists(select 1 from reservas where producto_id = p_producto_id and estado = 'Reservado' and fecha_expiracion > now()) then
        return jsonb_build_object('estado', 'en_proceso');
    end if;
    return jsonb_build_object('estado', 'no_disponible');
end $$;

create or replace function public.cancelar_reserva_compra_rpc(p_reserva_id bigint)
returns jsonb language plpgsql security definer set search_path = public as $$
declare v_reserva reservas%rowtype; v_usuario bigint;
begin
    select id into v_usuario from usuarios where auth_user_id = auth.uid();
    select * into v_reserva from reservas where id = p_reserva_id for update;
    if v_reserva.id is null or v_reserva.usuario_id is distinct from v_usuario or v_reserva.estado <> 'Reservado' then return jsonb_build_object('ok', false); end if;
    update productos set stock = stock + v_reserva.cantidad where id = v_reserva.producto_id;
    update reservas set estado = 'Cancelado' where id = p_reserva_id;
    return jsonb_build_object('ok', true);
end $$;

create or replace function public.canjear_codigo_retiro_rpc(p_tienda_id bigint, p_codigo text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare v_reserva reservas%rowtype; v_usuario bigint; v_producto text;
begin
    select id into v_usuario from usuarios where auth_user_id = auth.uid();
    if not exists(select 1 from tiendas where id = p_tienda_id and usuario_id = v_usuario) then
        return jsonb_build_object('ok', false, 'message', 'No se pudo validar el código para esta tienda.');
    end if;
    select * into v_reserva from reservas where tienda_id = p_tienda_id and codigo_retiro = upper(trim(p_codigo)) for update;
    if v_reserva.id is null then return jsonb_build_object('ok', false, 'message', 'El código no corresponde a esta tienda o ya fue utilizado.'); end if;
    if v_reserva.estado <> 'Listo para entregar' then return jsonb_build_object('ok', false, 'message', 'El pedido debe estar listo para entregar antes de canjear el código.'); end if;
    update reservas set estado = 'Entregado', fecha_entrega = now(), codigo_retiro = null, codigo_retiro_usado_en = now()
    where id = v_reserva.id and codigo_retiro = upper(trim(p_codigo)) and estado = 'Listo para entregar';
    if not found then return jsonb_build_object('ok', false, 'message', 'El código ya fue utilizado.'); end if;
    return jsonb_build_object('ok', true, 'message', 'Código confirmado. Compra pagada y entrega registrada.');
end $$;

revoke execute on function public.procesar_pago_reserva_rpc(bigint, numeric, bigint, text) from public, anon;
revoke execute on function public.crear_reserva(bigint, bigint, integer, bigint) from public, anon;
revoke execute on function public.cancelar_reservas_vencidas_rpc() from public, anon;
revoke execute on function public.obtener_estado_disponibilidad_producto_rpc(bigint) from public, anon;
revoke execute on function public.cancelar_reserva_compra_rpc(bigint) from public, anon;
revoke execute on function public.canjear_codigo_retiro_rpc(bigint, text) from public, anon;
grant execute on function public.procesar_pago_reserva_rpc(bigint, numeric, bigint, text) to authenticated;
grant execute on function public.crear_reserva(bigint, bigint, integer, bigint) to authenticated;
grant execute on function public.cancelar_reservas_vencidas_rpc() to authenticated;
grant execute on function public.obtener_estado_disponibilidad_producto_rpc(bigint) to authenticated;
grant execute on function public.cancelar_reserva_compra_rpc(bigint) to authenticated;
grant execute on function public.canjear_codigo_retiro_rpc(bigint, text) to authenticated;
-- SmartStore: checkout directo, apartados breves y códigos de retiro.
-- Ejecutar una vez en Supabase SQL Editor después del esquema base.

alter table public.reservas add column if not exists codigo_retiro text;
alter table public.reservas add column if not exists codigo_retiro_usado_en timestamptz;
alter table public.reservas add column if not exists fecha_expiracion timestamptz;
create unique index if not exists idx_reservas_codigo_retiro
    on public.reservas(codigo_retiro) where codigo_retiro is not null;
create index if not exists idx_reservas_expiracion on public.reservas(fecha_expiracion);

-- Los apartados activos anteriores a esta migración también vencen en diez minutos.
update public.reservas
set fecha_expiracion = least(coalesce(fecha_expiracion, fecha + interval '10 minutes'), fecha + interval '10 minutes')
where estado = 'Reservado';

create or replace function public.crear_reserva(
    p_usuario_id bigint, p_producto_id bigint, p_cantidad integer, p_tienda_id bigint
) returns jsonb language plpgsql security definer set search_path = public as $$
declare v_tienda_id bigint; v_id bigint;
begin
    if p_cantidad <= 0 then return jsonb_build_object('ok', false, 'message', 'La cantidad debe ser positiva'); end if;
    if not exists (select 1 from usuarios where id = p_usuario_id and auth_user_id = auth.uid()) then
        return jsonb_build_object('ok', false, 'message', 'No se pudo validar la sesión.');
    end if;
    perform public.cancelar_reservas_vencidas_rpc();
    select tienda_id into v_tienda_id from productos where id = p_producto_id for update;
    if v_tienda_id is null or v_tienda_id <> p_tienda_id then
        return jsonb_build_object('ok', false, 'message', 'El producto no pertenece a esa tienda');
    end if;
    update productos set stock = stock - p_cantidad where id = p_producto_id and stock >= p_cantidad;
    if not found then
        if exists (select 1 from reservas where producto_id = p_producto_id and estado = 'Reservado' and fecha_expiracion > now()) then
            return jsonb_build_object('ok', false, 'message', 'Otra persona está completando su pago. Te avisaremos si el producto vuelve a estar disponible.');
        end if;
        return jsonb_build_object('ok', false, 'message', 'El producto ya no tiene suficiente stock disponible.');
    end if;
    insert into reservas(usuario_id, producto_id, cantidad, estado, tienda_id, fecha_expiracion)
    values(p_usuario_id, p_producto_id, p_cantidad, 'Reservado', p_tienda_id, now() + interval '10 minutes') returning id into v_id;
    return jsonb_build_object('ok', true, 'message', 'Reserva creada', 'id', v_id);
end $$;

create or replace function public.cancelar_reservas_vencidas_rpc()
returns integer language plpgsql security definer set search_path = public as $$
declare v_total integer;
begin
    with vencidas as (
        select id, producto_id, cantidad from reservas
        where estado = 'Reservado' and fecha_expiracion <= now() for update skip locked
    ), devuelto as (
        update productos p set stock = p.stock + v.cantidad from vencidas v
        where p.id = v.producto_id returning v.id
    )
    update reservas r set estado = 'Vencido' where r.id in (select id from vencidas) and r.estado = 'Reservado';
    get diagnostics v_total = row_count;
    return coalesce(v_total, 0);
end $$;

drop function if exists public.procesar_pago_reserva_rpc(bigint, numeric, bigint);
create or replace function public.procesar_pago_reserva_rpc(
    p_reserva_id bigint, p_monto numeric, p_tienda_id bigint, p_codigo_retiro text
) returns jsonb language plpgsql security definer set search_path = public as $$
declare v_reserva reservas%rowtype; v_usuario bigint; v_monto numeric;
begin
    select id into v_usuario from usuarios where auth_user_id = auth.uid();
    select * into v_reserva from reservas where id = p_reserva_id for update;
    if v_reserva.id is null or v_reserva.usuario_id is distinct from v_usuario then
        return jsonb_build_object('ok', false, 'message', 'Compra no encontrada.');
    end if;
    if v_reserva.estado <> 'Reservado' or v_reserva.fecha_expiracion <= now() then
        if v_reserva.estado = 'Reservado' then
            update productos set stock = stock + v_reserva.cantidad where id = v_reserva.producto_id;
            update reservas set estado = 'Vencido' where id = p_reserva_id;
        end if;
        return jsonb_build_object('ok', false, 'message', 'El apartado venció; el producto volvió a estar disponible.');
    end if;
    if v_reserva.tienda_id is distinct from p_tienda_id or length(p_codigo_retiro) < 10 then
        return jsonb_build_object('ok', false, 'message', 'Los datos de la compra no coinciden.');
    end if;
    select precio_cordobas * v_reserva.cantidad into v_monto from productos where id = v_reserva.producto_id and tienda_id = p_tienda_id;
    if v_monto is null or abs(v_monto - p_monto) > 0.01 then
        return jsonb_build_object('ok', false, 'message', 'El total no coincide con el precio del producto.');
    end if;
    update reservas set estado = 'Pagado', codigo_retiro = p_codigo_retiro where id = p_reserva_id;
    update tiendas set saldo = saldo + v_monto where id = p_tienda_id;
    return jsonb_build_object('ok', true, 'message', 'Pago procesado');
end $$;

create or replace function public.obtener_estado_disponibilidad_producto_rpc(p_producto_id bigint)
returns jsonb language plpgsql security definer set search_path = public as $$
declare v_stock integer;
begin
    perform public.cancelar_reservas_vencidas_rpc();
    select stock into v_stock from productos where id = p_producto_id;
    if v_stock is null then return jsonb_build_object('estado', 'no_disponible'); end if;
    if v_stock > 0 then return jsonb_build_object('estado', 'disponible'); end if;
    if exists(select 1 from reservas where producto_id = p_producto_id and estado = 'Reservado' and fecha_expiracion > now()) then
        return jsonb_build_object('estado', 'en_proceso');
    end if;
    return jsonb_build_object('estado', 'no_disponible');
end $$;

create or replace function public.cancelar_reserva_compra_rpc(p_reserva_id bigint)
returns jsonb language plpgsql security definer set search_path = public as $$
declare v_reserva reservas%rowtype; v_usuario bigint; v_producto text;
begin
    select id into v_usuario from usuarios where auth_user_id = auth.uid();
    select * into v_reserva from reservas where id = p_reserva_id for update;
    if v_reserva.id is null or v_reserva.usuario_id is distinct from v_usuario or v_reserva.estado <> 'Reservado' then return jsonb_build_object('ok', false); end if;
    update productos set stock = stock + v_reserva.cantidad where id = v_reserva.producto_id;
    update reservas set estado = 'Cancelado' where id = p_reserva_id;
    return jsonb_build_object('ok', true);
end $$;

create or replace function public.canjear_codigo_retiro_rpc(p_tienda_id bigint, p_codigo text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare v_reserva reservas%rowtype; v_usuario bigint; v_producto text;
begin
    select id into v_usuario from usuarios where auth_user_id = auth.uid();
    if not exists(select 1 from tiendas where id = p_tienda_id and usuario_id = v_usuario) then
        return jsonb_build_object('ok', false, 'message', 'No se pudo validar el código para esta tienda.');
    end if;
    select r.* into v_reserva from reservas r
    where r.tienda_id = p_tienda_id and r.codigo_retiro = upper(trim(p_codigo)) for update of r;
    if v_reserva.id is null then return jsonb_build_object('ok', false, 'message', 'El código no corresponde a esta tienda o ya fue utilizado.'); end if;
    if v_reserva.estado <> 'Listo para entregar' then return jsonb_build_object('ok', false, 'message', 'El pedido debe estar listo para entregar antes de canjear el código.'); end if;
    select nombre into v_producto from productos where id = v_reserva.producto_id;
    update reservas set estado = 'Entregado', fecha_entrega = now(), codigo_retiro = null, codigo_retiro_usado_en = now()
    where id = v_reserva.id and codigo_retiro = upper(trim(p_codigo)) and estado = 'Listo para entregar';
    if not found then return jsonb_build_object('ok', false, 'message', 'El código ya fue utilizado.'); end if;
    return jsonb_build_object('ok', true, 'message', 'Compra pagada: ' || v_producto || '. Entrega registrada.');
end $$;

revoke execute on function public.procesar_pago_reserva_rpc(bigint, numeric, bigint, text) from public, anon;
revoke execute on function public.crear_reserva(bigint, bigint, integer, bigint) from public, anon;
revoke execute on function public.cancelar_reservas_vencidas_rpc() from public, anon;
revoke execute on function public.obtener_estado_disponibilidad_producto_rpc(bigint) from public, anon;
revoke execute on function public.cancelar_reserva_compra_rpc(bigint) from public, anon;
revoke execute on function public.canjear_codigo_retiro_rpc(bigint, text) from public, anon;
grant execute on function public.procesar_pago_reserva_rpc(bigint, numeric, bigint, text) to authenticated;
grant execute on function public.crear_reserva(bigint, bigint, integer, bigint) to authenticated;
grant execute on function public.cancelar_reservas_vencidas_rpc() to authenticated;
grant execute on function public.obtener_estado_disponibilidad_producto_rpc(bigint) to authenticated;
grant execute on function public.cancelar_reserva_compra_rpc(bigint) to authenticated;
grant execute on function public.canjear_codigo_retiro_rpc(bigint, text) to authenticated;
