import re

def segmentar_texto(texto):
    factura = {}
    
    factura["numero_factura"] = re.search(r"Factura Nº:\s*(\d+)", texto)
    
    if factura["numero_factura"]:
        factura["numero_factura"] = factura["numero_factura"].group(1)
        
    factura["fecha"] = re.search(r"Fecha:\s*(\d+\. \d{2})", texto)

    if factura["fecha"]:
        factura["fecha"] = factura["fecha"].group(1)
        
    factura["total"] = re.search(r"Total:\s*([\d\.,]+)", texto)
    if factura["total"]:
        factura["total"] = factura["total"].group(1)
        
    return factura