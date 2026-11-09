"""
nota.py — Nota que suena (byte 18 del paquete) y afinador.

principal.py llama a estimar() en cada bloque. Dos formas, según el afinador:
- Afinador activo: detectar_frecuencia() busca el período de la onda con el
  método YIN y a_nota() lo pasa a nota y cents. La frecuencia se promedia
  para que la aguja no tiemble.
- Afinador apagado (modo nota): croma() suma la energía del espectro en las
  12 notas y puntajes_raiz() la compara con plantillas de acordes; la nota es
  la raíz del acorde. Si hay estéreo, usa los lados (L - R) para ignorar la
  voz, que va al centro.
En los dos, debajo de NOTA_VOLUMEN_MINIMO_DB no hay nota.
"""

import math
import numpy
import configuracion


# --- Preparación de la croma: se hace una sola vez, al importar ---
# Ventana de Hann.
ventana_croma = numpy.hanning(configuracion.TAMANO_VENTANA)
# Frecuencia (Hz).
frecuencias = numpy.fft.rfftfreq(configuracion.TAMANO_VENTANA, 1 / configuracion.FRECUENCIA_MUESTREO)
# Solo los valores entre CROMA_FRECUENCIA_MINIMA y _MAXIMA.
mascara_croma = ((frecuencias >= configuracion.CROMA_FRECUENCIA_MINIMA)
                 & (frecuencias <= configuracion.CROMA_FRECUENCIA_MAXIMA))
# Nota (0-11) de cada frecuencia de la máscara: lo mismo que a_nota(), con arreglos.
clases_croma = numpy.round(69 + 12 * numpy.log2(frecuencias[mascara_croma]
                                                / configuracion.LA_REFERENCIA)).astype(int) % 12

# --- Plantillas de acordes: se arman una sola vez, al importar ---
def perfil_armonicos(nota):
    """
    Croma que deja una nota (0-11) con sus primeros 6 armónicos: la nota,
    la octava, la quinta de arriba, otra octava, la tercera mayor de arriba
    y otra quinta. Cada armónico tiene CROMA_DECAIMIENTO_ARMONICOS de la
    amplitud del anterior (al cuadrado, porque la croma está en potencia).
    """
    perfil = numpy.zeros(12)
    for armonico in range(1, 7):
        semitonos = round(12 * math.log2(armonico))   # 0, 12, 19, 24, 28, 31
        perfil[(nota + semitonos) % 12] += configuracion.CROMA_DECAIMIENTO_ARMONICOS ** (2 * (armonico - 1))
    return perfil


# 24 plantillas, en orden: C mayor, C menor, C# mayor, C# menor… Cada una
# es raíz + tercera (mayor o menor) + quinta, con sus armónicos y largo 1.
# Comparar con armónicos es lo que evita confundir el acorde con su
# quinta (G en un C) o, en el D abierto, con un A.
plantillas = []
for raiz in range(12):
    for tercera in (4, 3):   # mayor, menor
        plantilla = (configuracion.CROMA_PESO_RAIZ * perfil_armonicos(raiz)
                     + perfil_armonicos((raiz + tercera) % 12)
                     + perfil_armonicos((raiz + 7) % 12))
        plantillas.append(plantilla / numpy.linalg.norm(plantilla))
plantillas = numpy.array(plantillas)   # forma (24, 12)

# --- Promedios entre bloques (los cambia estimar()) ---
croma_suave = numpy.zeros(12)   # croma promediada (modo nota)
nota_actual = configuracion.SIN_NOTA  # nota que se muestra en modo nota (se mantiene entre bloques)
bloques_plana = 0               # bloques seguidos con la croma plana (modo nota)
candidata = None                # raíz que le está ganando a nota_actual (modo nota). None = ninguna
bloques_candidata = 0           # bloques seguidos que lleva ganando la candidata
frecuencia_suave = None         # frecuencia promediada (afinador). None = sin promedio


def croma(muestras):
    """
    Energía del espectro sumada por nota, sin importar la octava.

    Se suma la potencia (magnitud al cuadrado), no la magnitud: así pesan
    los picos de las notas y no el ruido, que ocupa cientos de valores
    del espectro pero con poca energía en cada uno.

    muestras: arreglo numpy mono de TAMANO_VENTANA muestras.
    Devuelve un arreglo de 12 valores (C…B); el más grande es la nota predominante.
    """
    espectro = numpy.abs(numpy.fft.rfft(muestras * ventana_croma))[mascara_croma] ** 2
    return numpy.bincount(clases_croma, weights=espectro, minlength=12)


def puntajes_raiz(croma_promediada):
    """
    Cuánto se parece la croma a un acorde con cada raíz (0-11).

    Compara la croma (con largo 1) contra las 24 plantillas y, para cada
    raíz, se queda con el mejor de sus dos acordes (mayor o menor).
    Devuelve 12 puntajes de 0 a 1; el más alto es la raíz del acorde.
    """
    parecido = plantillas @ (croma_promediada / numpy.linalg.norm(croma_promediada))
    # (24,) → (12, 2): fila = raíz, columnas = mayor y menor.
    return parecido.reshape(12, 2).max(axis=1)


def a_nota(frecuencia):
    """
    Pasa una frecuencia en Hz a (nota, cents).

    nota: 0 a 11 (C…B), la nota exacta más cercana.
    cents: desvío respecto de esa nota, de -50 a +50.
    """
    midi = 69 + 12 * math.log2(frecuencia / configuracion.LA_REFERENCIA)
    midi_cercano = round(midi)
    cents = (midi - midi_cercano) * 100
    nota = midi_cercano % 12
    return nota, cents


def detectar_frecuencia(muestras, fs):
    """
    Busca el período de la nota con el método YIN (autocorrelación).

    muestras: arreglo numpy mono. fs: frecuencia de muestreo en Hz.
    Devuelve (frecuencia, claridad):
    - frecuencia: en Hz, entre NOTA_FRECUENCIA_MINIMA y NOTA_FRECUENCIA_MAXIMA,
      o None si no hay una nota clara (silencio, ruido, fuera de rango).
    - claridad: 0 = la onda se repite perfecta, ~1 = no se repite nada.
      Con nota es la del período encontrado; sin nota, la mejor que hubo.
    """
    n = len(muestras)
    tau_min = int(fs / configuracion.NOTA_FRECUENCIA_MAXIMA)
    tau_max = math.ceil(fs / configuracion.NOTA_FRECUENCIA_MINIMA)

    x = muestras - numpy.mean(muestras)                 # sacar la continua


    # 1. Autocorrelación r(τ) con FFT (relleno a 2n para que no "dé la vuelta")
    r = numpy.fft.irfft(numpy.abs(numpy.fft.rfft(x, 2 * n)) ** 2) [0:tau_max + 2]  # r[0] … r[tau_max]

    # 2. Energía acumulada: c[k] = suma de x² de las primeras k muestras (c[0] = 0)
    c = numpy.concatenate(([0.0], numpy.cumsum(x**2)))
    # Silencio: sin energía, d sería 0 en todos lados y parecería una
    # repetición perfecta (daría 1000 Hz). No hay nota.
    if c[n] == 0:
        return None, 1.0
    tau = numpy.arange(tau_max + 2)
    d = c[n - tau] + (c[n] - c[tau]) - 2*r            # d(τ) para todos los τ de una

    # 3. Normalizar (diferencia acumulada media): 0 = repetición perfecta, ~1 = nada
    # dn[τ] = d[τ] · τ / (d[1] + … + d[τ]); el maximum evita dividir por 0.
    dn = numpy.ones_like(d)
    dn[1:] = d[1:] * tau[1:] / numpy.maximum(numpy.cumsum(d[1:]), 1e-12)

    # 4. Primer τ dentro del rango que baje del umbral
    candidatos = numpy.where(dn[tau_min:tau_max + 1] < configuracion.NOTA_UMBRAL_CLARIDAD)[0]
    if len(candidatos) == 0:
        return None, float(numpy.min(dn[tau_min:tau_max + 1]))
    k = candidatos[0] + tau_min
    while k < tau_max and dn[k+1] < dn[k]: k += 1    # bajar hasta el fondo del pozo

    # 5. Interpolar una parábola por los 3 puntos para tener τ con decimales
    a, b, c3 = dn[k-1], dn[k], dn[k+1]
    denominador = a - 2*b + c3
    # Si los 3 puntos están alineados no hay parábola: se queda con k.
    k_fino = k + 0.5*(a - c3) / denominador if denominador != 0 else k
    return fs / k_fino, float(dn[k])


def estimar(muestras, frecuencia_muestreo, afinador, lados=None):
    """
    Devuelve (nota, frecuencia, cents) para las últimas muestras de audio.

    muestras: arreglo numpy mono con las últimas TAMANO_VENTANA muestras.
    afinador: 1 = busca una sola nota con YIN (para afinar un instrumento);
              0 = raíz del acorde que suena (croma comparada con plantillas
                  de acordes); con una nota sola, esa nota.
    lados: las mismas muestras de (izquierdo - derecho) / 2, o None si el
           audio es mono. En modo nota, si los lados no están más de
           CROMA_UMBRAL_LADOS_DB por debajo de la mezcla, se usan en lugar
           de la mezcla: así se ignora la voz, que casi siempre va al centro.
    nota: 0 a 11 (C…B) o configuracion.SIN_NOTA si no hay una nota clara.
    frecuencia: frecuencia estimada en Hz (promediada), o None. Solo con afinador.
    cents: desvío respecto de la nota exacta, de -50 a +50, o None. Solo con afinador.
    """
    global croma_suave, nota_actual, bloques_plana, candidata, bloques_candidata, frecuencia_suave

    # 1. Puerta de volumen: en silencio o con un ruido de fondo muy bajo, no
    # hay nota. Se borran los promedios para que la próxima nota arranque limpia.
    volumen_db = 10 * math.log10(numpy.mean(muestras**2) + 1e-12)
    if volumen_db < configuracion.NOTA_VOLUMEN_MINIMO_DB:
        croma_suave = numpy.zeros(12)
        nota_actual = configuracion.SIN_NOTA
        bloques_plana = 0
        candidata = None
        bloques_candidata = 0
        frecuencia_suave = None
        return configuracion.SIN_NOTA, None, None

    if afinador:
        # 2. Buscar la frecuencia con YIN y pasar la puerta de claridad.
        frecuencia, claridad = detectar_frecuencia(muestras, frecuencia_muestreo)
        if frecuencia is None or claridad > configuracion.NOTA_UMBRAL_CLARIDAD:
            frecuencia_suave = None
            return configuracion.SIN_NOTA, None, None
        # 3. Promedio para que la aguja no tiemble. Si saltó más de medio
        # semitono es otra nota: arranca de cero en vez de arrastrar la anterior.
        if frecuencia_suave is None or abs(1200 * math.log2(frecuencia / frecuencia_suave)) > 50:
            frecuencia_suave = frecuencia
        else:
            frecuencia_suave = (configuracion.PROMEDIO_AFINADOR * frecuencia_suave
                                + (1 - configuracion.PROMEDIO_AFINADOR) * frecuencia)
        # 4. A nota y cents (paso 1)
        nota, cents = a_nota(frecuencia_suave)
        return nota, frecuencia_suave, cents

    # Modo nota. Si hay estéreo de verdad (guitarras abiertas a los
    # costados), se usan los lados: la voz al centro se cancela. Si todo
    # está al centro (los lados casi vacíos), se sigue con la mezcla.
    senal = muestras
    if lados is not None:
        lados_db = 10 * math.log10(numpy.mean(lados**2) + 1e-12)
        if lados_db - volumen_db > configuracion.CROMA_UMBRAL_LADOS_DB:
            senal = lados

    # Croma repartida (suma 1) y promediada entre bloques.
    c = croma(senal)
    c = c / c.sum()
    croma_suave = configuracion.PROMEDIO_CROMA * croma_suave + (1 - configuracion.PROMEDIO_CROMA) * c
    reparto = croma_suave / croma_suave.sum()
    if reparto.max() < configuracion.CROMA_MINIMA:
        # Croma plana (ruido, percusión): ninguna nota se destaca. No se
        # apaga enseguida, porque eso hace parpadear la nota con cada
        # rasguido: solo después de CROMA_ESPERA_SIN_NOTA bloques seguidos.
        bloques_plana += 1
        if bloques_plana >= configuracion.CROMA_ESPERA_SIN_NOTA:
            nota_actual = configuracion.SIN_NOTA
    else:
        bloques_plana = 0
        # La nota es la raíz del acorde que mejor coincide, no la nota más
        # fuerte (esa suele ser la quinta).
        puntajes = puntajes_raiz(croma_suave)
        lider = int(numpy.argmax(puntajes))
        if nota_actual == configuracion.SIN_NOTA:
            # No había nota: la primera que aparece se muestra enseguida.
            nota_actual = lider
            candidata = None
        elif lider != nota_actual and puntajes[lider] - puntajes[nota_actual] > configuracion.CROMA_MARGEN_CAMBIO:
            # Histéresis: la raíz nueva tiene que ganarle con claridad a la
            # actual durante CROMA_BLOQUES_CAMBIO bloques seguidos; si no, dos
            # acordes parecidos se turnarían (pasaba con Clair de lune).
            if lider == candidata:
                bloques_candidata += 1
            else:
                candidata = lider
                bloques_candidata = 1
            if bloques_candidata >= configuracion.CROMA_BLOQUES_CAMBIO:
                nota_actual = lider
                candidata = None
        else:
            # La actual sigue ganando (o empatada): se olvida la candidata.
            candidata = None
    return nota_actual, None, None


# Pruebas sin audio: solo se ejecutan con `python pc/nota.py`. Usan señales
# sintéticas (tonos, acordes de guitarra, ruido y voz) con semillas fijas.
if __name__ == "__main__":
    import time
    fs = configuracion.FRECUENCIA_MUESTREO
    n = configuracion.TAMANO_VENTANA
    bloque = configuracion.TAMANO_BLOQUE
    SIN = configuracion.SIN_NOTA
    CUERDA = (1, 0.7, 0.5, 0.4, 0.3, 0.2, 0.15, 0.1)   # armónicos de una cuerda de guitarra
    errores = 0

    def revisar(bien, nombre, obtenido, esperado):
        """Imprime una línea OK / ERROR y cuenta los errores."""
        global errores
        errores += 0 if bien else 1
        print(f"{'OK   ' if bien else 'ERROR'} {nombre:<36} → {obtenido}   (esperado {esperado})")

    def hz(midi):
        """Nota MIDI (con decimales para desafinar) → Hz."""
        return 440 * 2 ** ((midi - 69) / 12)

    def senal(frecuencias, largo=n, armonicos=(1,), rasguido=None, desfase=0.0, db=0.0, semilla=0):
        """
        Suma de notas (Hz) con sus armónicos, normalizada a `db` dB de volumen.
        rasguido: cada cuántos segundos se rasguea (la nota se apaga entre rasguidos).
        """
        t = numpy.arange(largo) / fs
        t_nota = (t + desfase) % rasguido if rasguido else t
        fases = numpy.random.default_rng(semilla).uniform(0, 6, (len(frecuencias), len(armonicos)))
        x = sum(a * numpy.sin(2 * numpy.pi * f * (i + 1) * t_nota + fases[j, i])
                for j, f in enumerate(frecuencias) for i, a in enumerate(armonicos))
        if rasguido:
            x = x * numpy.exp(-4 * t_nota)
        return x / x.std() * 10 ** (db / 20)

    def ruido(largo, rosa=False, db=0.0, semilla=0):
        """Ruido blanco o rosa (más graves, como una sala o una mezcla) a `db` dB."""
        x = numpy.random.default_rng(semilla).standard_normal(largo)
        if rosa:
            espectro = numpy.fft.rfft(x)
            x = numpy.fft.irfft(espectro / numpy.sqrt(numpy.arange(len(espectro)) + 1), largo)
        return x / x.std() * 10 ** (db / 20)

    def en_vivo(izquierdo, derecho=None, afinador=0):
        """Pasa un audio bloque a bloque como principal.py (con lados si es estéreo) y devuelve los resultados."""
        estimar(numpy.zeros(n), fs, afinador)   # silencio: arranca sin promedios
        derecho = izquierdo if derecho is None else derecho
        memoria, memoria_lados, resultados = numpy.zeros(n), numpy.zeros(n), []
        for inicio in range(0, len(izquierdo) - bloque + 1, bloque):
            i, d = izquierdo[inicio:inicio + bloque], derecho[inicio:inicio + bloque]
            memoria[:-bloque], memoria[-bloque:] = memoria[bloque:], (i + d) / 2
            memoria_lados[:-bloque], memoria_lados[-bloque:] = memoria_lados[bloque:], (i - d) / 2
            resultados.append(estimar(memoria, fs, afinador, memoria_lados))
        return resultados[n // bloque:]   # sin los bloques con la memoria a medio llenar

    def repetir(ventana, veces, nivel_ruido=0.0, semilla=0):
        """Llama a estimar() en modo nota `veces` seguidas con la misma ventana (+ ruido nuevo)."""
        generador = numpy.random.default_rng(semilla)
        return [estimar(ventana + nivel_ruido * generador.standard_normal(n), fs, 0)[0] for _ in range(veces)]

    def nombre(x):
        return configuracion.NOMBRES_NOTAS[x] if x in range(12) else "—"

    def cambios(notas):
        return sum(a != b for a, b in zip(notas, notas[1:]))

    def acierto_por_tramo(notas, raices, bloques_tramo, margen=12):
        """% de bloques con la raíz correcta en cada tramo, sin los primeros `margen` (para cambiar)."""
        aciertos = []
        for k, raiz in enumerate(raices):
            desde = max(0, k * bloques_tramo - n // bloque) + margen
            tramo = notas[desde:(k + 1) * bloques_tramo - n // bloque]
            aciertos.append(numpy.mean([x == raiz for x in tramo]))
        return numpy.mean(aciertos) * 100

    # --- a_nota(): Hz → (nota, cents) ---
    for frecuencia, esperada, cents_esperados in [(440, 9, 0), (261.63, 0, 0), (450, 9, 39), (453, 10, -50)]:
        nota, cents = a_nota(frecuencia)
        revisar(isinstance(nota, int) and nota == esperada and abs(cents - cents_esperados) <= 1,
                f"a_nota({frecuencia})", f"{nombre(nota)} {cents:+.1f} c", f"{nombre(esperada)} {cents_esperados:+d} c")

    # --- detectar_frecuencia(): YIN. None = no tiene que haber nota ---
    print()
    voz = (1, 0.6, 0.4, 0.2)
    casos = [("A4", senal([440]), 440, 5),
             ("E2 guitarra, fundamental débil", senal([82.41], armonicos=(0.3, 1, 0.8, 0.6, 0.4)), 82.41, 5),
             ("G3 desafinado +5 c", senal([hz(55.05)]), hz(55.05), 5),
             # Con ruido, un bloque solo se desvía hasta ~12 c (medido); el afinador lo promedia.
             ("A4 voz con ruido", senal([440], armonicos=voz) + ruido(n, db=-10), 440, 15),
             ("C2 bajo", senal([65.41], armonicos=(1, 0.7, 0.5)), 65.41, 5),
             ("B5", senal([987.77], armonicos=(1, 0.3)), 987.77, 5),
             ("Silencio", numpy.zeros(n), None, 0),
             ("Ruido blanco", ruido(n), None, 0),
             ("40 Hz, fuera de rango", senal([40]), None, 0)]
    for nombre_caso, x, esperada, tolerancia in casos:
        frecuencia, claridad = detectar_frecuencia(x, fs)
        if esperada is None:
            revisar(frecuencia is None, nombre_caso, f"{frecuencia}, claridad {claridad:.2f}", "None")
        else:
            desvio = 1200 * math.log2(frecuencia / esperada) if frecuencia else None
            revisar(desvio is not None and abs(desvio) <= tolerancia, nombre_caso,
                    f"{frecuencia} Hz" if desvio is None else f"{frecuencia:.2f} Hz ({desvio:+.1f} c)",
                    f"{esperada:.2f} Hz ± {tolerancia} c")
    inicio = time.perf_counter()
    for _ in range(100):
        detectar_frecuencia(senal([440]), fs)
    milisegundos = (time.perf_counter() - inicio) * 10
    revisar(milisegundos < 2, "Tiempo por llamada (bloque = 21 ms)", f"{milisegundos:.2f} ms", "< 2 ms")

    # --- estimar() con el afinador: puerta de volumen y aguja ---
    print()
    for db, esperada in [(-10, 9), (-55, 9), (-70, SIN)]:
        resultado = estimar(senal([440], db=db), fs, 1)
        revisar(resultado[0] == esperada and (esperada == SIN) == (resultado[2] is None),
                f"Afinador: A4 a {db} dB", repr(resultado[0]), nombre(esperada))
    # Con ruido, la aguja tiene que quedar quieta gracias al promedio (sin él: 3,2 c).
    tono_a = senal([440], armonicos=voz)
    resultados = en_vivo(numpy.concatenate([tono_a + ruido(n, db=-10, semilla=s) for s in range(60)]), afinador=1)
    cents_vistos = numpy.array([r[2] for r in resultados[10:]], dtype=float)
    revisar(cents_vistos.std() < 2, "Afinador: aguja quieta con ruido", f"desvío típico {cents_vistos.std():.1f} c", "< 2 c")
    # Al cambiar de nota no tiene que arrastrar el promedio de la anterior.
    resultado = estimar(senal([329.63]), fs, 1)
    revisar(resultado[0] == 4 and abs(resultado[2]) <= 5, "Afinador: A4 → E4 en un bloque",
            f"{nombre(resultado[0])} {resultado[2]:+.1f} c", "E ± 5 c")

    # --- puntajes_raiz(): la raíz del acorde, no la nota más fuerte (G en un C) ---
    print()
    piano = (1, 0.5, 0.33, 0.25)
    acorde_c = senal([hz(m) for m in (60, 64, 67)], armonicos=piano)
    for nombre_caso, x, raiz in [("C mayor", acorde_c, 0), ("A menor", senal([hz(m) for m in (57, 60, 64)], armonicos=piano), 9),
                                 ("D mayor abierto", senal([hz(m) for m in (50, 57, 62, 66)], armonicos=piano), 2),
                                 ("Nota sola A4", senal([440]), 9)]:
        p = puntajes_raiz(croma(x))
        gana = int(numpy.argmax(p))
        revisar(len(p) == 12 and gana == raiz and 0 <= p.min() and p.max() <= 1 + 1e-9,
                f"puntajes_raiz: {nombre_caso}", f"gana {nombre(gana)} ({p[gana]:.2f})", nombre(raiz))

    # --- Modo nota en vivo ---
    print()
    notas = [r[0] for r in en_vivo(ruido(fs, db=-10, semilla=9))]
    revisar(all(x == SIN for x in notas), "Ruido blanco (croma plana)", f"{notas.count(SIN)}/{len(notas)} sin nota", "todos sin nota")
    revisar(estimar(numpy.zeros(n), fs, 0) == (SIN, None, None), "Silencio", "", "(SIN_NOTA, None, None)")

    # Guitarra D3 rasgueada cada 1 s con ruido de sala: antes la nota se
    # prendía y apagaba con cada rasguido (D el 35% del tiempo).
    x = senal([146.83], int(8 * fs), armonicos=(0.5, 1, 0.7, 0.5, 0.35, 0.25, 0.15), rasguido=1.0)
    notas = [r[0] for r in en_vivo(x + ruido(len(x), rosa=True, db=-5, semilla=3))]
    en_d = notas.count(2) * 100 / len(notas)
    revisar(en_d >= 90 and cambios(notas) <= 2, "Guitarra rasgueada con ruido", f"D {en_d:.0f}%, {cambios(notas)} cambios", "D ≥ 90%, ≤ 2 cambios")

    # F → G con ruido tan fuerte como la música: antes, sin nota el 95%.
    x = numpy.concatenate([senal([hz(m) for m in acorde], 3 * fs, armonicos=piano) for acorde in ((53, 57, 60), (55, 59, 62))])
    notas = [r[0] for r in en_vivo(x + ruido(len(x), rosa=True, semilla=4))]
    sin_nota = notas.count(SIN) * 100 / len(notas)
    acierto = acierto_por_tramo(notas, [5, 7], 3 * fs // bloque, margen=20)
    revisar(sin_nota <= 10 and acierto >= 80 and cambios(notas) <= 6, "F → G con mucho ruido",
            f"sin nota {sin_nota:.0f}%, raíz {acierto:.0f}%, {cambios(notas)} cambios", "sin nota ≤ 10%, raíz ≥ 80%, ≤ 6 cambios")

    # Mantener: con ruido solo, la nota sigue ~1 s y recién después se apaga.
    estimar(numpy.zeros(n), fs, 0)
    repetir(senal([440]), 10)
    espera = configuracion.CROMA_ESPERA_SIN_NOTA
    notas = repetir(numpy.zeros(n), espera + 20, nivel_ruido=0.4, semilla=11)
    dura = next((k for k, v in enumerate(notas) if v != 9), len(notas))
    revisar(dura >= espera - 15 and notas[-1] == SIN, "Mantiene la nota y después se apaga",
            f"A durante {dura} bloques, al final {nombre(notas[-1])}", f"A ≥ {espera - 15} bloques, después sin nota")

    # Espera: un acorde que asoma 5 bloques (menos que CROMA_BLOQUES_CAMBIO) no cambia la nota.
    estimar(numpy.zeros(n), fs, 0)
    acorde_g = senal([hz(m) for m in (55, 59, 62)], armonicos=piano)
    notas = repetir(acorde_c, 30, 0.02, 13) + repetir(acorde_g, 5, 0.02, 14) + repetir(acorde_c, 20, 0.02, 15)
    revisar(all(v == 0 for v in notas[5:]), "G corto en medio de C", " ".join(sorted({nombre(v) for v in notas[5:]})), "solo C")

    # Acordes abiertos de guitarra con ruido de sala: con la nota más fuerte
    # daba la raíz el 28–36% (C → G, D → A, Am → E).
    abiertos = [(0, (48, 52, 55, 60, 64)), (7, (43, 47, 50, 55, 59, 67)), (9, (45, 52, 57, 60, 64)),
                (5, (41, 48, 53, 57, 60, 65)), (2, (50, 57, 62, 66)), (4, (40, 47, 52, 55, 59, 64)),
                (11, (47, 51, 57, 59, 66))]   # C G Am F D Em B7
    x = numpy.concatenate([senal([hz(m) for m in midis], 2 * fs, CUERDA, rasguido=1.0, semilla=k)
                           for k, (_, midis) in enumerate(abiertos)])
    notas = [r[0] for r in en_vivo(x + ruido(len(x), rosa=True, db=-10, semilla=5))]
    acierto = acierto_por_tramo(notas, [r for r, _ in abiertos], 2 * fs // bloque)
    # Demora de cada cambio de acorde: bloques hasta mostrar la raíz nueva.
    demoras = []
    for k, (raiz, _) in enumerate(abiertos[1:], start=1):
        cambio = k * 2 * fs // bloque - n // bloque
        demoras.append(next((j for j, v in enumerate(notas[cambio:]) if v == raiz), 99))
    revisar(acierto >= 90 and cambios(notas) <= 18 and max(demoras) <= 20, "Acordes abiertos de guitarra",
            f"raíz {acierto:.0f}%, {cambios(notas)} cambios, demora máx {max(demoras)} bloques",
            "raíz ≥ 90%, ≤ 18 cambios, demora ≤ 20 bloques (~0,4 s)")

    # Estéreo: guitarra grabada dos veces, una a cada lado, y voz al centro
    # 6 dB más fuerte con vibrato. Con los lados (L − R) la voz se cancela.
    progresion = abiertos[:4]   # C G Am F
    tomas = [numpy.concatenate([senal([hz(m) for m in midis], 2 * fs, CUERDA, rasguido=0.5, desfase=desfase, semilla=10 * d + k)
                                for k, (_, midis) in enumerate(progresion)]) for d, desfase in enumerate((0.0, 0.03))]
    t = numpy.arange(len(tomas[0])) / fs
    melodia = numpy.array([60, 62, 64, 65, 67, 64, 62, 59, 60, 57, 59, 62, 64, 67, 65, 62, 64, 65, 67, 69])
    f_voz = hz(melodia[numpy.minimum((t / 0.4).astype(int), len(melodia) - 1)]) * 2 ** (40 * numpy.sin(2 * numpy.pi * 5.5 * t) / 1200)
    fase = 2 * numpy.pi * numpy.cumsum(f_voz) / fs
    voz_centro = sum(a * numpy.sin((i + 1) * fase) for i, a in enumerate((1, 0.6, 0.45, 0.3, 0.2, 0.12)))
    voz_centro *= 10 ** (6 / 20) * 0.5 / voz_centro.std()
    izquierdo = 0.7 * tomas[0] + 0.15 * tomas[1] + voz_centro
    derecho = 0.15 * tomas[0] + 0.7 * tomas[1] + voz_centro
    raices = [r for r, _ in progresion]
    notas = [r[0] for r in en_vivo(izquierdo, derecho)]
    solo_mezcla = [r[0] for r in en_vivo((izquierdo + derecho) / 2)]
    acierto = acierto_por_tramo(notas, raices, 2 * fs // bloque)
    revisar(acierto >= 70 and cambios(notas) <= 10, "Estéreo: voz al centro",
            f"raíz {acierto:.0f}%, {cambios(notas)} cambios (sin lados: {acierto_por_tramo(solo_mezcla, raices, 2 * fs // bloque):.0f}%)",
            "raíz ≥ 70%, ≤ 10 cambios")
    # Todo al centro: los lados quedan vacíos y tiene que dar lo mismo que la mezcla.
    centro = 0.5 * (tomas[0] + tomas[1]) + voz_centro
    revisar(en_vivo(centro, centro) == en_vivo(centro), "Estéreo: todo al centro usa la mezcla", "", "igual que mono")

    print()
    print("Todo bien" if errores == 0 else f"{errores} errores")
