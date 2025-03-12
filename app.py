from flask import Flask, request, jsonify
from pdf_utils import extract_pdf_data, extraer_datos_de_pdf_con_plantilla, guardar_plantilla, obtener_plantilla_por_id
from db import crear_tabla
import os
from flask_cors import CORS  # Importa el paquete CORS

app = Flask(__name__)

# Crear la tabla al iniciar la aplicación si no existe
crear_tabla()
CORS(app)  

@app.route("/extract_data", methods=["POST"])
def extract_data():
    file = request.files.get('file')

    if not file or file.filename == "":
        return jsonify({"error": "No se envió un archivo válido"}), 400

    try:
        # Leer los datos binarios del archivo PDF
        pdf_data = file.read()

        # Extraer datos del PDF sin plantilla (función general)
        extracted_data = extract_pdf_data(pdf_data)

        return jsonify({"data": extracted_data})

    except Exception as e:
        # Agregar un log de error más detallado
        print(f"Error al procesar el archivo: {str(e)}")  # Esto se verá en la consola del servidor
        return jsonify({"error": f"Error al procesar el archivo: {str(e)}"}), 500


@app.route('/extraer-datos-plantilla', methods=['POST'])
def extraer_datos_con_plantilla_route():
    """
    Ruta dedicada a extraer datos del PDF utilizando una plantilla específica.
    """
    file = request.files.get('file')
    plantilla_id = request.form.get('plantilla_id')

    if not file or file.filename == "" or not plantilla_id:
        return jsonify({"error": "No se envió un archivo válido o plantilla ID"}), 400

    try:
        # Leer los datos binarios del archivo PDF
        pdf_data = file.read()

        # Obtener la plantilla desde la base de datos usando el ID
        plantilla = obtener_plantilla_por_id(plantilla_id)

        if not plantilla:
            return jsonify({"error": "Plantilla no encontrada"}), 404

        # Extraer datos utilizando la plantilla
        datos_extraidos = extraer_datos_de_pdf_con_plantilla(
            pdf_data, plantilla)

        return jsonify({"data": datos_extraidos})

    except Exception as e:
        return jsonify({"error": f"Error al procesar el archivo con plantilla: {str(e)}"}), 500


@app.route('/crear-plantilla', methods=['POST'])
def crear_plantilla_route():
    nombre = request.json.get('nombre')
    descripcion = request.json.get('descripcion')
    datos = request.json.get('datos')

    # Validación básica
    if not nombre or not descripcion or not datos:
        return jsonify({"error": "Faltan datos para crear la plantilla"}), 400

    try:
        # Guardar plantilla en la base de datos
        guardar_plantilla(nombre, descripcion, datos)
        return jsonify({"mensaje": "Plantilla creada exitosamente"}), 201
    except Exception as e:
        # Manejo de errores
        return jsonify({"error": f"Hubo un problema al crear la plantilla: {str(e)}"}), 500

if __name__ == '__main__':
    crear_tabla()  # Crear las tablas si no existen
    app.run(debug=True, port=5000)
