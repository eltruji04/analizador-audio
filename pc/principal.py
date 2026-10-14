"""
principal.py — Punto de entrada del analizador de audio.

Captura el audio de forma continua, guarda siempre las últimas
TAMANO_VENTANA muestras (ventana deslizante) y, cada vez que llega un
bloque nuevo, calcula la energía de las 16 bandas y la muestra en dB.

Por qué una ventana deslizante:
- Los bloques llegan de a TAMANO_BLOQUE muestras (1024, unos 21 ms):
  eso da una actualización rápida.
- Pero la FFT de solo 1024 muestras distingue frecuencias separadas por
  unos 47 Hz: la banda 2 (60–90 Hz) quedaría sin ningún valor y la
  banda 1 (40–60 Hz) con uno solo.
- Analizando las últimas 4096 muestras (unos 85 ms) la separación baja
  a unos 11,7 Hz, cada una de esas bandas tiene 2 valores, y el análisis
  se sigue repitiendo con cada bloque.
"""

import numpy
import configuracion
import captura
import bandas


fs = configuracion.FRECUENCIA_MUESTREO
n = configuracion.TAMANO_VENTANA
# Ventana de Hann y máscaras de las bandas para tramos de largo n.
ventana, mascaras = bandas.preparar_analisis(n, fs)
# Últimas n muestras de audio (mono). Empieza en silencio (ceros).
memoria = numpy.zeros(n)


def al_recibir_bloque(bloque, cantidad_muestras, tiempo, estado):
    """
    Función que llama sounddevice con cada bloque de audio (callback).

    Agrega el bloque a la memoria, analiza las últimas n muestras y
    muestra la energía de cada banda en dB.
    """
    # `estado` está vacío si no hubo problemas; si se perdió audio, lo muestra.
    if estado:
        print(estado)

    mono = bandas.a_mono(bloque)
    m = len(mono)

    # Ventana deslizante: se descartan las m muestras más viejas
    # corriendo el resto hacia la izquierda…
    memoria[:n-m] = memoria[m:]
    # …y el bloque nuevo ocupa las últimas m posiciones.
    memoria[-m:] = mono

    energias = bandas.calcular_bandas(memoria, ventana, mascaras)

    # Pasaje a decibeles: comprime el rango (los graves pueden tener miles
    # de veces más energía que los agudos). Se suma un número muy chico
    # para no calcular log10(0) en silencio; por eso el silencio da -120 dB.
    # Los valores todavía no están calibrados: solo importa cómo varían.
    db = 10 * numpy.log10(energias + 0.000000000001)
    print(f"dB: {db.round(1)}")


# Solo se ejecuta con `python pc/principal.py`, no al importar el módulo.
if __name__ == "__main__":
    try:
        numero = captura.buscar_dispositivo(configuracion.DISPOSITIVO_SISTEMA)
        captura.capturar_continuo(numero, al_recibir_bloque)
    except KeyboardInterrupt:
        print("Análisis detenido")