-- Ejecutar una vez en Supabase > SQL Editor.
-- Reemplaza la tabla heredada de reseñas por una vista dinámica de popularidad.
drop table if exists public.resenas;

create or replace view public.top_productos with (security_barrier = true) as
select
    p.id,
    p.nombre,
    p.precio_cordobas,
    p.precio_dolares,
    p.stock,
    count(r.id)::integer as compras,
    least(5, 1 + ((count(r.id)::integer - 2) / 2))::integer as estrellas_popularidad
from public.productos p
join public.reservas r on r.producto_id = p.id and r.estado = 'Pagado'
group by p.id
having count(r.id) >= 3;

grant select on public.top_productos to anon, authenticated;
