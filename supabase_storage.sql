-- Ejecutar una sola vez en Supabase SQL Editor.
-- Este bucket permite que las imagenes se vean desde PC y Android.
insert into storage.buckets (id, name, public)
values ('smartstore-media', 'smartstore-media', true)
on conflict (id) do update set public = true;

drop policy if exists "smartstore_media_public_read" on storage.objects;
create policy "smartstore_media_public_read"
on storage.objects for select
using (bucket_id = 'smartstore-media');

drop policy if exists "smartstore_media_anon_insert" on storage.objects;
create policy "smartstore_media_anon_insert"
on storage.objects for insert
with check (bucket_id = 'smartstore-media');