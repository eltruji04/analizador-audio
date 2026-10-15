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

def niveles_iniciales():
    techo = numpy.full(configuracion.CANTIDAD_BARRAS, configuracion.TECHO_INICIAL_DB)
    piso = techo - configuracion.RANGO_MINIMO_DB
    return piso, techo

def actualizar_niveles(piso, techo, db):
    # 1. Techo: sube enseguida, baja despacio
    nuevo_techo = numpy.where(db > techo, db, techo - configuracion.VELOCIDAD_DB)
    nuevo_techo = numpy.maximum(nuevo_techo, configuracion.TECHO_MINIMO_DB)
    techo_general = numpy.max(nuevo_techo)
    nuevo_techo = numpy.maximum(nuevo_techo, techo_general - configuracion.DISTANCIA_MAXIMA_DB)

    # 2. Piso: baja enseguida, sube despacio
    nuevo_piso = numpy.where(db < piso, db, piso + configuracion.VELOCIDAD_DB)

    # 3. Distancia entre los dos, entre RANGO_MINIMO y RANGO_MAXIMO
    nuevo_piso = numpy.clip(nuevo_piso, nuevo_techo - configuracion.RANGO_MAXIMO_DB, nuevo_techo - configuracion.RANGO_MINIMO_DB)

    techo[:] = nuevo_techo
    piso[:] = nuevo_piso

def a_alturas(db, piso, techo):
    # FUNCIÓN a_alturas(db, piso, techo):
    proporcion = (db - piso) / (techo - piso)
    alturas = proporcion * configuracion.ALTURA_MAXIMA
    alturas = numpy.clip(alturas, 0, configuracion.ALTURA_MAXIMA)
    return alturas

# Prueba con tonos: solo se ejecuta con `python pc/bandas.py`.
if __name__ == "__main__":
    n = configuracion.TAMANO_VENTANA
    fs = configuracion.FRECUENCIA_MUESTREO
    ventana, mascaras = preparar_analisis(n, fs)

    t = numpy.arange(n) / fs  # tiempos de cada muestra, en segundos
    frecuencias_prueba = []
    for minimo, maximo in configuracion.BANDAS:
        frecuencias_prueba.append(numpy.sqrt(minimo * maximo))
    for f in frecuencias_prueba:
        tono = numpy.sin(2 * numpy.pi * f * t)
        energias = calcular_bandas(tono, ventana, mascaras)
        ganadora = numpy.argmax(energias)  # empieza en 0
        print(f"{f:.0f} Hz → banda {ganadora + 1}")
    for n in [1024, 4096]:
        ventana, mascaras = preparar_analisis(n, fs)
        print(f"n = {n}, → separación: {fs / n} Hz")
        for numero, mascara in enumerate(mascaras):
            print(f"  banda {numero + 1}: {numpy.sum(mascara)} valores")

