import re
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, render_template
import os

app = Flask(__name__)

def extraer_texto(pdf_path):
    doc = fitz.open(stream=pdf_path, filetype="pdf")
    texto = "\n".join([pagina.get_text("text", sort=True) for pagina in doc])

    # Expresiones regulares mejoradas
    regex_cuit = r"\b(?:C\.U\.I\.T[:\s]*)?(30|20|27)[-]?\d{2}[-]?\d{6}[-]?\d\b"
    regex_fecha = r"\b(\d{2}/\d{2}/\d{4})\b"
    regex_numero_factura = r"(?:N[°ºo]?[°º]?\s*|Factura\s*N[°ºo]?\s*)?(\d{6,})"
    regex_importes = r"\b\d+(?:[.,]\d{2,})\b"

    # Extracción de datos
    cuit = re.search(regex_cuit, texto)
    cuit_numero = cuit.group(0) if cuit else None

    # Limpiar prefijo "C.U.I.T: " si existe
    if cuit_numero:
        cuit_numero = re.sub(r"[^\d]", "", cuit_numero)  # Elimina todo excepto números y guiones

    fecha = re.search(regex_fecha, texto)
    numero_factura = re.search(regex_numero_factura, texto)
    importes = re.findall(regex_importes, texto)

    print(importes)
    importes_numericos = []
    for i in importes:
        try:
            importes_numericos.append(float(i))
        except ValueError:
            continue  # Si no se puede convertir, lo ignora

    # Filtrar el valor más alto (el total)
    total = max(importes_numericos) if importes_numericos else 0.0

    # Resultado final
    datos_extraidos = {
        "CUIT": cuit_numero,
        "Fecha": fecha.group(1) if fecha else None,
        "Número de Factura": numero_factura.group(1) if numero_factura else None,
        "Importe Total": total,
    }

    return datos_extraidos


@app.route('/', methods=['GET', 'POST'])
def index():
    """Interfaz web con formulario de carga"""
    if request.method == 'POST':
        if 'pdf_file' not in request.files:
            return "No se subió ningún archivo", 400

        pdf_file = request.files['pdf_file']
        if pdf_file.filename == '':
            return "Nombre de archivo vacío", 400

        # Leer el archivo directamente en memoria
        pdf_bytes = pdf_file.read()
        extracted_data = extraer_texto(pdf_bytes)

        return render_template('index.html', data=extracted_data)

    return render_template('index.html', data=None)

@app.route('/extraer-general', methods=['POST'])
def extraer_datos():
    """Endpoint API para extraer datos del PDF"""
    archivo = request.files.get('file')
    if not archivo or archivo.filename == "":
        return jsonify({"error": "No se envió ningún archivo válido"}), 400

    pdf_bytes = archivo.read()
    datos = extraer_texto(pdf_bytes)

    return jsonify(datos)

if __name__ == '__main__':
    app.run(debug=True, port=5000)