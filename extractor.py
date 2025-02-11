import re
import fitz  # PyMuPDF
from flask import Flask, request, jsonify

app = Flask(__name__)

def extraer_texto(pdf_path):
    """
    Extrae el texto del PDF y lo divide en dos partes:
      - primera_parte: líneas anteriores a "Observaciones:"
      - segunda_parte: desde "Observaciones:" hasta el primer elemento que contenga "C.A.E."
    """
    doc = fitz.open(pdf_path)
    texto = "\n".join([pagina.get_text("text") for pagina in doc])
    lineas = texto.split("\n")
    
    # Dividir en dos partes según "Observaciones:"
    try:
        idx_observaciones = lineas.index("Observaciones:")
        primera_parte = lineas[:idx_observaciones]
        segunda_parte = lineas[idx_observaciones:]
    except ValueError:
        primera_parte = lineas
        segunda_parte = []
    
    # Extraer importes de la sección de "Observaciones:" (por ejemplo: importe IVA, subtotal, etc.)
    datos_importe = []
    if segunda_parte:
        try:
            idx_cae = next(i for i, el in enumerate(segunda_parte) if "C.A.E" in el)
        except StopIteration:
            idx_cae = len(segunda_parte)
        for item in segunda_parte[1:idx_cae]:
            try:
                valor = float(item.replace(',', ''))
                datos_importe.append(valor)
            except ValueError:
                pass  # Ignorar elementos que no sean numéricos

    return primera_parte, segunda_parte, datos_importe


def extraer_datos_obligatorios(primera_parte):
    """
    A partir de la primera parte del texto extraído de la factura,
    se utiliza una serie de expresiones regulares para obtener los datos
    que sabemos que siempre estarán presentes.
    """
    datos = {}
    texto_completo = " ".join(primera_parte)

    # Tipo de factura: se asume que es "FACTURA" o "NOTA DE CREDITO" seguido de una letra
    match_tipo = re.search(r'(FACTURA|NOTA DE CREDITO)\s+[A-Z]', texto_completo)
    datos["tipo_factura"] = match_tipo.group() if match_tipo else None

    # Número de factura
    match_numero = re.search(r'Nº\s*(\d+)', texto_completo)
    datos["numero_factura"] = match_numero.group(1) if match_numero else None

    # Fecha (formato dd/mm/aaaa)
    match_fecha = re.search(r'\d{2}/\d{2}/\d{4}', texto_completo)
    datos["fecha"] = match_fecha.group() if match_fecha else None

    # Hora (formato hh:mm:ss)
    match_hora = re.search(r'\d{2}:\d{2}:\d{2}', texto_completo)
    datos["hora"] = match_hora.group() if match_hora else None

    # Razón social: se asume que está en una línea con mayúsculas, con puntos o espacios
    if len(primera_parte) >= 7:
        match_razon = re.match(r'[A-Z\s.]+', primera_parte[6])
        datos["razon_social"] = match_razon.group().strip() if match_razon else None
    else:
        datos["razon_social"] = None

    # Localidad: se asume que la siguiente línea (por ejemplo, línea 8) contiene la localidad
    if len(primera_parte) >= 8:
        match_localidad = re.match(r'[A-Z\s]+', primera_parte[7])
        datos["localidad"] = match_localidad.group().strip() if match_localidad else None
    else:
        datos["localidad"] = None

    # CUIT: 11 dígitos
    match_cuit = re.search(r'\b\d{11}\b', texto_completo)
    datos["cuit"] = match_cuit.group() if match_cuit else None

    # Condición IVA: INSCRIPTO, MONOTRIBUTO, EXENTO, etc.
    match_iva = re.search(r'(INSCRIPTO|MONOTRIBUTO|EXENTO)', texto_completo)
    datos["condicion_iva"] = match_iva.group() if match_iva else None

    # Forma de pago: se busca un patrón como "CTA CTE 0 DIAS" o similar
    match_pago = re.search(r'(CTA CTE|CONTADO|TARJETA).*?\d+\s*DIAS?', texto_completo)
    datos["forma_pago"] = match_pago.group() if match_pago else None

    # Artículos: se intentará capturar las líneas que tengan un código de artículo (número largo) seguido de cantidad y demás datos.
    articulos = []
    patron_articulo = re.compile(r'(\d{5,})\s+(\d+\.\d{2})')
    for i, linea in enumerate(primera_parte):
        match_art = patron_articulo.search(linea)
        if match_art:
            articulo = {
                "numero": match_art.group(1),
                "cantidad": match_art.group(2)
            }
            # Se asume que la descripción y los importes siguen en las líneas siguientes
            if i + 1 < len(primera_parte):
                articulo["descripcion"] = primera_parte[i+1].strip()
            if i + 2 < len(primera_parte):
                articulo["precio_unitario"] = primera_parte[i+2].strip()
            if i + 3 < len(primera_parte):
                articulo["importe"] = primera_parte[i+3].strip()
            articulos.append(articulo)
    datos["articulos"] = articulos

    return datos


def identificar_importes_observaciones(importes, tasas_iva=[0.10, 0.21], tolerancia=0.02):
    """
    A partir de la lista de importes extraídos de la sección "Observaciones",
    identifica:
      - TOTAL: el mayor importe
      - SUBTOTAL: el siguiente mayor
      - IVA y PERC IIBB: utilizando el ratio (valor / SUBTOTAL) y comparándolo con las tasas de IVA conocidas.
    
    Se utiliza una tolerancia para considerar diferencias por redondeos.
    Retorna una tupla: (total, subtotal, iva, perc_iibb)
    """
    if not importes or len(importes) < 2:
        raise ValueError("Se requieren al menos dos importes para identificar TOTAL y SUBTOTAL.")

    # Ordenar de mayor a menor
    importes_ordenados = sorted(importes, reverse=True)
    total = importes_ordenados[0]
    subtotal = importes_ordenados[1]
    suma_impuestos = total - subtotal

    # Si sólo hay dos importes, asumimos que la diferencia es el IVA y no hay PERC IIBB
    if len(importes_ordenados) == 2:
        iva = suma_impuestos
        perc_iibb = 0.0
        return total, subtotal, iva, perc_iibb

    # Si hay valores adicionales (lo habitual cuando se presentan IVA y PERC IIBB)
    restantes = importes_ordenados[2:]
    if len(restantes) < 2:
        iva = restantes[0]
        perc_iibb = 0.0
        return total, subtotal, iva, perc_iibb

    # Para cada candidato, calcular el ratio respecto del subtotal y la diferencia con las tasas conocidas
    candidatos = []
    for valor in restantes:
        ratio = valor / subtotal if subtotal else 0
        diffs = [abs(ratio - tasa) for tasa in tasas_iva]
        min_diff = min(diffs)
        candidatos.append({
            "valor": valor,
            "ratio": ratio,
            "min_diff": min_diff,
            "tasa_asociada": tasas_iva[diffs.index(min_diff)]
        })

    # Seleccionar aquellos candidatos que se ajusten dentro de la tolerancia
    candidatos_aceptados = [c for c in candidatos if c["min_diff"] <= tolerancia]
    if len(candidatos_aceptados) == 0:
        # Si ninguno se ajusta, tomar el que esté más cercano
        candidato_iva = min(candidatos, key=lambda c: c["min_diff"])
        iva = candidato_iva["valor"]
        perc_iibb = suma_impuestos - iva
    elif len(candidatos_aceptados) == 1:
        candidato_iva = candidatos_aceptados[0]
        iva = candidato_iva["valor"]
        perc_iibb = suma_impuestos - iva
    else:
        # Si hay dos candidatos aceptados, elegir el que tenga menor diferencia respecto a alguna tasa conocida
        candidato_iva = min(candidatos_aceptados, key=lambda c: c["min_diff"])
        iva = candidato_iva["valor"]
        perc_iibb = suma_impuestos - iva

    # Redondear el PERC IIBB a dos decimales
    perc_iibb = round(perc_iibb, 2)
    
    return total, subtotal, iva, perc_iibb


@app.route('/extraer', methods=['POST'])
def extraer_datos():
    """
    API para recibir un PDF y devolver:
      - Todo el contenido extraído de la factura.
      - Los datos obligatorios identificados mediante expresiones regulares.
      - La identificación de importes observaciones (TOTAL, SUBTOTAL, IVA, PERC IIBB).
    """
    archivo = request.files.get('file')
    if not archivo:
        return jsonify({"error": "No se envió ningún archivo"}), 400

    ruta_pdf = "temp.pdf"
    archivo.save(ruta_pdf)

    # Extraer todo el contenido (texto dividido y datos de importes de observaciones)
    primera_parte, segunda_parte, datos_importe = extraer_texto(ruta_pdf)

    # Extraer datos obligatorios de la primera parte
    datos_obligatorios = extraer_datos_obligatorios(primera_parte)
    datos_obligatorios["importes_observaciones"] = datos_importe

    # Identificar importes de observaciones: TOTAL, SUBTOTAL, IVA y PERC IIBB
    try:
        total, subtotal, iva, perc_iibb = identificar_importes_observaciones(datos_importe, tasas_iva=[0.10, 0.21], tolerancia=0.02)
        impuestos = {
            "total": total,
            "subtotal": subtotal,
            "iva": iva,
            "perc_iibb": perc_iibb
        }
    except ValueError as e:
        impuestos = {"error": str(e)}

    datos_completos = {
        "texto_completo": primera_parte + segunda_parte,
        "datos_obligatorios": datos_obligatorios,
        "impuestos_observaciones": impuestos
    }

    return jsonify(datos_completos)


if __name__ == '__main__':
    app.run(debug=True, port=5000)

