import fitz
import json
import sqlite3

# Definir los márgenes de tolerancia
MARGEN_X = 10
MARGEN_Y = 10


import fitz  # PyMuPDF

def extract_pdf_data(pdf_data):
    # Abrir el PDF directamente desde los datos binarios (en memoria)
    pdf = fitz.open(stream=pdf_data, filetype="pdf")
    data = []

    for page_num in range(pdf.page_count):
        page = pdf.load_page(page_num)
        blocks = page.get_text("dict")["blocks"]

        if not blocks:
            continue

        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        data.append({
                            "text": span["text"],
                            "position": [
                                span["bbox"][0], span["bbox"][1], span["bbox"][2], span["bbox"][3]
                            ],
                        })

    return data


def extraer_datos_de_pdf_con_plantilla(pdf_data, plantilla):
    doc = fitz.open(stream=pdf_data, filetype="pdf")  # Abrir el PDF directamente desde los datos binarios
    datos_extraidos = {}

    # Recorrer las páginas del PDF
    for pagina in doc:
        for dato in plantilla["datos"]:
            nombre = dato["key"]
            coords = dato["value"]["position"]

            # Verificar si las coordenadas están en el formato correcto (lista de 4 elementos)
            if len(coords) != 4:
                raise ValueError(f"Las coordenadas para el campo '{nombre}' no tienen 4 elementos, como se esperaba.")

            x1, y1, x2, y2 = coords

            # Buscar bloques de texto en la página
            for bloque in pagina.get_text("dict")["blocks"]:
                for linea in bloque.get("lines", []):
                    for span in linea["spans"]:
                        bx1, by1, bx2, by2 = span["bbox"]

                        # Verificar si el texto está dentro de las coordenadas definidas en la plantilla
                        if (x1 <= bx1 <= x2 and
                            y1 <= by1 <= y2 and
                            x1 <= bx2 <= x2 and
                            y1 <= by2 <= y2):
                            datos_extraidos[nombre] = span["text"]

    return datos_extraidos



def obtener_plantilla_por_id(plantilla_id):
    conn = sqlite3.connect('plantillas.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM plantillas WHERE id = ?", (plantilla_id,))
    row = cursor.fetchone()

    conn.close()

    if row:
        nombre, descripcion, datos_serializados = row[1], row[2], row[3]
        datos = json.loads(datos_serializados)
        return {"nombre": nombre, "descripcion": descripcion, "datos": datos}

    return None


def guardar_plantilla(nombre, descripcion, datos):
    datos_serializados = json.dumps(datos)

    # Conexión con la base de datos SQLite
    try:
        with sqlite3.connect('plantillas.db') as conn:
            cursor = conn.cursor()

            # Crear la consulta de inserción
            cursor.execute(""" 
            INSERT INTO plantillas (nombre, descripcion, datos)
            VALUES (?, ?, ?)
            """, (nombre, descripcion, datos_serializados))

            # Confirmar la transacción
            conn.commit()
    
    except sqlite3.Error as e:
        raise e  # Relanzamos el error para capturarlo en la ruta
    

def obtener_todas_las_plantillas():
        conn = sqlite3.connect('plantillas.db')
        cursor = conn.cursor()

        cursor.execute("SELECT id, nombre, descripcion, datos FROM plantillas")
        rows = cursor.fetchall()
        conn.close()

        # Convertir los datos a formato JSON
        plantillas = [
            {"id": row[0], "nombre": row[1], "descripcion": row[2], "datos": json.loads(row[3])}
            for row in rows
        ]

        return plantillas

