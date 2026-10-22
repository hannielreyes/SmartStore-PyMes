# SmartStorePyMEs — Camera (Android) setup & test

Este repositorio ya incluye soporte para cámara usando `flet_camera`. Aquí están los pasos y comprobaciones para asegurarte de que la cámara funcione en Android al instalar la app.

## Resumen de lo que ya configuré

- `flet_camera` añadido a `pyproject.toml` y a `build/python-app/pyproject.toml`.
- `requirements.txt` creado con `flet` y `flet_camera`.
- Permiso de cámara añadido: `[tool.flet.android.permission] "android.permission.CAMERA" = true`.
- `utils.py` contiene la función `abrir_selector_imagen(...)` que usa `flet_camera` en Android.
- `camera_test.py` creado como ejemplo mínimo para probar captura.

## Requisitos previos

- Python 3.10+ (tu entorno actual es Python 3.12 — OK).
- `flet` y `flet_camera` instalados (se incluyen en `requirements.txt`).
- `flet` CLI instalado globalmente si vas a usar `flet build`.
- Dispositivo Android (o emulador) con cámara y USB debugging habilitado para pruebas.

## Instalación local (entorno de desarrollo)

```bash
python -m pip install -r requirements.txt
```

## Probar localmente (desktop)

Ejecuta la app de prueba de cámara (ventana Flet):

```bash
python camera_test.py
```

- Esto muestra `Camera` y un botón `Capturar`. Si la vista previa no aparece en desktop, prueba en un dispositivo móvil.

## Build para Android

Para generar y validar una APK sin publicarla ni instalarla, usa:

```powershell
.\build_and_install.ps1 -BuildOnly
```

Para publicar la actualización en Supabase e instalarla si hay un dispositivo
conectado, ejecuta `.\build_and_install.ps1` sin `-BuildOnly`.

El script valida la clave cliente de Supabase, pasa exclusiones de rutas exactas
al empaquetador de Flet y revisa `assets/app.zip` antes de publicar o instalar la
APK. La validación detiene el flujo si encuentra archivos locales/sensibles o si
faltan módulos y recursos de runtime. Si una caché de Flutter conserva una ruta
rota a una extensión local, el script la restablece al manifiesto base generado
por Flet para que el empaquetador pueda volver a registrar la extensión. También
limita Gradle a 3 GiB y un worker para reducir fallos por falta de memoria en el
equipo de compilación.

No uses `flet build apk` para una versión de distribución: ese comando directo no
ejecuta las exclusiones ni el control de seguridad de este script.

## Permisos en tiempo de ejecución

- Android 6+ requiere permisos en tiempo de ejecución. El permiso está declarado en `pyproject.toml`, pero si la app no solicita automáticamente, abre Ajustes → Apps → tu app → Permisos y habilita la Cámara.

## Uso dentro de la app

- En el código se usa la función `abrir_selector_imagen(page, callback)` (ver `utils.py`). En Android, esta función muestra el control `fc.Camera` y captura una imagen con `camera.capture_image()`.
- Por seguridad, la imagen se guarda localmente en `storage/data/temp/foto_<timestamp>.jpg` y la ruta se devuelve al `callback`.

## Troubleshooting común

- ImportError: asegúrate de ejecutar el `python` del entorno donde instalaste `flet_camera`.
- Camera preview no aparece en Android: comprobar que el dispositivo tenga cámara, y revisar `adb logcat` para ver errores nativos.

```bash
adb logcat | grep -i flet
```

- Si la app falla al empaquetar: revisa que `flet` CLI use el mismo intérprete donde `flet_camera` está instalado.

## Comprobaciones avanzadas (si algo falla)

- Verifica que `flet_camera` esté realmente incluido en el ambiente que `flet build` utiliza (a veces `flet build` apunta a otro intérprete o entorno virtual).
- Ejecuta `python -c "import flet_camera; print('OK', getattr(flet_camera,'__version__','no-version'))"` con el mismo `python` que usas para `flet build`.

## Próximos pasos si quieres que automatice más

- Añadir una pantalla de comprobación de permisos en la app (solicitar permisos en tiempo de ejecución si Flet lo permite).

## Conexion de prueba con Supabase

En desarrollo, la conexion usa la URL del proyecto y la clave cliente
`anon/public` desde variables de entorno. Para una APK, el script de release
genera una configuracion temporal que Flet compila junto con la app; el `.env`
no se distribuye. La clave cliente publicable/anon necesariamente queda
disponible en la aplicacion y no es un secreto administrativo: el acceso a los
datos debe protegerse con RLS y funciones seguras de Supabase.

En PowerShell, para probarla solo durante la sesion actual:

```powershell
$env:SMARTSTORE_SUPABASE_KEY = "PEGA_AQUI_TU_CLAVE_ANON_PUBLIC"
python check_supabase.py
```

Si la prueba funciona, mostrara `Conexion correcta`. La URL y la clave cliente
se cargan desde la configuracion local durante el desarrollo y desde la
configuracion generada para la APK.

No uses una clave `service_role`, `secret` o similar en la aplicacion.

## Migracion de la base compartida

El esquema preparado para Supabase esta en `supabase_schema.sql`. Ejecutalo desde `SQL Editor` de Supabase antes de cambiar la aplicacion a la base central.

La aplicacion aun conserva SQLite durante esta etapa para no mezclar datos ni perder informacion. Cuando el esquema este creado, se migrara la capa `database.py` a una API central y se exportaran los datos existentes.
- Incluir logs de `adb` o un script de CI que valide la inclusión de `flet_camera` en el build.

## Estado de seguridad y pendientes

La aplicacion ya incluye bcrypt para las contrasenas y tokens locales
revocables. La recuperacion permite validar por separado el codigo de sesion
o un codigo de un solo uso enviado por Supabase Auth. Cualquiera de los dos
permite establecer una contrasena nueva y luego iniciar sesion. La opcion de
codigo de sesion actualiza Supabase Auth mediante una Edge Function; la clave
administrativa solo se usa en el servidor y nunca se incluye en la app.

### Despliegue de recuperación por código de sesión

Desde la raíz del proyecto, vincula Supabase y despliega la función:

```powershell
supabase link --project-ref TU_PROJECT_REF
supabase functions deploy smartstore-session-recovery
```

La función utiliza `SUPABASE_SERVICE_ROLE_KEY` del entorno seguro de Supabase
Edge Functions. No copies esa clave a `.env`, a la app ni a la APK.

### Archivo de pruebas

`supabase_test_policies.sql` es exclusivamente temporal. Se usa para probar la
app mientras el login propio y las pantallas terminan de migrarse. Su politica
`using (true)` permite acceso amplio a `anon`, por lo que una persona que
modifique la APK podria intentar leer o cambiar datos de otras cuentas. No debe
ejecutarse en produccion ni en un proyecto con datos reales.

### Pendientes antes de produccion

1. Ejecutar `supabase_security_migration.sql` una sola vez.
2. Crear una cuenta nueva desde la app y verificar que `usuarios.auth_user_id`
	tenga un UUID.
3. Probar login, cierre, reapertura automatica y revocacion del token.
4. Desplegar `smartstore-session-recovery` para habilitar la recuperación con
	código de sesión.
5. En Supabase Auth, configurar la plantilla de correo de recuperación para
	incluir `{{ .Token }}`; la aplicación valida ese código antes de permitir
	cambiar la contraseña.
6. Decidir el tratamiento de cuentas antiguas sin `auth_user_id`; no borrarlas
	automaticamente.
7. Ejecutar una copia de seguridad y probar con cuentas compradora y vendedora.
8. Ejecutar `supabase_production_rls.sql` solo despues de completar los pasos
	anteriores.
9. Confirmar que la APK usa `anon/public` y nunca `service_role`.

Si una prueba falla despues de activar RLS, no se debe volver a poner
`using (true)` en produccion. Hay que revisar el JWT, `auth_user_id` y la
politica concreta que rechazo la operacion.

---

Si quieres, procedo a:
- añadir la verificación de permisos en la app (si confirmas que `flet` tiene API para solicitar permisos en runtime), o
- crear un script `build_and_install.sh`/`.ps1` para automatizar build + instalación en el dispositivo.

## Estructuras de datos aplicadas en la aplicación

- **Listas:** agrupan productos, tiendas, reservas, entregas y alertas para que la interfaz pueda recorrerlas y mostrarlas. Los diccionarios conservan los datos del usuario y el contexto que necesita la interfaz.
- **Dataclasses:** `database/models.py` define registros tipados para cuentas, productos, tiendas, reservas, entregas, alertas y ventas diarias. Las consultas de dominio los devuelven como objetos; el formulario de creación también representa sus productos pendientes con un dataclass.
- **Búsqueda lineal:** `services/busqueda_lineal.py` recorre la lista de productos candidatos y compara sus nombres sin distinguir mayúsculas. La consulta a la base de datos limita primero los candidatos para no cargar todo el catálogo en memoria.
- **Cola:** `services/cola_tareas.py` usa `queue.Queue` y una tarea tipada con `dataclass` para registrar en segundo plano las búsquedas sin resultados, sin bloquear la interfaz.
