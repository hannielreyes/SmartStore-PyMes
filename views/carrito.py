import flet as ft
import os

import database as db
from database.conexion import SupabaseNoDisponible
from database.models import ReservaCliente
from utils import abrir_url_en_background, configurar_retroceso, mostrar_snackbar

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "").strip()
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "").strip()


def _dialogo_codigo(page, codigo):
    def copiar(_):
        page.run_task(page.clipboard.set, codigo)
        mostrar_snackbar(page, "Código copiado.", color="#1B5E20")

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("¡Pago confirmado!", weight=ft.FontWeight.BOLD),
        content=ft.Column(
            [
                ft.Text("Guarda este código y muéstralo en la tienda al retirar tu compra."),
                ft.Text(codigo, size=24, weight=ft.FontWeight.BOLD, color="#0A2540"),
            ],
            tight=True,
        ),
        actions=[ft.TextButton("Copiar código", on_click=copiar), ft.TextButton("Entendido", on_click=lambda e: (setattr(dlg, "open", False), page.update()))],
    )
    page.overlay.append(dlg)
    dlg.open = True
    page.update()


def iniciar_pago_reserva(page, reserva_id, tienda_id, total, go_back):
    """Paga directamente después de apartar stock; retiene el artículo 10 minutos."""
    try:
        tienda = db.obtener_tienda_por_id(tienda_id)
        if tienda:
            from database.models import Tienda
            tienda = tienda if isinstance(tienda, Tienda) else Tienda.desde_fila(tienda)
        paypal_email = db.obtener_paypal_email(tienda.usuario_id) if tienda else None
    except SupabaseNoDisponible:
        mostrar_snackbar(
            page,
            "La reserva necesita internet para continuar al pago. El stock se liberará al vencer el plazo.",
            color="#8A4B08",
            duracion=6000,
        )
        return

    def finalizar():
        ok, mensaje, codigo = db.procesar_pago_reserva(reserva_id, total, tienda_id)
        if ok:
            mostrar_snackbar(page, "Pago confirmado. Tu código de retiro está listo.", color="#1B5E20")
            _dialogo_codigo(page, codigo)
        else:
            mostrar_snackbar(page, mensaje, color="#B3261E")

    if not paypal_email:
        db.eliminar_reserva(reserva_id)
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Pago no disponible"),
            content=ft.Text("La tienda todavía no tiene una cuenta PayPal vinculada. Se liberó el producto."),
            actions=[ft.TextButton("Entendido", on_click=lambda e: (setattr(dlg, "open", False), page.update(), go_back()))],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()
        return

    simulacion_permitida = os.getenv("SMARTSTORE_PAGO_SIMULADO", "false").lower() == "true"
    try:
        if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
            raise RuntimeError("Configura PAYPAL_CLIENT_ID y PAYPAL_CLIENT_SECRET en .env")
        from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment
        from paypalcheckoutsdk.orders import OrdersCreateRequest, OrdersCaptureRequest
        client = PayPalHttpClient(SandboxEnvironment(client_id=PAYPAL_CLIENT_ID, client_secret=PAYPAL_CLIENT_SECRET))
        request = OrdersCreateRequest()
        request.prefer("return=representation")
        request.body = {
            "intent": "CAPTURE",
            "purchase_units": [{"amount": {"currency_code": "USD", "value": str(round(total / 36.5, 2))}, "payee": {"email_address": paypal_email}, "invoice_id": f"RES-{reserva_id}"}],
            "application_context": {"return_url": "https://example.com/return", "cancel_url": "https://example.com/cancel"},
        }
        response = client.execute(request)
        order_id = response.result.id
        db.guardar_order_id(reserva_id, order_id)
        approval_url = next((link.href for link in response.result.links if link.rel == "approve"), None)
    except Exception:
        approval_url = None
        client = None

    def verificar(_):
        if client is None:
            mostrar_snackbar(page, "No se pudo conectar con PayPal. Cancela y vuelve a intentar.", color="#B3261E")
            return
        try:
            pago_vigente = db.reserva_pago_vigente(reserva_id)
        except SupabaseNoDisponible:
            mostrar_snackbar(page, "Verificar o completar el pago requiere conexión.", color="#B3261E")
            return
        if not pago_vigente:
            try:
                db.cancelar_reservas_vencidas()
            except SupabaseNoDisponible:
                mostrar_snackbar(page, "No se pudo comprobar el vencimiento; inténtalo con conexión.", color="#B3261E")
                return
            mostrar_snackbar(page, "El tiempo de pago terminó. No se cobró y el producto volvió a estar disponible.", color="#8A4B08", duracion=6000)
            dlg.open = False
            page.update()
            return
        try:
            capture = client.execute(OrdersCaptureRequest(order_id))
            if capture.status_code in (200, 201):
                finalizar()
                dlg.open = False
                page.update()
            else:
                mostrar_snackbar(page, "PayPal todavía no confirma el pago.", color="#8A4B08")
        except Exception:
            mostrar_snackbar(page, "PayPal aún no confirma el pago. Completa el proceso y vuelve a verificar.", color="#8A4B08")

    def cancelar(_):
        try:
            eliminada = db.eliminar_reserva(reserva_id)
        except SupabaseNoDisponible:
            eliminada = False
        if not eliminada:
            mostrar_snackbar(page, "Cancelar la reserva y liberar el stock requiere conexión.", color="#B3261E")
            return
        dlg.open = False
        page.update()
        go_back()

    acciones = [ft.TextButton("Cancelar y liberar producto", on_click=cancelar)]
    if approval_url:
        acciones.extend([ft.ElevatedButton("Abrir PayPal", on_click=lambda e: abrir_url_en_background(page, approval_url)), ft.ElevatedButton("Verificar pago", on_click=verificar)])
    elif simulacion_permitida:
        acciones.append(ft.ElevatedButton("Pago de prueba", on_click=lambda e: (finalizar(), setattr(dlg, "open", False), page.update())))
    else:
        db.eliminar_reserva(reserva_id)
        mostrar_snackbar(page, "PayPal no está configurado. La reserva temporal se canceló y el stock fue liberado.", color="#B3261E", duracion=6000)
        return
    dlg = ft.AlertDialog(modal=True, title=ft.Text("Completa el pago"), content=ft.Text(f"Total: C${total:.2f}. El producto queda apartado por 10 minutos."), actions=acciones)
    page.overlay.append(dlg)
    dlg.open = True
    page.update()


def carrito_view(page: ft.Page, usuario, go_back):
    configurar_retroceso(page, lambda: go_back(usuario))
    page.clean()
    page.bgcolor = "#FFFFFF"
    error_carga = None
    try:
        db.cancelar_reservas_vencidas()
    except RuntimeError as exc:
        error_carga = str(exc)
    lista = ft.Column(spacing=10, scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True), expand=True)
    total_text = ft.Text("Total: C$0.00 / $0.00", weight=ft.FontWeight.BOLD)
    try:
        filas = db.obtener_reservas_usuario(usuario["id"])
    except RuntimeError as exc:
        filas = []
        error_carga = str(exc)
    total_c = total_d = 0.0
    for fila in filas:
        compra = fila if isinstance(fila, ReservaCliente) else ReservaCliente.desde_fila(fila)
        subtotal_c = float(compra.precio_cordobas or 0) * compra.cantidad
        subtotal_d = float(compra.precio_dolares or 0) * compra.cantidad
        total_c += subtotal_c
        total_d += subtotal_d
        codigo = compra.codigo_retiro
        codigo_view = ft.Row([ft.Text(f"Código de retiro: {codigo}", weight=ft.FontWeight.BOLD), ft.IconButton(ft.Icons.COPY, tooltip="Copiar", on_click=lambda e, c=codigo: (page.run_task(page.clipboard.set, c), mostrar_snackbar(page, "Código copiado.", color="#1B5E20")))]) if codigo else ft.Text("Entrega completada")
        lista.controls.append(ft.Container(content=ft.Column([ft.Text(f"{compra.producto or 'Producto'} × {compra.cantidad}", weight=ft.FontWeight.BOLD), ft.Text(f"Total: C${subtotal_c:.2f} / ${subtotal_d:.2f}"), ft.Text(f"Estado: {compra.estado}"), codigo_view], spacing=5), bgcolor="#FFFFFF", border_radius=12, padding=12))
    if error_carga and ("42703" in error_carga or "migración" in error_carga.lower()):
        lista.controls.append(
            ft.Text(
                "Falta actualizar el esquema de Supabase. Ejecuta "
                "supabase_checkout_retiro_migration.sql en SQL Editor y vuelve a abrir Mis Compras.",
                color="#B45309",
                text_align=ft.TextAlign.CENTER,
            )
        )
    elif error_carga:
        lista.controls.append(ft.Text("No se pudieron cargar tus compras porque Supabase no está disponible.", color="#B45309", text_align=ft.TextAlign.CENTER))
    elif not filas:
        lista.controls.append(
            ft.Text(
                "Aún no tienes compras pagadas.",
                size=17,
                weight=ft.FontWeight.BOLD,
                color="#0F0101",
            )
        )
    total_text.value = f"Total: C${total_c:.2f} / ${total_d:.2f}"
    btn_volver_menu = ft.ElevatedButton(
        "↩️ Volver al Menú",
        on_click=lambda e: go_back(usuario),
    )
    resumen = ft.Column(
        [total_text, btn_volver_menu],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10,
    )
    contenido = ft.Column(
        [
            ft.Text("Mis Compras", size=28, weight=ft.FontWeight.BOLD, color="#040D4A"),
            lista,
            resumen,
        ],
        expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.START,
        spacing=12,
    )
    fondo = ft.Container(
        expand=True,
        image=ft.DecorationImage(src="fondopro.png", fit="cover"),
    )
    panel = ft.Container(
        content=contenido,
        padding=20,
        alignment=ft.Alignment(0, 0),
        expand=True,
    )
    page.add(ft.Stack([fondo, ft.SafeArea(panel)], expand=True))
