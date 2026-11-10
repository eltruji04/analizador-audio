"""
colores.py — Paleta de la interfaz y color de cada banda.

- Paleta fija de la ventana (fondo, tarjetas, texto, estados).
- color_banda(): color de una banda según el modo (fijo, arcoíris o nota).
- MAPA_ESPECTROGRAMA: de intensidad (0–255) a color, para el espectrograma.
"""

import colorsys
import numpy
import configuracion

# --- Paleta de la interfaz ---
FONDO = (13, 17, 23)            # #0D1117
TARJETA = (21, 27, 35)          # #151B23
BORDE = (37, 45, 56)            # #252D38
TEXTO = (230, 237, 243)         # #E6EDF3
TEXTO_SECUNDARIO = (154, 167, 181)  # #9AA7B5
ACTIVO = (92, 200, 255)         # #5CC8FF
PAUSA = (245, 165, 36)          # #F5A524
ROJO = (248, 81, 73)            # #F85149, zona roja del medidor de nivel
CONECTADO = (63, 185, 80)       # #3FB950
DESCONECTADO = (110, 118, 129)
OLED_ENCENDIDO = (220, 235, 255)  # #DCEBFF
OLED_APAGADO = (0, 0, 0)
BLANCO = (255, 255, 255)

# Tono (0 a 1) de cada banda en arcoíris: de rojo (0) a violeta (~0,78).
TONO_VIOLETA = 0.78


def desde_tono(tono, saturacion=0.75, brillo=1.0):
    """Color (R, G, B) de 0 a 255 a partir de un tono entre 0 y 1."""
    r, g, b = colorsys.hsv_to_rgb(tono % 1.0, saturacion, brillo)
    return (int(r * 255), int(g * 255), int(b * 255))


# Se calculan una sola vez: son siempre los mismos.
ARCOIRIS = [desde_tono(i / (configuracion.CANTIDAD_BARRAS - 1) * TONO_VIOLETA)
            for i in range(configuracion.CANTIDAD_BARRAS)]
# 12 notas = 12 tonos repartidos en el círculo (C rojo, E amarillo verdoso…).
COLORES_NOTAS = [desde_tono(i / 12) for i in range(12)]


def color_banda(banda, modo, color_fijo, nota):
    """
    Color de la banda `banda` (0 a 15) según el modo de color:
    - "fijo": la muestra elegida (color_fijo, índice en COLORES_FIJOS);
    - "arcoiris": un tono distinto por banda, de rojo a violeta;
    - "nota": el tono de la nota que suena; sin nota, el color fijo.
    """
    if modo == "arcoiris":
        return ARCOIRIS[banda]
    if modo == "nota" and nota != configuracion.SIN_NOTA:
        return COLORES_NOTAS[nota]
    return configuracion.COLORES_FIJOS[color_fijo][1]


def mezclar(a, b, t):
    """Color entre `a` (t = 0) y `b` (t = 1)."""
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _armar_mapa():
    """
    Tabla de 256 colores para el espectrograma: oscuro → violeta → magenta
    → naranja → amarillo. Devuelve un arreglo numpy de forma (256, 3).
    """
    escalones = [FONDO, (88, 28, 135), (219, 39, 119), (249, 115, 22), (250, 204, 21)]
    mapa = numpy.zeros((256, 3), dtype=numpy.uint8)
    tramos = len(escalones) - 1
    for i in range(256):
        posicion = i / 255 * tramos
        tramo = min(int(posicion), tramos - 1)
        mapa[i] = mezclar(escalones[tramo], escalones[tramo + 1], posicion - tramo)
    return mapa


MAPA_ESPECTROGRAMA = _armar_mapa()
