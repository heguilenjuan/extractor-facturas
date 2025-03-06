import sqlite3
import json

def crear_tabla():
    conn = sqlite3.connect('plantillas.db')
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS plantillas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        descripcion TEXT NOT NULL,
        datos TEXT NOT NULL  -- Esta columna guardará el JSON serializado
    )
    """)

    conn.commit()
    conn.close()
    print("Tabla 'plantillas' creada o ya existente.")
