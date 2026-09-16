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
    values (p_usuario_id, p_producto_id, p_cantidad, 'Reservado', p_tienda_id, now() + interval '24 hours')
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