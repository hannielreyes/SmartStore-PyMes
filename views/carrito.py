import flet as ft
from utils import mostrar_snackbar, abrir_url_en_background, configurar_retroceso
import database as db
import warnings
import threading

warnings.filterwarnings("ignore")

# ==========================================
# 🔐 CREDENCIALES DE PAYPAL (SANDBOX)
# ==========================================
PAYPAL_CLIENT_ID = "ASMnjYjYF4YbSD1fAxe-TnXkYckH8DQdzF046Yc18Og19n1BdxVl2xfhIwFO6bekZGQM6UZiVpPLdKF4".strip()
PAYPAL_CLIENT_SECRET = "EFbw2J9jLJ0SwcSwrZioGoJDHqmYGCCHUZ0fbzPYC9x8SVaTYS0h_sXr8ro80u4E4LK3pVvTH2-TD2-8".strip()
PAYPAL_MODE = "sandbox"

PAYPAL_READY = False
client = None

try:
    from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment, LiveEnvironment
    from paypalcheckoutsdk.orders import OrdersCreateRequest, OrdersCaptureRequest, OrdersGetRequest

    if PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET:
        if PAYPAL_MODE == "sandbox":
            environment = SandboxEnvironment(
                client_id=PAYPAL_CLIENT_ID,
                client_secret=PAYPAL_CLIENT_SECRET,
            )
        else:
            environment = LiveEnvironment(
                client_id=PAYPAL_CLIENT_ID,
                client_secret=PAYPAL_CLIENT_SECRET,
            )
        client = PayPalHttpClient(environment)
        print(f"✅ PayPal configurado para entorno: {PAYPAL_MODE}")
        PAYPAL_READY = True
    else:
        print("⚠️ Credenciales PayPal incompletas")
except ImportError:
    print("⚠️ paypalcheckoutsdk no instalado. Instala: pip install paypalcheckoutsdk")
    PAYPAL_READY = False


def carrito_view(page: ft.Page, usuario, go_back):
    # PANTALLA: reservas del cliente, pagos, estados y acciones de cada pedido.
    configurar_retroceso(page, lambda: go_back(usuario))
    page.clean()
    page.bgcolor = "white"
    db.cancelar_reservas_vencidas()

    fondo = ft.Container(
        expand=True,
        image=ft.DecorationImage(src="fondopro.png", fit="cover"),
    )

    # CONTROLES: espacio desplazable donde se apilan las tarjetas de reservas.
    # El tamaño de cada tarjeta se mantiene independiente de este contenedor.
    lista = ft.Column(
        spacing=10,
        scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        height=500,
    )
    total_text = ft.Text("Total: C$0.00 / $0.00", weight=ft.FontWeight.BOLD)
    verificaciones_en_curso = set()
    verificaciones_lock = threading.Lock()

    def _ejecutar_captura_paypal(e, reserva_id, tienda_id, total):
        # ACCIÓN: verifica y captura en PayPal el pago de una reserva.
        print(f"🔄 Intentando verificar pago para reserva #{reserva_id}, tienda #{tienda_id}, total={total}...")
        order_id = db.obtener_order_id(reserva_id)
        print(f"   order_id obtenido: {order_id}")

        if not order_id:
            mostrar_snackbar(
                page,
                "⚠️ No se encontró una orden de PayPal. Toca 'Pagar con PayPal' primero.",
                color="orange",
            )
            return

        try:
            mostrar_snackbar(page, "⏳ Verificando pago con PayPal...", color="blue")

            estado_paypal = getattr(
                client.execute(OrdersGetRequest(order_id)).result,
                "status",
                None,
            )
            if estado_paypal != "APPROVED":
                mostrar_snackbar(
                    page,
                    f"⚠️ PayPal aún no aprobó la orden ({estado_paypal}). Abre 'Pagar con PayPal', completa el pago y vuelve a verificar.",
                    color="orange",
                    duracion=7000,
                )
                return

            request = OrdersCaptureRequest(order_id)
            print(f"   Enviando captura a PayPal para orden: {order_id}")
            response = client.execute(request)
            print(f"   Respuesta PayPal: status_code={response.status_code}")

            if response.status_code in (200, 201):
                print("✅ Captura exitosa! Procesando pago en BD...")
                exito, mensaje = db.procesar_pago_reserva(reserva_id, total, tienda_id)
                print(f"   Resultado BD: exito={exito}, mensaje={mensaje}")
                if exito:
                    mostrar_snackbar(
                        page,
                        "✅ Pago verificado correctamente.",
                        color="green",
                    )
                    cargar()
                else:
                    mostrar_snackbar(page, f"⚠️ {mensaje}", color="orange")
        except Exception as err:
            print(f"❌ Error en ejecutar_captura_paypal: {err}")
            if "RESOURCE_NOT_FOUND" in str(err) or "INVALID_RESOURCE_ID" in str(err):
                db.guardar_order_id(reserva_id, None)
                mostrar_snackbar(
                    page,
                    "⚠️ La orden de PayPal ya no existe. Toca 'Pagar con PayPal' para crear una nueva.",
                    color="orange",
                )
                return
            if "ORDER_NOT_APPROVED" in str(err):
                mostrar_snackbar(
                    page,
                    "⚠️ El pago aún no fue aprobado en PayPal. Completa el pago y vuelve a verificar.",
                    color="orange",
                    duracion=7000,
                )
                return
            import traceback
            traceback.print_exc()
            mostrar_snackbar(page, ft.Text(f"❌ Error al verificar: {str(err)}", color="red"))

    def ejecutar_captura_paypal(e, reserva_id, tienda_id, total):
        with verificaciones_lock:
            if reserva_id in verificaciones_en_curso:
                mostrar_snackbar(page, "⏳ Ya se está verificando esta reserva.", color="blue")
                return
            verificaciones_en_curso.add(reserva_id)
        try:
            _ejecutar_captura_paypal(e, reserva_id, tienda_id, total)
        finally:
            with verificaciones_lock:
                verificaciones_en_curso.discard(reserva_id)

    def procesar_pago_simulado(reserva_id, tienda_id, total, dlg=None):
        # ACCIÓN: procesa un pago simulado para pruebas o entornos sin PayPal.
        if dlg is not None:
            dlg.open = False
            page.update()

        try:
            exito, mensaje = db.procesar_pago_reserva(reserva_id, total, tienda_id)
            if exito:
                mostrar_snackbar(
                    page,
                    ft.Text(
                        f"✅ Pago simulado exitoso. Se agregó C${total:.2f} a la billetera.",
                        color="green",
                    ),
                    duration=4000,
                )
                cargar()
            else:
                mostrar_snackbar(page, f"⚠️ {mensaje}", color="orange")
        except Exception as e:
            mostrar_snackbar(page, f"❌ Error simulado: {str(e)}", color="red")

    def procesar_pago_real(reserva_id, tienda_id, total, paypal_email, dlg=None):
        # ACCIÓN: crea o reutiliza una orden real de PayPal.
        if dlg is not None:
            dlg.open = False
            page.update()

        try:
            estado_reserva = db.obtener_estado_reserva(reserva_id)
            if estado_reserva != "Reservado":
                mostrar_snackbar(
                    page,
                    f"✅ Esta reserva ya está en estado: {estado_reserva or 'procesado'}. No se creará otra orden.",
                    color="green",
                )
                cargar()
                return

            mostrar_snackbar(page, "⏳ Conectando con PayPal...", color="blue")

            tasa = 36.5
            total_usd = round(total / tasa, 2)

            # Reutiliza la orden pendiente para evitar crear varias órdenes
            # cuando el usuario toca el botón más de una vez.
            orden_existente = db.obtener_order_id(reserva_id)
            if orden_existente:
                try:
                    estado_orden = client.execute(OrdersGetRequest(orden_existente)).result
                    if getattr(estado_orden, "status", None) in {"CREATED", "SAVED", "APPROVED"}:
                        approval_link = f"https://www.sandbox.paypal.com/checkoutnow?token={orden_existente}"
                        print(f"ℹ️ Reutilizando orden PayPal existente: {orden_existente}")
                        abrir_url_en_background(page, approval_link)
                        mostrar_snackbar(
                            page,
                            "✅ Reabriendo el pago pendiente de PayPal. Después toca 'Verificar Pago'.",
                            color="green",
                        )
                        return
                except Exception as error_orden:
                    if "RESOURCE_NOT_FOUND" not in str(error_orden) and "INVALID_RESOURCE_ID" not in str(error_orden):
                        raise
                    print(f"⚠️ Orden PayPal inválida; se creará una nueva: {orden_existente}")
                    db.guardar_order_id(reserva_id, None)

            print(f"💳 Creando orden PayPal: reserva #{reserva_id}, C${total} = ${total_usd} USD")

            request = OrdersCreateRequest()
            request.prefer("return=representation")
            request.body = {
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "amount": {
                            "currency_code": "USD",
                            "value": str(total_usd),
                        },
                        "payee": {
                            "email_address": paypal_email,
                        },
                        "invoice_id": f"RES-{reserva_id}",
                        "description": f"Reserva #{reserva_id}",
                    }
                ],
                "application_context": {
                    "return_url": "https://example.com/return",
                    "cancel_url": "https://example.com/cancel",
                },
            }

            response = client.execute(request)
            print(f"   Respuesta PayPal: status={response.status_code}")

            if response.status_code == 201:
                order_id = response.result.id
                db.guardar_order_id(reserva_id, order_id)
                print(f"✅ Orden creada en PayPal: {order_id}")

                approval_link = None
                if hasattr(response.result, "links"):
                    for link in response.result.links:
                        if link.rel == "approve":
                            approval_link = link.href
                            break

                if approval_link:
                    print(f"🔗 URL de aprobación: {approval_link}")
                    abrir_url_en_background(page, approval_link)
                    mostrar_snackbar(
                        page,
                        "✅ Abriendo PayPal. Aprobá el pago y luego tocá 'Verificar Pago'.",
                        color="green",
                    )
                else:
                    print("❌ No se obtuvo link de aprobación")
                    mostrar_snackbar(page, "❌ No se obtuvo el enlace de aprobación. Inténtalo nuevamente 😊", color="orange")
            else:
                error_msg = f"Error {response.status_code}"
                if hasattr(response, "result") and hasattr(response.result, "message"):
                    error_msg = response.result.message
                print(f"❌ Error PayPal: {error_msg}")
                mostrar_snackbar(page, ft.Text(f"❌ Error PayPal: {error_msg}", color="orange"))
        except Exception as error:
            print(f"❌ EXCEPCIÓN en procesar_pago_real: {str(error)}")
            import traceback
            traceback.print_exc()
            mostrar_snackbar(page, ft.Text(f"❌ Error: {str(error)}", color="orange"))

    def mostrar_pago(reserva_id, tienda_id, total):
        tienda = db.obtener_tienda_por_id(tienda_id)
        if not tienda:
            mostrar_snackbar(page, "❌ No encontramos la tienda. Revisa la información e inténtalo nuevamente 😊", color="red")
            return

        usuario_id = tienda[4]
        paypal_email = db.obtener_paypal_email(usuario_id)

        if not paypal_email:
            mostrar_snackbar(page, "❌ El dueño de la tienda aún no ha vinculado PayPal 😊", color="red")
            return

        if not PAYPAL_READY:
            dlg_sim = ft.AlertDialog(
                modal=True,
                title=ft.Text("💳 Pago Simulado", size=20, weight=ft.FontWeight.BOLD, color="#0A2540"),
                content=ft.Column(
                    [
                        ft.Text(f"Total a pagar: C${total:.2f}", size=18, weight=ft.FontWeight.BOLD, color="#2E7D32"),
                        ft.Divider(height=10),
                        ft.Text("⚠️ PayPal no está configurado. Se usará un pago simulado.", size=14, color="#E65100"),
                    ],
                    spacing=8,
                    tight=True,
                ),
                actions=[
                    ft.TextButton("↩️ Cancelar", on_click=lambda e: (setattr(dlg_sim, "open", False), page.update())),
                    ft.ElevatedButton(
                        "✅ Pagar (Simulado)",
                        on_click=lambda e: procesar_pago_simulado(reserva_id, tienda_id, total, dlg_sim),
                        bgcolor="#0A2540",
                        color="white",
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.overlay.append(dlg_sim)
            dlg_sim.open = True
            page.update()
            return

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("💳 Pagar con PayPal", size=20, weight=ft.FontWeight.BOLD, color="#0A2540"),
            content=ft.Column(
                [
                    ft.Text(f"Total a pagar: C${total:.2f}", size=18, weight=ft.FontWeight.BOLD, color="#2E7D32"),
                    ft.Divider(height=10),
                    ft.Text("🔧 Entorno de PRUEBAS (Sandbox)", size=14, color="#E65100"),
                    ft.Text(f"Cuenta PayPal: {paypal_email}", size=14, color="#0A2540"),
                    ft.Divider(height=10),
                    ft.Text(
                        "Serás redirigido a PayPal para completar el pago.\n"
                        "Una vez que autorices el pago en el navegador, regresa a esta app y presiona 'Verificar Pago'.",
                        size=14,
                        color="#555555",
                    ),
                ],
                spacing=8,
                tight=True,
            ),
            actions=[
                ft.TextButton(
                    "Cancelar",
                    on_click=lambda e: (setattr(dlg, "open", False), page.update()),
                ),
                ft.ElevatedButton(
                    "✅ Ir a Pagar con PayPal",
                    on_click=lambda e: procesar_pago_real(reserva_id, tienda_id, total, paypal_email, dlg),
                    bgcolor="#0A2540",
                    color="white",
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def cancelar(rid):
        def confirmar_cancelacion(e):
            db.eliminar_reserva(rid)
            dlg.open = False
            mostrar_snackbar(page, "✅ La reserva fue cancelada y las unidades volvieron al inventario 😊", color="green")
            cargar()

        def cancelar_cancelacion(e):
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("❌ Cancelar Reserva", size=20, weight=ft.FontWeight.BOLD, color="#C62828"),
            content=ft.Text("¿Deseas cancelar esta reserva? Las unidades volverán al inventario 😊", size=14),
            actions=[
                ft.TextButton("No, mantener", on_click=cancelar_cancelacion),
                ft.ElevatedButton(
                    "✅ Eliminar Reserva",
                    on_click=confirmar_cancelacion,
                    bgcolor=ft.Colors.RED_400,
                    color="white",
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def cargar():
        lista.controls.clear()
        reservas = db.obtener_reservas_usuario(usuario["id"])
        total_c = 0.0
        total_d = 0.0

        for r in reservas:
            rid, nom, cant, pc, pd, estado, tienda_id = r
            subtotal_c = pc * cant
            subtotal_d = pd * cant

            if estado == "Reservado":
                total_c += subtotal_c
                total_d += subtotal_d

            estados_pedido = {
                "Reservado": "⏳ Pendiente de pago (aprueba PayPal y luego verifica)",
                "Pagado": "💳 Pago confirmado; la tienda debe preparar tu pedido.",
                "Preparando": "📦 Tu pedido está siendo preparado.",
                "Listo para entregar": "✅ Tu pedido está listo para entregar.",
                "Entregado": "🎉 Pedido entregado.",
                "Vencido": "⌛ Reserva vencida; el stock fue liberado.",
            }
            estado_mostrar = estados_pedido.get(estado, estado or "Estado no disponible")

            # Tarjeta de reserva: datos, estado actual y acciones disponibles.
            card = ft.Container(
                content=ft.Column(
                    [
                        ft.Text(f"{nom} x{cant}", weight=ft.FontWeight.BOLD),
                        ft.Text(f"C${pc:.2f} c/u = C${subtotal_c:.2f} / ${subtotal_d:.2f}"),
                        ft.Text(f"Estado: {estado_mostrar}", size=13, color="#555555"),
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.ElevatedButton(
                                        "Pagar con PayPal",
                                        on_click=lambda e, rid=rid, tid=tienda_id, total=subtotal_c: mostrar_pago(rid, tid, total),
                                    ) if estado == "Reservado" else ft.Container(),
                                    ft.ElevatedButton(
                                        "Verificar Pago",
                                        bgcolor="#2E7D32",
                                        color="white",
                                        on_click=lambda e, rid=rid, tid=tienda_id, total=subtotal_c: threading.Thread(
                                            target=ejecutar_captura_paypal,
                                            args=(e, rid, tid, total),
                                            daemon=True,
                                        ).start(),
                                    ) if estado == "Reservado" else ft.Container(),
                                    ft.ElevatedButton(
                                        "Cancelar",
                                        on_click=lambda e, rid=rid: cancelar(rid),
                                        bgcolor=ft.Colors.RED_400,
                                    ) if estado == "Reservado" else ft.Container(),
                                ],
                                spacing=10,
                                wrap=True,
                                scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
                            ),
                            width=300,
                        ),
                    ],
                    spacing=5,
                ),
                bgcolor=ft.Colors.WHITE,
                border_radius=15,
                padding=10,
            )
            lista.controls.append(card)

        total_text.value = f"Total: C${total_c:.2f} / ${total_d:.2f}"
        page.update()

    content = ft.Container(
        content=ft.Column(
            [
                ft.Container(height=40),
                ft.Text("Mis Reservas", size=28, weight=ft.FontWeight.BOLD, color="#040D4A"),
                ft.Text("Las reservas expiran en 24 horas", size=14, weight=ft.FontWeight.BOLD, color="#0A2540", italic=True),
                lista,
                total_text,
                ft.ElevatedButton("↩️ Volver al Menu", on_click=lambda e: go_back(usuario)),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=15,
            scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        ),
        padding=20,
    )

    cargar()
    page.add(
        ft.Stack(
            [
                fondo,
                ft.SafeArea(content),
            ],
            expand=True,
        )
    )