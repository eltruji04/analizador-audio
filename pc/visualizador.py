"""
visualizador.py — Ventana de la compu: espectro, espejo de la OLED y panel de control.

Abre la ventana, atiende el mouse y el teclado y, en cada cuadro, copia
del estado los últimos datos del audio y le pide a dibujo.py que dibuje
cada zona. Usa pygame.

Los clics y las teclas cambian el estado con estado.cambiar(..., "compu"),
la misma función que usan los botones del Arduino y Blynk.

En macOS la ventana solo se puede manejar desde el hilo principal: por
eso dibujar() se llama desde el bucle principal, nunca desde el callback
de audio.
"""

import collections
import time
import numpy
import pygame
import bandas
import colores
import configuracion
import dibujo
import estado
import golpe

# Teclas y la acción de cada una (todas con origen "compu").
TECLAS = {
    pygame.K_SPACE: lambda: estado.alternar("pausa", "compu"),
    pygame.K_p: lambda: estado.alternar("pico", "compu"),
    pygame.K_g: lambda: estado.alternar("golpe", "compu"),
    pygame.K_a: lambda: estado.alternar("afinador", "compu"),
    pygame.K_f: lambda: estado.siguiente("forma", "compu"),
    pygame.K_c: lambda: estado.siguiente("color", "compu"),
    pygame.K_v: lambda: estado.siguiente("velocidad", "compu"),
    pygame.K_r: lambda: estado.pedir_recalibracion("compu"),
    # Fuente: alterna entre MIC y LINE (MODO_MIC = 0, MODO_LINE = 1).
    pygame.K_i: lambda: estado.alternar("fuente", "compu"),
    # Pantalla completa: no es estado del sistema, solo de esta ventana.
    pygame.K_z: lambda: alternar_pantalla_completa(),
}

# Ventana. La crea iniciar(); empieza vacía.
pantalla = None
# Últimas alturas para el espectrograma: se agrega una cada
# DURACION_HISTORIAL / LARGO_HISTORIAL segundos (~47 ms), así los 64
# cuadros abarcan unos 3 s sin importar los FPS.
historial = collections.deque(maxlen=configuracion.LARGO_HISTORIAL)
ultimo_historial = 0    # momento en que se agregó el último cuadro al historial
# Para medir los cuadros por segundo reales: cuántos se dibujaron desde
# inicio_cuadros y el último valor medido (se actualiza una vez por segundo).
cuadros = 0
inicio_cuadros = 0
fps = 0
# Texto extra del pie (por ejemplo "datos simulados").
aviso_pie = ""
# Con la tecla Z: solo el espectro, en grande y con la ventana a pantalla completa.
pantalla_completa = False


def iniciar():
    """Abre la ventana y prepara las fuentes de letra. Se llama una sola vez."""
    # Sin `global`, la asignación crearía una variable local y dibujar()
    # seguiría viendo pantalla en None.
    global pantalla
    pygame.init()
    # SCALED: el dibujo sigue siendo de 1280×840 aunque la ventana pase a
    # pantalla completa; pygame lo escala y ajusta las coordenadas del mouse.
    pantalla = pygame.display.set_mode((configuracion.ANCHO_VENTANA, configuracion.ALTO_VENTANA), pygame.SCALED)
    pygame.display.set_caption("Analizador de audio")
    dibujo.cargar_fuentes()


def alternar_pantalla_completa():
    """
    Entra o sale de la pantalla completa: la ventana ocupa todo el monitor
    y se dibuja solo el espectro, en grande. Si el sistema no deja poner la
    ventana a pantalla completa, igual cambia lo que se dibuja.
    """
    global pantalla_completa
    pantalla_completa = not pantalla_completa
    try:
        pygame.display.toggle_fullscreen()
    except pygame.error as error:
        print(f"No se pudo cambiar a pantalla completa: {error}")


def atender_eventos():
    """
    Lee los eventos de la ventana: clics en los botones y teclas. Devuelve
    False si se cerró la ventana. Hay que llamarla en cada cuadro: si no,
    macOS marca la ventana como "no responde".
    """
    for evento in pygame.event.get():
        if evento.type == pygame.QUIT:
            return False
        if evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
            # Los botones del último cuadro dibujado: el primero que contiene el mouse.
            for rect, accion in dibujo.botones:
                if rect.collidepoint(evento.pos):
                    accion()
                    break
        elif evento.type == pygame.KEYDOWN and evento.key in TECLAS:
            TECLAS[evento.key]()
        elif evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE and pantalla_completa:
            # Escape también sale de la pantalla completa.
            alternar_pantalla_completa()
    return True


def dibujar():
    """
    Atiende los eventos y dibuja un cuadro con los últimos datos del estado.

    Devuelve False si se cerró la ventana (con la ✕), True si no.
    """
    global ultimo_historial, cuadros, inicio_cuadros, fps
    if not atender_eventos():
        return False

    ahora = time.monotonic()
    # Se toma el diccionario una sola vez: el callback lo reemplaza entero.
    datos = estado.audio
    # Historial del espectrograma: un cuadro cada DURACION_HISTORIAL / LARGO_HISTORIAL s.
    if ahora - ultimo_historial >= configuracion.DURACION_HISTORIAL / configuracion.LARGO_HISTORIAL:
        historial.append(datos["alturas"])
        ultimo_historial = ahora

    pantalla.fill(colores.FONDO)
    # Se vuelven a anotar en cada cuadro, al dibujar el panel.
    dibujo.botones.clear()
    if pantalla_completa:
        # Solo el espectro: sin panel no hay botones, pero las teclas siguen andando.
        dibujo.espectro(pantalla, datos, historial, ahora, dibujo.ESPECTRO_COMPLETO)
        dibujo.aviso_pantalla_completa(pantalla)
        pygame.display.flip()
        return True
    dibujo.encabezado(pantalla)
    dibujo.espectro(pantalla, datos, historial, ahora)
    dibujo.espejo_oled(pantalla)
    dibujo.tarjeta_nota(pantalla, datos)
    dibujo.panel(pantalla)

    # Cada 1 s se calculan los FPS reales y se vuelve a contar.
    cuadros += 1
    if ahora - inicio_cuadros >= 1:
        fps = cuadros / (ahora - inicio_cuadros)
        cuadros = 0
        inicio_cuadros = ahora
    dibujo.pie(pantalla, f"{fps:.0f} FPS" + (f" · {aviso_pie}" if aviso_pie else ""))

    # Hasta acá todo se dibujó en memoria: flip() lo muestra en la ventana.
    pygame.display.flip()
    return True


def cerrar():
    """Cierra la ventana y libera pygame."""
    pygame.quit()


# --- Prueba con datos simulados (sin audio ni Arduino) ------------------------

# Momentos de los golpes inventados, para calcular el tempo como con audio real.
golpes_simulados = collections.deque(maxlen=64)

def simular(ahora, dt, mostradas, destello, picos, ultimo_golpe):
    """
    Inventa los datos de un cuadro como si vinieran del audio: barras que
    se mueven como ondas, un golpe cada 0,5 s (120 BPM), una nota distinta
    cada 2 s y un desvío en cents que oscila. Usa `inicio`, el momento
    en que empezó la prueba. Devuelve el momento del último golpe.
    """
    t = ahora - inicio
    posiciones = numpy.arange(configuracion.CANTIDAD_BARRAS)
    alturas = 14 + 10 * numpy.sin(2.2 * t - posiciones * 0.5) + 6 * numpy.sin(5.3 * t + posiciones)
    alturas = numpy.clip(alturas + numpy.random.uniform(-2, 2, len(alturas)), 0, configuracion.ALTURA_MAXIMA)

    # La caída está pensada por bloque de audio (~21 ms): se ajusta a la duración del cuadro.
    bloques = dt / (configuracion.TAMANO_BLOQUE / configuracion.FRECUENCIA_MUESTREO)
    caida = configuracion.VELOCIDADES_CAIDA[estado.velocidad] * bloques
    bandas.suavizar(mostradas, alturas, caida)
    bandas.suavizar(destello, numpy.zeros(len(destello)), caida)
    for _ in range(max(1, round(bloques))):
        bandas.actualizar_picos(picos, mostradas)

    if ahora - ultimo_golpe >= 0.5:
        ultimo_golpe = ahora
        golpes_simulados.append(ahora)
        if estado.golpe:
            destello[configuracion.BARRAS_GOLPE] = configuracion.ALTURA_MAXIMA
    # Como en principal.py: el golpe solo se marca con el efecto activo.
    momento_golpe = ultimo_golpe if estado.golpe else None

    nota = int(t // 2) % 12
    cents = 20 * numpy.sin(t * 1.3)
    # Octava 3: midi de C3 = 48.
    frecuencia = 440 * 2 ** ((48 + nota - 69 + cents / 100) / 12)
    # Nivel general: entre −30 y −6 dB más o menos, que sube con cada golpe.
    nivel = -18 + 8 * numpy.sin(t * 0.7) + (6 if ahora - ultimo_golpe < 0.1 else 0)
    bpm = golpe.estimar_bpm(golpes_simulados, ahora)
    estado.publicar_audio(mostradas, destello, picos, nota, frecuencia, cents, momento_golpe, nivel, bpm)
    return ultimo_golpe


if __name__ == "__main__":
    # Solo se ejecuta con `python pc/visualizador.py`: la ventana completa
    # con datos inventados, para probar el dibujo y el panel sin audio.
    # Se cierra con la ✕.
    import serie
    estado.cargar_preferencias()
    iniciar()
    aviso_pie = "datos simulados"
    print("Prueba del visualizador con datos simulados: se cierra con la ✕ de la ventana")
    reloj = pygame.time.Clock()
    mostradas = numpy.zeros(configuracion.CANTIDAD_BARRAS)
    destello = numpy.zeros(configuracion.CANTIDAD_BARRAS)
    picos = numpy.zeros(configuracion.CANTIDAD_BARRAS)
    inicio = time.monotonic()   # la usa simular() para el tiempo de la prueba
    anterior = inicio           # momento del cuadro anterior, para saber cuánto duró
    ultimo_golpe = 0            # momento del último golpe inventado
    pausa_enviada = False       # como en principal.py: el paquete de pausa sale una sola vez
    while True:
        ahora = time.monotonic()
        ultimo_golpe = simular(ahora, ahora - anterior, mostradas, destello, picos, ultimo_golpe)
        anterior = ahora
        # Mismo criterio que principal.py: en pausa, un último paquete y nada más.
        if not estado.pausa or not pausa_enviada:
            salida = numpy.maximum(mostradas, destello)
            paquete = serie.armar_paquete(salida, estado.fuente, estado.audio["nota"], estado.pausa, estado.pico, estado.forma_oled)
            estado.publicar_paquete(paquete, picos)
            pausa_enviada = bool(estado.pausa)
        if not dibujar():
            break
        # Espera lo que falte para dibujar unos 30 cuadros por segundo.
        reloj.tick(1 / configuracion.INTERVALO_DIBUJO)
    cerrar()
