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

Además, estimar_bpm() calcula el tempo con los momentos de los últimos
golpes, que detectar() va anotando en `momentos`.
"""
import collections
import numpy
import configuracion

# dB del bloque anterior. None hasta el primer bloque.
anterior = None
# Momento del último golpe: muy en el pasado para que el primero valga.
ultimo_golpe = -1000
# Momentos de los últimos golpes, para el tempo. 64 alcanzan de sobra
# para BPM_VENTANA aunque los golpes vengan a la velocidad máxima.
momentos = collections.deque(maxlen=64)

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
        momentos.append(ahora)
        return True
    return False


def estimar_bpm(momentos_golpes, ahora):
    """
    Tempo en BPM (entero) a partir de los momentos de los golpes, o None si
    no se puede decir.

    - Solo cuentan los golpes de los últimos BPM_VENTANA segundos, y tienen
      que ser al menos BPM_MINIMO_GOLPES.
    - Si el último fue hace más de BPM_SIN_GOLPES, la música paró: None.
    - La MEDIANA de los intervalos entre golpes dice cuál es el intervalo
      típico: un golpe perdido (un intervalo doble) o uno de más (uno corto)
      no la mueven mientras sean minoría. Después se PROMEDIAN solo los
      intervalos a menos de BPM_TOLERANCIA de la mediana: los golpes caen
      en bloques de ~21 ms, así que los intervalos salen de a saltos
      (0,49 o 0,51 s en vez de 0,5) y con la mediana sola el número
      saltaría entre 117 y 122.
    - La mediana es la "baja": el intervalo del medio de la lista ordenada,
      que siempre es uno de verdad. numpy.median, con una cantidad par,
      promedia los dos del medio: con intervalos en dos grupos (0,25 y
      0,75 s, mitad y mitad) daba 0,5, ninguno quedaba cerca, el promedio
      de una lista vacía daba NaN y round() cortaba el análisis.
    - El resultado se dobla o se divide por 2 hasta quedar entre BPM_MINIMO
      y BPM_MAXIMO: si el bombo suena cada 2 tiempos daría la mitad.
    """
    recientes = [m for m in momentos_golpes if ahora - m <= configuracion.BPM_VENTANA]
    if len(recientes) < configuracion.BPM_MINIMO_GOLPES:
        return None
    if ahora - recientes[-1] > configuracion.BPM_SIN_GOLPES:
        return None
    intervalos = numpy.diff(recientes)
    ordenados = numpy.sort(intervalos)
    mediana = ordenados[(len(ordenados) - 1) // 2]
    if mediana <= 0:
        return None
    # Nunca queda vacío: la mediana baja es uno de los intervalos.
    cercanos = intervalos[numpy.abs(intervalos - mediana) <= configuracion.BPM_TOLERANCIA * mediana]
    intervalo = numpy.mean(cercanos)
    # Por las dudas: esto corre en el callback de audio y un error ahí corta
    # todo el análisis. Si algo raro da NaN o infinito, mejor no mostrar tempo.
    if not numpy.isfinite(intervalo) or intervalo <= 0:
        return None
    bpm = 60 / intervalo
    while bpm < configuracion.BPM_MINIMO:
        bpm *= 2
    while bpm >= configuracion.BPM_MAXIMO:
        bpm /= 2
    return round(bpm)


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

    # --- estimar_bpm(momentos, ahora) ---
    errores_bpm = 0

    def revisar(nombre, obtenido, esperado):
        """Imprime una línea OK / ERROR y cuenta los errores."""
        global errores_bpm
        bien = obtenido == esperado
        errores_bpm += 0 if bien else 1
        print(f"{'OK   ' if bien else 'ERROR'} {nombre:<46} → {obtenido}   (esperado {esperado})")

    def golpes(intervalo, cantidad, desde=0.0):
        """`cantidad` golpes separados `intervalo` segundos, empezando en `desde`."""
        return [desde + i * intervalo for i in range(cantidad)]

    def ultimo(lista):
        return lista[-1]

    casos_bpm = [
        ("120 BPM parejo", golpes(0.5, 12), None, 120),
        ("90 BPM parejo", golpes(60 / 90, 10), None, 90),
        ("solo 3 golpes → sin tempo", golpes(0.5, 3), None, None),
        ("la música paró hace 5 s → sin tempo", golpes(0.5, 12), 5.0, None),
        ("bombo cada 2 tiempos (60) → 120", golpes(1.0, 8), None, 120),
        ("muy rápido (300) → 150", golpes(0.2, 20), None, 150),
        ("golpes viejos fuera de la ventana no cuentan", golpes(0.4, 10) + golpes(0.5, 12, 20.0), None, 120),
    ]
    for nombre, lista, despues, esperado in casos_bpm:
        try:
            ahora = ultimo(lista) + (despues if despues is not None else 0.1)
            revisar(nombre, estimar_bpm(lista, ahora), esperado)
        except Exception as e:
            errores_bpm += 1
            print(f"ERROR {nombre:<46} → {type(e).__name__}: {e}")

    # Un golpe perdido y uno de más en medio de un 120 parejo: la mediana no se mueve.
    try:
        lista = golpes(0.5, 14)
        del lista[6]                 # se perdió uno: queda un intervalo de 1 s
        lista.insert(3, lista[2] + 0.2)  # uno de más: dos intervalos cortos
        revisar("un golpe perdido y uno de más → sigue 120", estimar_bpm(lista, lista[-1] + 0.1), 120)
    except Exception as e:
        errores_bpm += 1
        print(f"ERROR golpe perdido y de más → {type(e).__name__}: {e}")

    # Con ruido de ±20 ms en cada golpe tiene que seguir cerca de 120.
    try:
        ruido = numpy.random.default_rng(0).uniform(-0.02, 0.02, 16)
        lista = list(numpy.array(golpes(0.5, 16)) + ruido)
        obtenido = estimar_bpm(lista, lista[-1] + 0.1)
        bien = obtenido is not None and abs(obtenido - 120) <= 3
        errores_bpm += 0 if bien else 1
        print(f"{'OK   ' if bien else 'ERROR'} {'120 con ±20 ms de ruido → 117 a 123':<46} → {obtenido}   (esperado 117 a 123)")
    except Exception as e:
        errores_bpm += 1
        print(f"ERROR ruido → {type(e).__name__}: {e}")

    # Golpes que caen en bloques de audio de ~21,3 ms (1024 muestras a 48 kHz):
    # los intervalos salen de 0,490 o 0,511 s, pero el promedio da 120.
    try:
        bloque_s = configuracion.TAMANO_BLOQUE / configuracion.FRECUENCIA_MUESTREO
        lista = [numpy.ceil(t / bloque_s) * bloque_s for t in golpes(0.5, 16, 0.013)]
        revisar("golpes en bloques de audio → 120", estimar_bpm(lista, lista[-1] + 0.1), 120)
    except Exception as e:
        errores_bpm += 1
        print(f"ERROR bloques → {type(e).__name__}: {e}")

    # El caso que cortó el análisis: intervalos en dos grupos, mitad y mitad.
    # Con la mediana de numpy daba NaN y round() explotaba.
    try:
        lista = [0.0]
        for i in range(6):
            lista.append(lista[-1] + (0.25 if i % 2 == 0 else 0.75))
        obtenido = estimar_bpm(lista, lista[-1] + 0.1)
        bien = obtenido is None or (configuracion.BPM_MINIMO <= obtenido < configuracion.BPM_MAXIMO)
        errores_bpm += 0 if bien else 1
        print(f"{'OK   ' if bien else 'ERROR'} {'intervalos en dos grupos → no explota':<46} → {obtenido}   (esperado un tempo válido o None)")
    except Exception as e:
        errores_bpm += 1
        print(f"ERROR {'intervalos en dos grupos → no explota':<46} → {type(e).__name__}: {e}")

    # A lo bruto: miles de listas de golpes al azar (intervalos de 0,15 a 2 s,
    # en grupos o no). Nunca tiene que explotar ni dar algo fuera del rango.
    try:
        azar = numpy.random.default_rng(1)
        malos = []
        for k in range(3000):
            cantidad = int(azar.integers(4, 30))
            if k % 2:
                intervalos_azar = azar.choice([0.15, 0.25, 0.5, 0.75, 1.0, 2.0], cantidad)
            else:
                intervalos_azar = azar.uniform(0.15, 2.0, cantidad)
            lista = list(numpy.cumsum(intervalos_azar))
            obtenido = estimar_bpm(lista, lista[-1] + azar.uniform(0, 4))
            if obtenido is not None and not (configuracion.BPM_MINIMO <= obtenido < configuracion.BPM_MAXIMO):
                malos.append(obtenido)
        bien = not malos
        errores_bpm += 0 if bien else 1
        print(f"{'OK   ' if bien else 'ERROR'} {'3000 listas al azar → nunca explota':<46} → fuera de rango: {malos[:5]}   (esperado ninguno)")
    except Exception as e:
        errores_bpm += 1
        print(f"ERROR {'3000 listas al azar → nunca explota':<46} → {type(e).__name__}: {e}")

    # detectar() anota cada golpe en `momentos` (los casos de arriba dieron 2).
    revisar("detectar() anota los golpes en momentos", len(momentos), 2)
    print("Tempo: todo bien" if errores_bpm == 0 else f"Tempo: {errores_bpm} errores")
