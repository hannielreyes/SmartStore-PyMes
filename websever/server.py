import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import uuid

app = Flask(__name__)
CORS(app)  # Permite que la web y Flet se comuniquen con el servidor

# Configuración
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB máximo
# Configuración del servidor web: carpeta de imágenes y límite de subida.

# ==========================================
# RUTAS DE LA API
# ==========================================

@app.route('/')
def index():
    """Sirve la página web de la galería"""
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'static'), 'index.html')

@app.route('/upload', methods=['POST'])
def upload_image():
    """Recibe una imagen subida desde la web"""
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No se envió ninguna imagen'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
        
        # Generar nombre único para la imagen
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = uuid.uuid4().hex[:8]
        filename = f"img_{timestamp}_{unique_id}.jpg"
        
        # Guardar la imagen
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        return jsonify({
            'success': True,
            'message': 'Imagen subida correctamente',
            'filename': filename,
            'url': f'/static/uploads/{filename}'
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/images', methods=['GET'])
def get_images():
    """Devuelve la lista de imágenes disponibles en la galería"""
    try:
        images = []
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')):
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                images.append({
                    'filename': filename,
                    'url': f'/static/uploads/{filename}',
                    'size': os.path.getsize(filepath),
                    'last_modified': os.path.getmtime(filepath)
                })
        
        # Ordenar por fecha de modificación (más reciente primero)
        images.sort(key=lambda x: x['last_modified'], reverse=True)
        
        return jsonify({
            'success': True,
            'count': len(images),
            'images': images
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/static/uploads/<filename>', methods=['GET'])
def get_image(filename):
    """Sirve una imagen específica desde la carpeta de uploads"""
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        return jsonify({'error': 'Imagen no encontrada'}), 404

@app.route('/clear', methods=['DELETE'])
def clear_images():
    """Elimina todas las imágenes de la galería (opcional)"""
    try:
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(filepath):
                os.remove(filepath)
        return jsonify({'success': True, 'message': 'Galería limpiada'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================================
# INICIAR EL SERVIDOR
# ==========================================

if __name__ == '__main__':
    # Obtener la IP local para mostrar al usuario
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print("=" * 50)
    print("📸 GALERÍA WEB - SERVIDOR FLASK")
    print("=" * 50)
    print(f"✅ Servidor corriendo en:")
    print(f"   • Local: http://127.0.0.1:5000")
    print(f"   • Red:   http://{local_ip}:5000")
    print("=" * 50)
    print("📌 Para subir imágenes, abre la URL en tu navegador.")
    print("📌 Para detener el servidor, presiona Ctrl+C.")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=True)