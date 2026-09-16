-- Ejecutar una sola vez en Supabase SQL Editor.
alter table public.productos
    add column if not exists categoria text not null default 'General';

alter table public.productos
    add column if not exists imagen_2 text;

alter table public.productos
    add column if not exists descripcion text;

alter table public.productos
    add column if not exists estado_producto text default 'Nuevo';

alter table public.productos
    add column if not exists etiquetas text;

alter table public.productos
    add column if not exists estilo text;

alter table public.productos
    add column if not exists color_principal text;

alter table public.productos
    add column if not exists material text;

alter table public.productos
    add column if not exists garantia text;

alter table public.productos
    add column if not exists especificacion text;