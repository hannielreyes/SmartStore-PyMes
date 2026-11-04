-- Impide que un usuario tenga mas de una tienda, incluso con guardados simultaneos.
-- Si ya hay usuarios con varias tiendas, primero resuelve esos duplicados y vuelve a ejecutar.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.tiendas
        WHERE usuario_id IS NOT NULL
        GROUP BY usuario_id
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION
            'Hay usuarios con varias tiendas. Resuelve los duplicados antes de aplicar esta migracion.';
    END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_tiendas_una_por_usuario
    ON public.tiendas (usuario_id)
    WHERE usuario_id IS NOT NULL;

-- Claves estables para que reintentar una sincronizacion offline no duplique filas.
ALTER TABLE public.tiendas
    ADD COLUMN IF NOT EXISTS offline_uuid uuid;
ALTER TABLE public.productos
    ADD COLUMN IF NOT EXISTS offline_uuid uuid;

CREATE UNIQUE INDEX IF NOT EXISTS idx_tiendas_offline_uuid
    ON public.tiendas (offline_uuid)
    WHERE offline_uuid IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_productos_offline_uuid
    ON public.productos (offline_uuid)
    WHERE offline_uuid IS NOT NULL;
