"""
golpe.py — Detector de golpes (bombo).

principal.py llama a detectar() en cada bloque y, si devuelve True con
el efecto activo, sube las BARRAS_GOLPE a 32 en el arreglo `destello`.

Criterio (valores en configuracion.py, sin verificar contra golpes reales):
- trabaja sobre los dB SIN promediar (el promedio le quita ~6 dB al bombo);
- golpe = algún grave (BANDAS_DETECCION_GOLPE) sube más de GOLPE_SUBIDA_DB
  respecto del bloque anterior y queda a menos de GOLPE_DISTANCIA_TECHO_DB
  de su techo;
- después de un golpe, espera GOLPE_ESPERA segundos antes de aceptar otro.
"""
import numpy
import configuracion

# dB del bloque anterior. None hasta el primer bloque.
anterior = None
# Momento del último golpe: muy en el pasado para que el primero valga.
ultimo_golpe = -1000

def detectar(db, techo, ahora):
    """
    Devuelve True si en este bloque hubo un golpe.

    db: dB de las 16 bandas en este bloque, sin promediar (arreglo numpy).
    techo: techo de cada banda en dB (de bandas.actualizar_niveles).
    ahora: time.monotonic() del bloque, para la espera entre golpes.
    """
    global anterior, ultimo_golpe

    # Primer bloque: todavía no hay con qué comparar.
    if anterior is None:
        anterior = db.copy()
        return False

    g = configuracion.BANDAS_DETECCION_GOLPE
    # Cuánto subió cada grave respecto del bloque anterior.
    subida = db[g] - anterior[g]
    # True en los graves que están cerca de su techo.
    cerca = db[g] > techo[g] - configuracion.GOLPE_DISTANCIA_TECHO_DB
    # Se actualiza SIEMPRE, antes de cualquier return: si no, durante la
    # espera se compararía contra un bloque viejo.
    anterior = db.copy()

    # Espera entre golpes: evita contar dos veces el mismo bombo.
    if ahora - ultimo_golpe < configuracion.GOLPE_ESPERA:
        return False
    # Golpe: algún grave subió lo suficiente y está cerca de su techo.
    if numpy.any((subida > configuracion.GOLPE_SUBIDA_DB) & cerca):
        ultimo_golpe = ahora
        return True
    return False


# Pruebas sin audio: solo se ejecutan con `python pc/golpe.py`.
if __name__ == "__main__":
    # Techo en -20 dB en todas las bandas: "cerca del techo" es por encima de -35.
    techo = numpy.full(configuracion.CANTIDAD_BARRAS, -20.0)

    def bloque(graves, resto=-40.0):
        """dB de un bloque: los graves en `graves` y las demás bandas en `resto`."""
        db = numpy.full(configuracion.CANTIDAD_BARRAS, resto)
        db[configuracion.BANDAS_DETECCION_GOLPE] = graves
        return db

    # Cada caso es (descripción, dB del bloque, momento, resultado esperado).
    # Van en orden: cada uno se compara con el bloque del caso anterior.
    casos = [
        ("1. Primer bloque, no hay con qué comparar", bloque(-40), 0.00, False),
        ("2. Graves suben 15 dB, a 5 del techo", bloque(-25), 0.02, True),
        ("3a. Graves vuelven a bajar", bloque(-40), 0.05, False),
        ("3b. Suben otra vez dentro de la espera", bloque(-25), 0.10, False),
        ("4a. Graves quietos", bloque(-40), 0.50, False),
        ("4b. Suben solo 3 dB", bloque(-37), 0.52, False),
        ("5a. Graves lejos del techo", bloque(-60), 1.00, False),
        ("5b. Suben 10 dB pero quedan a 30 del techo", bloque(-50), 1.02, False),
        ("6a. Graves quietos", bloque(-40), 1.50, False),
        ("6b. Pasada la espera, otro golpe vale", bloque(-25), 1.52, True),
        ("7a. Todo quieto", bloque(-40), 2.00, False),
        ("7b. Suben solo los agudos (no cuentan)", bloque(-40, resto=-25), 2.02, False),
    ]
    errores = 0
    for descripcion, db, ahora, esperado in casos:
        resultado = detectar(db, techo, ahora)
        marca = "ok" if resultado == esperado else "ERROR"
        if resultado != esperado:
            errores += 1
        print(f"{marca:5} {descripcion} (esperado {esperado}): {resultado}")
    print(f"Errores: {errores} de {len(casos)}")
