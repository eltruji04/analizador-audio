"""
nota.py — Estimación de la nota fundamental, su frecuencia y el desvío en cents.

FALTA IMPLEMENTAR. principal.py ya llama a estimar() en cada bloque: la
nota va en el byte 18 del paquete y el visualizador ya dibuja la tarjeta
de nota, el color por nota y el afinador. Alcanza con completar estimar().

Pendiente de medir: con 48 000 / 4096 ≈ 11,7 Hz por valor del espectro,
en G3 (196 Hz) un valor vale unos 100 cents. Para el afinador hace falta
interpolar el pico o usar una ventana más larga.
"""

import configuracion


def estimar(muestras, frecuencia_muestreo):
    """
    Devuelve (nota, frecuencia, cents) para las últimas muestras de audio.

    muestras: arreglo numpy mono con las últimas TAMANO_VENTANA muestras.
    nota: 0 a 11 (C…B) o configuracion.SIN_NOTA si no hay una nota clara.
    frecuencia: frecuencia estimada en Hz, o None.
    cents: desvío respecto de la nota exacta, de −50 a +50, o None.

    Por ahora siempre devuelve "sin nota".
    """
    return configuracion.SIN_NOTA, None, None
