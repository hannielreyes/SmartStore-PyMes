from flask import Flask, request, jsonify
import database as db

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    # Recibe eventos de PayPal y actualiza el estado del pedido correspondiente.
    try:
        data = request.get_json()
        event_type = data.get('event_type', '')

        if event_type == 'PAYMENT.CAPTURE.COMPLETED':
            resource = data.get('resource', {})

            # Intentar obtener el order_id desde supplementary_data (ruta correcta de PayPal)
            order_id = None
            supplementary = resource.get('supplementary_data', {})
            related_ids = supplementary.get('related_ids', {})
            order_id = related_ids.get('order_id')

            # Fallback: intentar desde invoice_id (por compatibilidad)
            if not order_id:
                order_id = resource.get('invoice_id')

            if order_id:
                db.actualizar_estado_pago(order_id)
                print(f"✅ Webhook: Pago procesado para orden {order_id}")
                return jsonify({'status': 'ok'}), 200
            else:
                print("⚠️ Webhook: No se encontró order_id en el evento")
                return jsonify({'status': 'missing_order_id'}), 400

        return jsonify({'status': 'ignored'}), 200

    except Exception as e:
        print(f"❌ Webhook error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
#flet build apk --arch arm64-v8a