"""
bandas.py — Análisis de las 16 bandas de frecuencia y cálculo de las barras.

1. Recibe un tramo de audio, calcula su espectro con la FFT y suma la
   energía de las frecuencias que caen dentro de cada banda definida en
   configuracion.BANDAS.
2. Ajusta solo el piso y el techo de cada banda (calibración automática),
   para que las barras se vean bien con música fuerte o suave.
3. Convierte los dB en alturas de barra entre 0 y ALTURA_MAXIMA.
4. Suaviza las barras: suben enseguida y bajan a la velocidad de caída elegida.
5. Mide el nivel general del bloque (dBFS), sin calibración, para el medidor.
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


def nivel_db(muestras):
    """
    Nivel del bloque en dBFS: 0 es una onda que llega a ±1 todo el tiempo
    (lo máximo sin saturar), −6 es la mitad de amplitud y el silencio da
    −240. Se calcula con el valor eficaz (RMS), sin la calibración de las
    bandas, para saber si la música está fuerte o baja.

    Devuelve un float de Python: sounddevice da las muestras en float32 y
    numpy devolvería un numpy.float32, que pygame no acepta como coordenada.
    """
    rms = numpy.sqrt(numpy.mean(numpy.square(muestras)))
    return float(20 * numpy.log10(rms + 0.000000000001))


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


def promediar(db_suave, db):
    """
    Mezcla el nivel nuevo de cada banda (`db`) con el promedio de los
    bloques anteriores (`db_suave`): PROMEDIO_DB del anterior y el resto
    del nuevo. Modifica `db_suave` por dentro (con [:]).

    Sirve sobre todo para los graves: las bandas 1 y 2 se calculan con
    solo 2 valores del espectro, y sin promedio el ruido les hace saltar
    el nivel unos 3 a 5 dB de un bloque al otro.
    """
    p = configuracion.PROMEDIO_DB
    db_suave[:] = p * db_suave + (1 - p) * db


def niveles_iniciales():
    """
    Crea los arreglos de piso y techo (en dB) con los que arranca la
    calibración automática: el techo en TECHO_INICIAL_DB y el piso
    RANGO_MAXIMO_DB por debajo. Solo importan los primeros segundos:
    después se ajustan solos con la música.

    El piso arranca lo más abajo posible porque baja despacio: si
    arrancara cerca del techo, tardaría mucho en llegar al nivel de la
    música y las barras se verían vacías al empezar. Desde abajo, sube
    hasta quedar por encima del ruido en unos segundos.
    """
    techo = numpy.full(configuracion.CANTIDAD_BARRAS,
                       configuracion.TECHO_INICIAL_DB, dtype=float)
    piso = techo - configuracion.RANGO_MAXIMO_DB
    return piso, techo


def actualizar_niveles(piso, techo, db):
    """
    Calibración automática: ajusta el piso y el techo de cada banda
    según lo que está sonando. Modifica `piso` y `techo` por dentro
    (con [:]), así los cambios se conservan de un bloque al siguiente.

    Reglas, en este orden:
    1. Techo: si la música lo supera, sube enseguida; si no, baja
       VELOCIDAD_TECHO_DB por bloque (muy despacio, así una parte suave
       se ve baja). Además tiene dos límites:
       - nunca baja de TECHO_MINIMO_DB, para que en un silencio
         (-120 dB) el techo no lo alcance y llene las barras;
       - nunca queda a más de DISTANCIA_MAXIMA_DB por debajo del techo
         más alto, para que una banda casi vacía (los agudos de un piano)
         no se "estire" y muestre ruido como si fuera música.
    2. Piso: si la música baja de él, baja VELOCIDAD_PISO_BAJA_DB por
       bloque; si no, sube VELOCIDAD_PISO_SUBE_DB. Despacio en las dos
       direcciones: si bajara enseguida, seguiría cada pozo del ruido y
       el ruido de fondo se vería como barras que tiemblan.
    3. La distancia entre piso y techo queda entre RANGO_MINIMO_DB (para
       no amplificar diferencias chiquitas) y RANGO_MAXIMO_DB (para que
       después de una pausa el piso no quede muy abajo y se recupere rápido).
    """
    # 1. Techo: sube enseguida, baja despacio.
    nuevo_techo = numpy.where(db > techo, db, techo - configuracion.VELOCIDAD_TECHO_DB)
    # Límite absoluto: protege del silencio.
    nuevo_techo = numpy.maximum(nuevo_techo, configuracion.TECHO_MINIMO_DB)
    # Límite relativo a la banda más fuerte: protege de las bandas casi vacías.
    techo_general = numpy.max(nuevo_techo)
    nuevo_techo = numpy.maximum(nuevo_techo,
                                techo_general - configuracion.DISTANCIA_MAXIMA_DB)

    # 2. Piso: baja y sube despacio.
    nuevo_piso = numpy.where(db < piso,
                             piso - configuracion.VELOCIDAD_PISO_BAJA_DB,
                             piso + configuracion.VELOCIDAD_PISO_SUBE_DB)

    # 3. Distancia entre piso y techo, entre RANGO_MINIMO y RANGO_MAXIMO.
    nuevo_piso = numpy.clip(nuevo_piso,
                            nuevo_techo - configuracion.RANGO_MAXIMO_DB,
                            nuevo_techo - configuracion.RANGO_MINIMO_DB)

    techo[:] = nuevo_techo
    piso[:] = nuevo_piso


def a_alturas(db, piso, techo):
    """
    Convierte los dB de cada banda en una altura de barra: 0 cuando la
    banda está en su piso y ALTURA_MAXIMA cuando está en su techo,
    proporcional en el medio y limitada a ese rango.

    No hay riesgo de dividir por cero: actualizar_niveles garantiza que
    techo − piso es al menos RANGO_MINIMO_DB.
    """
    proporcion = (db - piso) / (techo - piso)
    alturas = proporcion * configuracion.ALTURA_MAXIMA
    alturas = numpy.clip(alturas, 0, configuracion.ALTURA_MAXIMA)
    return alturas


def suavizar(mostradas, alturas, caida):
    """
    Suaviza las barras para que no parpadeen: suben enseguida hasta la
    altura nueva, pero bajan como mucho `caida` píxeles por bloque
    (VELOCIDADES_CAIDA según estado.velocidad), sin pasar de la altura
    nueva. Modifica `mostradas` por dentro (con [:]), así se conserva de
    un bloque al siguiente.
    """
    # La mayor de las dos: si la altura nueva es mayor, sube hasta ella;
    # si es menor, baja `caida` pero sin pasarse. Si bajara siempre
    # `caida`, con una nota que se apaga despacio la barra quedaría por
    # debajo y en el bloque siguiente volvería a saltar (parpadeo).
    nuevas = numpy.maximum(alturas, mostradas - caida)
    nuevas = numpy.clip(nuevas, 0, None)
    mostradas[:] = nuevas


def actualizar_picos(picos, mostradas):
    """
    Marca de pico de cada barra: sube enseguida con la barra y, cuando la
    barra baja, se queda arriba y baja despacio.
    """
    picos[:] = numpy.maximum(mostradas, picos - configuracion.CAIDA_PICO)


# Prueba con tonos: solo se ejecuta con `python pc/bandas.py`.
if __name__ == "__main__":
    n = configuracion.TAMANO_VENTANA
    fs = configuracion.FRECUENCIA_MUESTREO
    ventana, mascaras = preparar_analisis(n, fs)

    # Un tono en el centro "logarítmico" de cada banda: raíz de (mínimo × máximo).
    # Tiene que ganar la banda correspondiente: 16 de 16.
    t = numpy.arange(n) / fs  # tiempos de cada muestra, en segundos
    frecuencias_prueba = []
    for minimo, maximo in configuracion.BANDAS:
        frecuencias_prueba.append(numpy.sqrt(minimo * maximo))
    for f in frecuencias_prueba:
        tono = numpy.sin(2 * numpy.pi * f * t)
        energias = calcular_bandas(tono, ventana, mascaras)
        ganadora = numpy.argmax(energias)  # empieza en 0
        print(f"{f:.0f} Hz → banda {ganadora + 1}")

    # Cuántos valores del espectro caen en cada banda según el largo del
    # tramo. Con 1024, la banda 2 queda vacía: por eso se analiza con 4096.
    for largo in [1024, 4096]:
        ventana, mascaras = preparar_analisis(largo, fs)
        print(f"n = {largo} → separación: {fs / largo} Hz")
        for numero, mascara in enumerate(mascaras):
            print(f"  banda {numero + 1}: {numpy.sum(mascara)} valores")

    # nivel_db(): valores conocidos.
    errores = 0
    cuadrada = numpy.where(numpy.arange(1024) % 2 == 0, 1.0, -1.0)
    seno = numpy.sin(2 * numpy.pi * 440 * numpy.arange(1024) / fs)
    casos = [("cuadrada ±1 → 0 dB", cuadrada, 0.0),
             ("cuadrada ±0,5 → −6 dB", cuadrada * 0.5, -6.02),
             ("seno de amplitud 1 → −3 dB", seno, -3.01),
             ("silencio → −240 dB", numpy.zeros(1024), -240.0)]
    for nombre, muestras, esperado in casos:
        try:
            obtenido = nivel_db(muestras)
            bien = abs(obtenido - esperado) < 0.05
            errores += 0 if bien else 1
            print(f"{'OK   ' if bien else 'ERROR'} {nombre:<30} → {obtenido:.2f}   (esperado {esperado})")
        except Exception as e:
            errores += 1
            print(f"ERROR {nombre:<30} → {type(e).__name__}: {e}")
    # Con muestras float32 (como las da sounddevice) tiene que devolver un
    # float de Python: un numpy.float32 rompe el dibujo del medidor.
    try:
        obtenido = nivel_db(seno.astype(numpy.float32))
        bien = type(obtenido) is float
        errores += 0 if bien else 1
        print(f"{'OK   ' if bien else 'ERROR'} {'float32 → float de Python':<30} → {type(obtenido).__name__}   (esperado float)")
    except Exception as e:
        errores += 1
        print(f"ERROR {'float32 → float de Python':<30} → {type(e).__name__}: {e}")
    print("nivel_db: todo bien" if errores == 0 else f"nivel_db: {errores} errores")