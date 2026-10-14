"""
bandas.py — Cálculo de la energía de las 16 bandas de frecuencia.

Recibe un tramo de audio, calcula su espectro con la FFT y suma la
energía de las frecuencias que caen dentro de cada banda definida en
configuracion.BANDAS.
"""

import numpy
import configuracion


def a_mono(audio):
    """
    Si el audio tiene varios canales (forma (muestras, canales)), los
    promedia en uno solo. Si ya es mono, lo devuelve sin cambios.
    """
    if audio.ndim == 2:
        # axis=1: promedia entre canales, muestra por muestra.
        return numpy.mean(audio, axis=1)
    return audio


def preparar_analisis(n, frecuencia_muestreo):
    """
    Calcula UNA SOLA VEZ todo lo que depende solo del largo del tramo (n)
    y no del audio: la ventana de Hann y, para cada banda, qué valores
    del espectro le corresponden (máscaras).

    Devuelve (ventana, mascaras). Sirven para cualquier tramo de largo n.
    """
    ventana = numpy.hanning(n)
    # Frecuencia en Hz de cada valor que devuelve rfft para un tramo de largo n.
    frecuencias = numpy.fft.rfftfreq(n, d=1 / frecuencia_muestreo)
    mascaras = []
    for minimo, maximo in configuracion.BANDAS:
        # Lista de True/False: True en las frecuencias que pertenecen a la banda.
        mascaras.append((frecuencias >= minimo) & (frecuencias < maximo))
    return ventana, mascaras


def calcular_bandas(muestras, ventana, mascaras):
    """
    Devuelve un arreglo de numpy con la energía de cada banda.
    """
    # La ventana suaviza los bordes del tramo para que la energía de un
    # tono no se desparrame hacia las bandas vecinas.
    espectro = numpy.abs(numpy.fft.rfft(muestras * ventana))
    # Se eleva al cuadrado una sola vez, para todo el espectro.
    potencia = espectro ** 2
    energias = []
    for mascara in mascaras:
        energias.append(numpy.sum(potencia[mascara]))
    return numpy.array(energias)


# Prueba con tonos: solo se ejecuta con `python pc/bandas.py`.
if __name__ == "__main__":
    n = 1024
    fs = configuracion.FRECUENCIA_MUESTREO
    ventana, mascaras = preparar_analisis(n, fs)

    t = numpy.arange(n) / fs  # tiempos de cada muestra, en segundos
    for f in [40, 60, 90, 130, 190, 280, 410, 610, 900, 1300, 1950, 2850, 4200, 6250, 9200, 13500, 20000]:
        tono = numpy.sin(2 * numpy.pi * f * t)
        energias = calcular_bandas(tono, ventana, mascaras)
        ganadora = numpy.argmax(energias)  # empieza en 0
        print(f"{f} Hz → banda {ganadora + 1}")
    for n in [1024, 4096]:
        ventana, mascaras = preparar_analisis(n, fs)
        print(f"n = {n}, → separación: {fs / n} Hz")
        for numero, mascara in enumerate(mascaras):
            print(f"  banda {numero + 1}: {numpy.sum(mascara)} valores")

