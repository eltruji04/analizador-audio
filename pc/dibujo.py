"""
dibujo.py — Una función por zona de la ventana del visualizador.

Zonas (en píxeles, ventana de 1280×840):
- encabezado: arriba, alto 68 (título, último cambio, Arduino, Blynk, fuente);
- espectro: x 24–916, y 88–514, en la forma elegida;
- espejo de la OLED: x 24–596, y 534–770 (128×32 escalado ×3);
- nota / afinador: x 616–916, y 534–770;
- panel de control: x 936–1256, y 88–816.

Estas funciones solo dibujan: leen el estado y los datos que les pasa
visualizador.py. Los botones del panel se anotan en `botones` (rectángulo
y función a llamar) para que visualizador.py sepa qué se clicó.
"""

import math
import time
import numpy
import pygame
import configuracion
import colores
import estado

ESPECTRO = pygame.Rect(24, 88, 892, 426)
ESPEJO = pygame.Rect(24, 534, 572, 236)
NOTA = pygame.Rect(616, 534, 300, 236)
PANEL = pygame.Rect(936, 88, 320, 728)

# Pantalla completa (tecla Z): el espectro ocupa casi toda la ventana.
ESPECTRO_COMPLETO = pygame.Rect(16, 16, 1248, 796)
# Columna a la izquierda del espectrograma para las frecuencias.
ANCHO_FRECUENCIAS = 40
# Ancho del medidor de nivel, al lado del título del espectro.
ANCHO_MEDIDOR = 160

ESCALA_OLED = 3
ANCHO_OLED = 128
ALTO_OLED = 32
# En la OLED: 16 barras de 5 px con 1 px de separación (96 px) y el texto a la derecha.
ANCHO_BARRA_OLED = 6
# Supuesto hasta que Lucía defina la pantalla real.
X_TEXTO_OLED = 98

NOMBRES_FORMAS = {"barras": "Barras", "centro": "Desde el centro",
                  "onda": "Onda", "espectrograma": "Espectrograma"}
NOMBRES_COLORES = {"fijo": "Fijo", "arcoiris": "Arcoíris", "nota": "Por nota"}

# Fuentes de letra: las carga cargar_fuentes(), después de pygame.init().
fuentes = {}
# Textos ya dibujados, para no volver a armarlos en cada cuadro.
_cache_textos = {}
# Botones del cuadro actual: lista de (rectángulo, función sin parámetros).
botones = []
# Superficies con transparencia, una por tamaño (se crean la primera vez).
_capas = {}


def cargar_fuentes():
    """
    Carga las fuentes. El diseño usa Inter y JetBrains Mono; si no están
    instaladas, SysFont prueba las siguientes de la lista y, al final, usa
    la de pygame.
    """
    sans = "inter,helveticaneue,helvetica,arial,dejavusans"
    mono = "jetbrainsmono,menlo,dejavusansmono,couriernew"
    fuentes["titulo"] = pygame.font.SysFont(sans, 22, bold=True)
    fuentes["normal"] = pygame.font.SysFont(sans, 15)
    fuentes["negrita"] = pygame.font.SysFont(sans, 15, bold=True)
    fuentes["chica"] = pygame.font.SysFont(sans, 13)
    fuentes["mono"] = pygame.font.SysFont(mono, 14)
    fuentes["mono_chica"] = pygame.font.SysFont(mono, 11)
    fuentes["grande"] = pygame.font.SysFont(sans, 76, bold=True)
    fuentes["mediana"] = pygame.font.SysFont(mono, 20, bold=True)
    # La OLED se dibuja a 128×32 y se escala: sin suavizado, como píxeles.
    fuentes["oled"] = pygame.font.Font(None, 14)


def texto(superficie, contenido, fuente, color, posicion, ancla="topleft", suave=True):
    """
    Escribe `contenido` con la fuente `fuente` (clave de `fuentes`).
    `ancla` dice qué punto del texto va en `posicion` ("topleft",
    "topright", "center", "midleft"…). Devuelve el rectángulo ocupado.
    """
    clave = (contenido, fuente, color, suave)
    if clave not in _cache_textos:
        _cache_textos[clave] = fuentes[fuente].render(contenido, suave, color)
    imagen = _cache_textos[clave]
    rect = imagen.get_rect(**{ancla: posicion})
    superficie.blit(imagen, rect)
    return rect


def capa(ancho, alto, nombre=""):
    """
    Superficie transparente de ese tamaño, vacía, para dibujar con opacidad.
    Con `nombre` distinto se obtienen dos capas del mismo tamaño a la vez.
    """
    clave = (ancho, alto, nombre)
    if clave not in _capas:
        _capas[clave] = pygame.Surface((ancho, alto), pygame.SRCALPHA)
    _capas[clave].fill((0, 0, 0, 0))
    return _capas[clave]


def tarjeta(superficie, rect, titulo=None, detalle=None, fondo=colores.TARJETA):
    """Fondo de una zona: rectángulo redondeado con borde y título opcional."""
    pygame.draw.rect(superficie, fondo, rect, border_radius=10)
    pygame.draw.rect(superficie, colores.BORDE, rect, width=1, border_radius=10)
    if titulo:
        texto(superficie, titulo, "negrita", colores.TEXTO, (rect.x + 16, rect.y + 12))
    if detalle:
        texto(superficie, detalle, "chica", colores.TEXTO_SECUNDARIO, (rect.right - 16, rect.y + 14), "topright")


def nombre_frecuencia(hz):
    """40 → "40", 1300 → "1,3k" (con coma decimal)."""
    if hz < 1000:
        return f"{hz}"
    return f"{hz / 1000:g}k".replace(".", ",")


def nombre_nota(nota):
    """0–11 → "C"…"B"; SIN_NOTA → "—"."""
    if nota == configuracion.SIN_NOTA:
        return "—"
    return configuracion.NOMBRES_NOTAS[nota]


def octava(frecuencia):
    """Octava de una frecuencia en notación científica (A4 = 440 Hz → 4)."""
    midi = round(69 + 12 * math.log2(frecuencia / 440))
    return midi // 12 - 1


# --- Encabezado --------------------------------------------------------------

def chip(superficie, derecha, y, contenido, color_punto):
    """Etiqueta redondeada con un punto de color, alineada a la derecha en `derecha`. Devuelve su x izquierda."""
    ancho = fuentes["chica"].size(contenido)[0] + 36
    rect = pygame.Rect(derecha - ancho, y, ancho, 28)
    pygame.draw.rect(superficie, colores.TARJETA, rect, border_radius=14)
    pygame.draw.rect(superficie, colores.BORDE, rect, width=1, border_radius=14)
    pygame.draw.circle(superficie, color_punto, (rect.x + 15, rect.centery), 5)
    texto(superficie, contenido, "chica", colores.TEXTO, (rect.x + 26, rect.centery), "midleft")
    return rect.x


def encabezado(superficie):
    """Título, rango de frecuencias, último cambio y estado de las conexiones."""
    minimo = configuracion.BANDAS[0][0]
    maximo = configuracion.BANDAS[-1][1]
    texto(superficie, "Analizador de audio", "titulo", colores.TEXTO, (24, 12))
    texto(superficie, f"{configuracion.CANTIDAD_BARRAS} bandas · {minimo} Hz – {maximo / 1000:g} kHz",
          "chica", colores.TEXTO_SECUNDARIO, (24, 42))

    # Chips de derecha a izquierda: fuente, Blynk, Arduino.
    x = 1256
    fuente = "MIC" if estado.fuente == configuracion.MODO_MIC else "LINE"
    x = chip(superficie, x, 10, f"Fuente: {fuente}", colores.ACTIVO) - 8
    x = chip(superficie, x, 10, "Blynk: " + ("conectado" if estado.blynk_conectado else "desconectado"),
             colores.CONECTADO if estado.blynk_conectado else colores.DESCONECTADO) - 8
    chip(superficie, x, 10, "Arduino: " + ("conectado" if estado.arduino_conectado else "desconectado"),
         colores.CONECTADO if estado.arduino_conectado else colores.DESCONECTADO)

    cambio, origen, _ = estado.ultimo_cambio
    linea = f"Último cambio: {cambio}" + (f" · desde {origen}" if origen else "")
    texto(superficie, linea, "chica", colores.TEXTO_SECUNDARIO, (1256, 46), "topright")
    pygame.draw.line(superficie, colores.BORDE, (0, 68), (1280, 68))


# --- Espectro ------------------------------------------------------------------

# Color que se está mostrando en cada banda (con decimales, para que la
# transición no se trabe al redondear) y momento del último cuadro.
_colores_mostrados = None
_momento_colores = None


def acercar_colores(objetivos, ahora):
    """
    Acerca el color mostrado de cada banda a su color `objetivo`, para que
    al cambiar la nota (o el modo de color) pase de uno a otro en unos
    TRANSICION_COLOR segundos en vez de saltar. Es un acercamiento
    exponencial: en cada cuadro recorre una parte de lo que falta, que
    depende de cuánto duró el cuadro, así se ve igual con cualquier FPS.
    Devuelve los colores como (R, G, B) enteros.
    """
    global _colores_mostrados, _momento_colores
    if _colores_mostrados is None:
        _colores_mostrados = [list(color) for color in objetivos]
    else:
        dt = max(0.0, ahora - _momento_colores)
        # En TRANSICION_COLOR segundos recorre el 95 % (e^-3 ≈ 0,05).
        parte = 1 - math.exp(-3 * dt / configuracion.TRANSICION_COLOR)
        for mostrado, objetivo in zip(_colores_mostrados, objetivos):
            for c in range(3):
                mostrado[c] += (objetivo[c] - mostrado[c]) * parte
    _momento_colores = ahora
    return [tuple(round(c) for c in color) for color in _colores_mostrados]


def espectro(superficie, datos, historial, ahora, zona=ESPECTRO):
    """
    Dibuja las 16 bandas en la forma elegida, las etiquetas de frecuencia,
    el medidor de nivel y las tiras laterales de golpe, dentro de `zona`
    (la tarjeta normal o, en pantalla completa, casi toda la ventana).
    Con cada golpe el fondo de la tarjeta se aclara un poco (pulso). Al
    cambiar de forma, la imagen vieja se desvanece encima de la nueva.
    """
    global _foto_fundido, _inicio_fundido, _forma_anterior, _foto_anterior
    # Si cambió la forma, la foto del cuadro anterior es la que se desvanece.
    if estado.forma != _forma_anterior and _foto_anterior is not None:
        _foto_fundido = _foto_anterior
        _inicio_fundido = ahora
    _forma_anterior = estado.forma

    if estado.forma == "espectrograma":
        detalle = "intensidad como color"
    else:
        detalle = f"{NOMBRES_FORMAS[estado.forma]} · color {NOMBRES_COLORES[estado.color].lower()}"
    golpe = intensidad_golpe(datos["momento_golpe"], ahora)
    fondo = colores.mezclar(colores.TARJETA, colores.ACTIVO, configuracion.OPACIDAD_PULSO_GOLPE * golpe)
    tarjeta(superficie, zona, "Espectro", detalle, fondo)
    medidor_nivel(superficie, zona, datos["nivel"], ahora)
    indicador_bpm(superficie, zona, datos["bpm"], golpe)

    # Área de dibujo: deja lugar al título arriba, a las etiquetas abajo y
    # a las tiras de golpe a los costados.
    area = pygame.Rect(zona.x + 34, zona.y + 44, zona.w - 68, zona.h - 44 - 34)
    tiras_golpe(superficie, zona, area, golpe)

    if estado.forma == "espectrograma":
        espectrograma(superficie, area, historial)
    else:
        objetivos = [colores.color_banda(i, estado.color, estado.color_fijo, datos["nota"])
                     for i in range(configuracion.CANTIDAD_BARRAS)]
        colores_bandas = acercar_colores(objetivos, ahora)
        # Barras y onda dejan abajo un lugar para su reflejo.
        con_reflejo = estado.forma in ("barras", "onda")
        alto_reflejo = int(area.h * configuracion.ALTO_REFLEJO) if con_reflejo else 0
        area_forma = pygame.Rect(area.x, area.y, area.w, area.h - alto_reflejo)
        if estado.forma == "onda":
            onda(superficie, area_forma, datos, colores_bandas)
        else:
            barras(superficie, area_forma, datos, colores_bandas, estado.forma == "centro")
        if con_reflejo:
            reflejo(superficie, area_forma, alto_reflejo)

        # Etiquetas: el límite inferior de cada banda, debajo de su barra.
        ancho = area.w / configuracion.CANTIDAD_BARRAS
        for i, (minimo, _) in enumerate(configuracion.BANDAS):
            centro = (area.x + (i + 0.5) * ancho, area.bottom + 10)
            texto(superficie, nombre_frecuencia(minimo), "mono_chica", colores.TEXTO_SECUNDARIO, centro, "midtop")

    fundido(superficie, zona, ahora)


# Fundido al cambiar de forma: foto del último cuadro dibujado, forma de
# ese cuadro y, durante el fundido, la foto que se desvanece y desde cuándo.
_foto_anterior = None
_forma_anterior = None
_foto_fundido = None
_inicio_fundido = 0


def fundido(superficie, zona, ahora):
    """
    Dibuja encima la foto de la forma anterior, cada vez más transparente,
    durante DURACION_FUNDIDO_FORMA segundos. Después guarda la foto de este
    cuadro, por si en el próximo cambia la forma. Solo se funde lo que está
    debajo del encabezado de la tarjeta. Si la zona cambió de tamaño
    (pantalla completa), la foto vieja no sirve y se descarta.
    """
    global _foto_fundido, _foto_anterior
    # Sin el encabezado de la tarjeta (título, medidor y detalle): esos
    # cambian enseguida y superpuestos se leen mal.
    debajo = pygame.Rect(zona.x + 1, zona.y + 40, zona.w - 2, zona.h - 41)
    if _foto_fundido is not None:
        transcurrido = ahora - _inicio_fundido
        if _foto_fundido.get_size() != debajo.size or transcurrido >= configuracion.DURACION_FUNDIDO_FORMA:
            _foto_fundido = None
        else:
            _foto_fundido.set_alpha(int(255 * (1 - transcurrido / configuracion.DURACION_FUNDIDO_FORMA)))
            superficie.blit(_foto_fundido, debajo.topleft)
    _foto_anterior = superficie.subsurface(debajo).copy()


def reflejo(superficie, area, alto):
    """
    Debajo del piso de `area`, la parte de abajo del dibujo dada vuelta y
    cada vez más transparente: de OPACIDAD_REFLEJO junto al piso a 0 a
    `alto` píxeles.
    """
    if alto <= 0:
        return
    origen = superficie.subsurface(pygame.Rect(area.x, area.bottom - alto, area.w, alto))
    imagen = pygame.Surface((area.w, alto), pygame.SRCALPHA)
    imagen.blit(pygame.transform.flip(origen, False, True), (0, 0))
    opacidad = configuracion.OPACIDAD_REFLEJO * (1 - numpy.arange(alto) / alto)
    alfa = pygame.surfarray.pixels_alpha(imagen)
    alfa[:] = (255 * opacidad[None, :]).astype(numpy.uint8)
    del alfa
    superficie.blit(imagen, (area.x, area.bottom))


def indicador_bpm(superficie, zona, bpm, golpe):
    """
    Tempo a la derecha del medidor de nivel: un punto que se enciende con
    cada golpe y "120 BPM". Sin tempo (pocos golpes o la música paró),
    "— BPM" en gris.
    """
    x = zona.x + 110 + ANCHO_MEDIDOR + 64
    y = zona.y + 22
    pygame.draw.circle(superficie, colores.mezclar(colores.BORDE, colores.ACTIVO, golpe), (x + 4, y), 4)
    numero = texto(superficie, "—" if bpm is None else str(bpm), "mono",
                   colores.TEXTO_SECUNDARIO if bpm is None else colores.TEXTO, (x + 14, y), "midleft")
    texto(superficie, "BPM", "mono_chica", colores.TEXTO_SECUNDARIO, (numero.right + 5, y + 1), "midleft")


# Nivel mostrado en el medidor (dB) y momento del último cuadro: sube enseguida
# y baja NIVEL_CAIDA_DB por segundo, como un vúmetro.
_nivel_mostrado = None
_momento_nivel = 0


def medidor_nivel(superficie, zona, nivel, ahora):
    """
    Medidor del volumen total, sin calibración, al lado del título de la
    tarjeta: de NIVEL_MINIMO_DB a 0 dBFS, verde, amarillo desde
    NIVEL_AMARILLO_DB y rojo desde NIVEL_ROJO_DB. Las zonas se ven apagadas
    y se encienden hasta el nivel actual.
    """
    global _nivel_mostrado, _momento_nivel
    minimo = configuracion.NIVEL_MINIMO_DB
    # float(): por si llega un tipo de numpy (pygame no acepta numpy.float32).
    nivel = minimo if nivel is None else max(minimo, min(0.0, float(nivel)))
    if _nivel_mostrado is None or nivel >= _nivel_mostrado:
        _nivel_mostrado = nivel
    else:
        bajada = configuracion.NIVEL_CAIDA_DB * max(0.0, ahora - _momento_nivel)
        _nivel_mostrado = max(nivel, _nivel_mostrado - bajada)
    _momento_nivel = ahora

    barra = pygame.Rect(zona.x + 110, zona.y + 19, ANCHO_MEDIDOR, 6)

    def a_x(db):
        return barra.x + (db - minimo) / -minimo * barra.w

    zonas = [(minimo, configuracion.NIVEL_AMARILLO_DB, colores.CONECTADO),
             (configuracion.NIVEL_AMARILLO_DB, configuracion.NIVEL_ROJO_DB, colores.PAUSA),
             (configuracion.NIVEL_ROJO_DB, 0.0, colores.ROJO)]
    for desde, hasta, color in zonas:
        x1, x2 = a_x(desde), a_x(hasta)
        pygame.draw.rect(superficie, colores.mezclar(colores.TARJETA, color, 0.22),
                         (x1, barra.y, x2 - x1 - 2, barra.h), border_radius=2)
        encendido = min(a_x(_nivel_mostrado), x2 - 2) - x1
        if encendido > 0:
            pygame.draw.rect(superficie, color, (x1, barra.y, encendido, barra.h), border_radius=2)
    texto(superficie, f"{_nivel_mostrado:.0f} dB".replace("-", "−"), "mono_chica", colores.TEXTO_SECUNDARIO,
          (barra.right + 8, barra.centery), "midleft")


def a_pixeles(altura, area):
    """Altura 0–32 → píxeles dentro del área."""
    return altura / configuracion.ALTURA_MAXIMA * area.h


def barras(superficie, area, datos, colores_bandas, desde_centro):
    """
    Forma "barras" (desde el piso) o "centro" (simétricas desde la línea
    media). Cada barra se aclara hacia el tope (degradar_barras) y tiene un
    brillo suave alrededor. Detrás, el destello de golpe con
    OPACIDAD_GOLPE; encima, la marca de pico si está activa.
    """
    ancho = area.w / configuracion.CANTIDAD_BARRAS
    separacion = max(4, ancho * 0.18)
    medio = area.h / 2
    # Tres capas: brillo (abajo de todo), destello y el cuerpo de las barras.
    brillo = capa(area.w, area.h, "brillo")
    destellos = capa(area.w, area.h)
    cuerpo = capa(area.w, area.h, "barras")
    alfa_destello = int(255 * configuracion.OPACIDAD_GOLPE)
    alfa_brillo = int(255 * configuracion.OPACIDAD_BRILLO_BARRA)
    margen = configuracion.ANCHO_BRILLO_BARRA
    # Alto de la barra que cae en cada columna de píxeles (0 en los huecos).
    altos = numpy.zeros(area.w)

    for i in range(configuracion.CANTIDAD_BARRAS):
        x = i * ancho + separacion / 2
        w = ancho - separacion
        color = colores_bandas[i]
        alto = a_pixeles(datos["alturas"][i], area)
        alto_destello = a_pixeles(datos["destello"][i], area)

        # Rectángulo de un alto dado, en coordenadas del área.
        def rect(alto_px):
            if desde_centro:
                return pygame.Rect(x, medio - alto_px / 2, w, alto_px)
            return pygame.Rect(x, area.h - alto_px, w, alto_px)

        # El destello se dibuja aparte y transparente: completa lo que le
        # falta a la barra y el nivel real se sigue viendo abajo.
        if alto_destello > alto:
            pygame.draw.rect(destellos, (*color, alfa_destello), rect(alto_destello), border_radius=3)
        r = rect(alto)
        if r.h > 0:
            pygame.draw.rect(cuerpo, color, r, border_radius=3)
            # Halo en tres anillos, de afuera hacia adentro y cada uno más opaco
            # (en una capa con transparencia, draw reemplaza los píxeles, no
            # los suma): fuerte pegado a la barra y se desvanece hacia afuera.
            for k in (3, 2, 1):
                m = margen * k / 3
                alfa = alfa_brillo * (4 - k) // 3
                pygame.draw.rect(brillo, (*color, alfa), r.inflate(2 * m, 2 * m), border_radius=round(3 + m))
            altos[r.x:r.right] = alto

    degradar_barras(cuerpo, altos, desde_centro)
    superficie.blit(brillo, area.topleft)
    superficie.blit(destellos, area.topleft)
    superficie.blit(cuerpo, area.topleft)

    # Un pico de menos de 1 no se marca: sería una raya suelta en el piso.
    if estado.pico:
        for i in range(configuracion.CANTIDAD_BARRAS):
            if datos["picos"][i] < 1:
                continue
            x = i * ancho + separacion / 2
            w = ancho - separacion
            pico = a_pixeles(datos["picos"][i], area)
            if desde_centro:
                marcas = [area.y + medio - pico / 2 - 3, area.y + medio + pico / 2]
            else:
                marcas = [area.bottom - pico - 3]
            for y in marcas:
                pygame.draw.rect(superficie, colores.BLANCO, (area.x + x, y, w, 3))

    if desde_centro:
        pygame.draw.line(superficie, colores.BORDE, (area.x, area.centery), (area.right, area.centery))


def degradar_barras(cuerpo, altos, desde_centro):
    """
    Oscurece cada barra hacia su base: el tope queda con su color y la base
    con BRILLO_BASE_BARRA de ese color. `altos` es el alto en píxeles de la
    barra de cada columna. Desde el centro, la base es la línea media y se
    aclara hacia las dos puntas.
    """
    ancho, alto = cuerpo.get_size()
    filas = numpy.arange(alto)[None, :]
    altos = numpy.maximum(altos, 1)[:, None]
    if desde_centro:
        # 0 en la línea media, 1 en las puntas.
        subida = numpy.abs(filas - alto / 2) / (altos / 2)
    else:
        # 0 en el piso, 1 en el tope de la barra.
        subida = (alto - filas) / altos
    base = configuracion.BRILLO_BASE_BARRA
    factor = base + (1 - base) * numpy.clip(subida, 0, 1)
    # pixels3d bloquea la superficie mientras exista: se suelta con del.
    rgb = pygame.surfarray.pixels3d(cuerpo)
    rgb[:] = (rgb * factor[:, :, None]).astype(numpy.uint8)
    del rgb


def suavizar(alturas, pasos):
    """
    Curva suave que pasa por el tope de cada banda, con `pasos` puntos por
    tramo (interpolación cúbica monótona de Fritsch–Carlson). Entre dos
    bandas nunca sale del rango de esas dos: no inventa picos ni baja del
    piso. Devuelve una lista de (posición, altura), con la posición medida
    en bandas (0.0 … n−1).
    """
    n = len(alturas)
    # Pendiente de cada tramo y pendiente de la curva en cada banda.
    d = [alturas[i + 1] - alturas[i] for i in range(n - 1)]
    m = [0.0] * n
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, n - 1):
        # Pico, valle o tramo plano: la curva se aplana ahí para no pasarse.
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            m[i] = 2 / (1 / d[i - 1] + 1 / d[i])   # media armónica

    curva = []
    for i in range(n - 1):
        for k in range(pasos):
            t = k / pasos
            h00 = 2 * t ** 3 - 3 * t ** 2 + 1
            h10 = t ** 3 - 2 * t ** 2 + t
            h01 = -2 * t ** 3 + 3 * t ** 2
            h11 = t ** 3 - t ** 2
            curva.append((i + t, h00 * alturas[i] + h10 * m[i] + h01 * alturas[i + 1] + h11 * m[i + 1]))
    curva.append((n - 1, alturas[-1]))
    return curva


def trazar(superficie, puntos, color, ancho):
    """
    Línea gruesa por una lista de puntos, con las uniones redondeadas (un
    círculo en cada una) para que no queden muescas. `color` es un color
    para toda la línea o una lista con uno por tramo; puede tener
    transparencia si la superficie la tiene.
    """
    radio = ancho / 2
    for j in range(len(puntos) - 1):
        c = color[j] if isinstance(color, list) else color
        pygame.draw.line(superficie, c, puntos[j], puntos[j + 1], ancho)
        pygame.draw.circle(superficie, c, puntos[j], radio)


def color_en(posicion, colores_bandas):
    """Color de la onda en una posición (en bandas, 0.0 … 15.0), mezclando las dos vecinas."""
    i = min(int(posicion), len(colores_bandas) - 2)
    return colores.mezclar(colores_bandas[i], colores_bandas[i + 1], posicion - i)


def degradar_relleno(relleno, puntos):
    """
    Cambia la transparencia del relleno de la onda: en cada columna va de
    OPACIDAD_RELLENO_ARRIBA justo debajo de la curva a
    OPACIDAD_RELLENO_ABAJO en el piso. Lo que está por encima de la curva
    sigue transparente.
    """
    ancho, alto = relleno.get_size()
    xs, ys = zip(*puntos)
    # Altura de la curva en cada columna de píxeles, y la fila de cada píxel.
    techo = numpy.interp(numpy.arange(ancho), xs, ys)[:, None]
    filas = numpy.arange(alto)[None, :]
    # 0 en la curva, 1 en el piso (el máximo evita dividir por 0 con la curva en el piso).
    bajada = numpy.clip((filas - techo) / numpy.maximum(alto - techo, 1), 0, 1)
    arriba = configuracion.OPACIDAD_RELLENO_ARRIBA
    abajo = configuracion.OPACIDAD_RELLENO_ABAJO
    opacidad = arriba + (abajo - arriba) * bajada
    # pixels_alpha bloquea la superficie mientras exista: se suelta con del.
    alfa = pygame.surfarray.pixels_alpha(relleno)
    alfa[:] = (alfa * opacidad).astype(numpy.uint8)
    del alfa


def onda(superficie, area, datos, colores_bandas):
    """
    Forma "onda": una curva suave que pasa por los topes de las bandas, con
    un brillo detrás y un relleno abajo que se desvanece de la curva al
    piso. El color va pasando de una banda a la siguiente. El golpe no se
    dibuja sobre la curva: solo se ven las tiras de los costados.
    """
    cantidad = configuracion.CANTIDAD_BARRAS
    ancho = area.w / cantidad

    curva = suavizar(datos["alturas"], configuracion.PASOS_ONDA)
    puntos = [((posicion + 0.5) * ancho, area.h - a_pixeles(altura, area)) for posicion, altura in curva]
    colores_curva = [color_en(posicion, colores_bandas) for posicion, _ in curva]

    # Relleno: un trapecio fino entre cada par de puntos, opaco del todo;
    # después se le aplica el degradado a la transparencia.
    relleno = capa(area.w, area.h)
    for j in range(len(puntos) - 1):
        (x1, y1), (x2, y2) = puntos[j], puntos[j + 1]
        color = colores.mezclar(colores_curva[j], colores_curva[j + 1], 0.5)
        pygame.draw.polygon(relleno, color, [(x1, y1), (x2, y2), (x2, area.h), (x1, area.h)])
    degradar_relleno(relleno, puntos)
    superficie.blit(relleno, area.topleft)

    # Brillo: la misma curva, más gruesa y transparente, detrás de la línea.
    # Va en otra capa para no pisar la transparencia del relleno.
    brillo = capa(area.w, area.h, "brillo")
    alfa_brillo = int(255 * configuracion.OPACIDAD_BRILLO_ONDA)
    trazar(brillo, puntos, [(*color, alfa_brillo) for color in colores_curva], configuracion.ANCHO_BRILLO_ONDA)
    superficie.blit(brillo, area.topleft)

    # Línea de 3 px encima del brillo.
    en_ventana = [(x + area.x, y + area.y) for x, y in puntos]
    trazar(superficie, en_ventana, colores_curva, 3)

    if estado.pico:
        pico_curva(superficie, area, datos["picos"], curva, ancho)


def pico_curva(superficie, area, picos, curva_onda, ancho):
    """
    Peak de la forma onda: una curva fina y clara con la misma forma suave
    que la onda, un poco por encima de los picos. Va con aalines (bordes
    suavizados) dos veces, una un píxel más abajo, para que tenga 2 px sin
    verse escalonada. Los tramos donde las dos bandas tienen pico menor a 1
    no se dibujan (serían una línea pegada al piso). `curva_onda` es la
    curva de la onda: entre dos bandas las dos curvas se interpolan por
    separado y podrían cruzarse, así que el peak nunca baja de la onda.
    """
    pasos = configuracion.PASOS_ONDA
    curva = suavizar(list(picos), pasos)
    puntos = [(area.x + (posicion + 0.5) * ancho,
               area.bottom - a_pixeles(max(altura, onda_altura), area) - configuracion.SEPARACION_PICO_ONDA)
              for (posicion, altura), (_, onda_altura) in zip(curva, curva_onda)]
    # aalines no usa transparencia: el blanco se mezcla con el fondo de la tarjeta.
    color = colores.mezclar(colores.TARJETA, colores.BLANCO, configuracion.OPACIDAD_PICO_ONDA)
    for i in range(len(picos) - 1):
        if picos[i] < 1 and picos[i + 1] < 1:
            continue
        tramo = puntos[i * pasos:(i + 1) * pasos + 1]
        pygame.draw.aalines(superficie, color, False, tramo)
        pygame.draw.aalines(superficie, color, False, [(x, y + 1) for x, y in tramo])


def espectrograma(superficie, area, historial):
    """
    Forma "espectrograma": tiempo en horizontal (lo más nuevo a la
    derecha), bandas en vertical (agudos arriba) e intensidad como color.
    Se arma una imagen de LARGO_HISTORIAL × 16 píxeles y se estira al área,
    menos una columna a la izquierda para las frecuencias. Sin peak y sin
    modo de color.
    """
    largo = configuracion.LARGO_HISTORIAL
    intensidades = numpy.zeros((largo, configuracion.CANTIDAD_BARRAS))
    if historial:
        # Si todavía hay menos de `largo` cuadros, quedan a la derecha.
        intensidades[largo - len(historial):] = numpy.array(historial)
    indices = (numpy.clip(intensidades / configuracion.ALTURA_MAXIMA, 0, 1) * 255).astype(int)
    # Forma (ancho, alto, 3); [:, ::-1] da vuelta las bandas para que los agudos queden arriba.
    imagen = colores.MAPA_ESPECTROGRAMA[indices][:, ::-1]
    chica = pygame.surfarray.make_surface(imagen)
    zona_imagen = area.inflate(-ANCHO_FRECUENCIAS, 0).move(ANCHO_FRECUENCIAS / 2, 0)
    superficie.blit(pygame.transform.scale(chica, zona_imagen.size), zona_imagen.topleft)

    # Frecuencias a la izquierda: el límite inferior de una banda de cada
    # dos, en el borde de abajo de su fila, y arriba el máximo de la última.
    fila = zona_imagen.h / configuracion.CANTIDAD_BARRAS
    x = zona_imagen.x - 6
    for i in range(0, configuracion.CANTIDAD_BARRAS, 2):
        minimo = configuracion.BANDAS[i][0]
        texto(superficie, nombre_frecuencia(minimo), "mono_chica", colores.TEXTO_SECUNDARIO,
              (x, zona_imagen.bottom - i * fila), "midright")
    maximo = configuracion.BANDAS[-1][1]
    texto(superficie, nombre_frecuencia(maximo), "mono_chica", colores.TEXTO_SECUNDARIO, (x, zona_imagen.y), "midright")

    segundos = configuracion.DURACION_HISTORIAL
    texto(superficie, f"−{segundos:g} s", "mono_chica", colores.TEXTO_SECUNDARIO, (zona_imagen.x, zona_imagen.bottom + 10))
    texto(superficie, "ahora", "mono_chica", colores.TEXTO_SECUNDARIO, (zona_imagen.right, zona_imagen.bottom + 10), "topright")


def intensidad_golpe(momento_golpe, ahora):
    """1 justo en el golpe, baja hasta 0 en DURACION_DESTELLO_GOLPE; 0 sin golpe."""
    if momento_golpe is None:
        return 0.0
    transcurrido = ahora - momento_golpe
    if 0 <= transcurrido < configuracion.DURACION_DESTELLO_GOLPE:
        return 1 - transcurrido / configuracion.DURACION_DESTELLO_GOLPE
    return 0.0


def tiras_golpe(superficie, zona, area, intensidad):
    """
    Tiras a los costados del espectro que se encienden con cada golpe y se
    apagan en DURACION_DESTELLO_GOLPE (`intensidad` va de 1 a 0). En la
    forma onda son lo único que muestra el golpe, junto con el pulso del
    fondo. Cada tira queda centrada en el margen entre el borde de la
    tarjeta y el área de dibujo.
    """
    color = colores.mezclar(colores.BORDE, colores.ACTIVO, intensidad)
    w = configuracion.ANCHO_TIRA_GOLPE
    for centro in ((zona.x + area.x) / 2, (area.right + zona.right) / 2):
        pygame.draw.rect(superficie, color, (round(centro - w / 2), area.y, w, area.h), border_radius=w // 2)


# --- Espejo de la OLED ------------------------------------------------------

def espejo_oled(superficie):
    """
    Réplica de la OLED a partir del último paquete armado para el Arduino
    (lo mismo que se manda por serie). En pausa no llegan paquetes nuevos,
    así que queda congelada con el último.
    """
    tarjeta(superficie, ESPEJO, "Espejo de la OLED", "128×32 · ×3")
    pantalla_rect = pygame.Rect(0, 0, ANCHO_OLED * ESCALA_OLED, ALTO_OLED * ESCALA_OLED)
    pantalla_rect.midtop = (ESPEJO.centerx, ESPEJO.y + 48)
    paquete = estado.ultimo_paquete

    oled = pygame.Surface((ANCHO_OLED, ALTO_OLED))
    oled.fill(colores.OLED_APAGADO)
    if paquete is None:
        texto(oled, "SIN DATOS", "oled", colores.OLED_ENCENDIDO, (ANCHO_OLED // 2, ALTO_OLED // 2), "center", suave=False)
    else:
        dibujar_oled(oled, paquete, estado.picos_enviados)

    marco = pantalla_rect.inflate(8, 8)
    en_pausa = paquete is not None and paquete[19] == 1
    pygame.draw.rect(superficie, colores.PAUSA if en_pausa else colores.BORDE, marco, width=2, border_radius=4)
    superficie.blit(pygame.transform.scale(oled, pantalla_rect.size), pantalla_rect)

    # Los bytes del paquete, para comparar con lo que recibe el Arduino.
    y = marco.bottom + 12
    if paquete is not None:
        texto(superficie, " ".join(str(b) for b in paquete), "mono_chica", colores.TEXTO_SECUNDARIO,
              (ESPEJO.centerx, y), "midtop")
    if en_pausa:
        texto(superficie, "En pausa: la OLED queda con el último cuadro", "chica", colores.PAUSA,
              (ESPEJO.centerx, y + 24), "midtop")
    elif not estado.arduino_conectado:
        texto(superficie, "Sin Arduino: así se vería la OLED", "chica", colores.TEXTO_SECUNDARIO,
              (ESPEJO.centerx, y + 24), "midtop")


def dibujar_oled(oled, paquete, picos):
    """
    Dibuja en una superficie de 128×32 lo que mostraría la OLED con este
    paquete: barras a la izquierda, fuente y nota a la derecha.

    Las barras salen desde el centro si el byte 21 (forma OLED) lo pide;
    si no, desde el piso (también con onda y espectrograma).
    """
    alturas = paquete[1:1 + configuracion.CANTIDAD_BARRAS]
    fuente, nota, _, pico, forma_oled = paquete[17], paquete[18], paquete[19], paquete[20], paquete[21]
    desde_centro = forma_oled == configuracion.FORMA_OLED_CENTRO
    for i, alto in enumerate(alturas):
        x = i * ANCHO_BARRA_OLED
        y = (ALTO_OLED - alto) // 2 if desde_centro else ALTO_OLED - alto
        if alto > 0:
            pygame.draw.rect(oled, colores.OLED_ENCENDIDO, (x, y, ANCHO_BARRA_OLED - 1, alto))
        if pico and picos is not None and picos[i] >= 1:
            p = int(picos[i])
            if desde_centro:
                filas = [(ALTO_OLED - p) // 2 - 1, (ALTO_OLED + p) // 2]
            else:
                filas = [ALTO_OLED - p - 1]
            for fila in filas:
                if 0 <= fila < ALTO_OLED:
                    pygame.draw.line(oled, colores.OLED_ENCENDIDO, (x, fila), (x + ANCHO_BARRA_OLED - 2, fila))
    nombre_fuente = "MIC" if fuente == configuracion.MODO_MIC else "LINE"
    texto(oled, nombre_fuente, "oled", colores.OLED_ENCENDIDO, (X_TEXTO_OLED + 15, 2), "midtop", suave=False)
    texto(oled, nombre_nota(nota).replace("—", "-"), "oled", colores.OLED_ENCENDIDO,
          (X_TEXTO_OLED + 15, 17), "midtop", suave=False)


# --- Nota / afinador ----------------------------------------------------------

def tarjeta_nota(superficie, datos):
    """Nota grande con la tira de 12 notas o, con el afinador activo, el afinador."""
    if estado.afinador:
        afinador(superficie, datos)
        return
    tarjeta(superficie, NOTA, "Nota", "fundamental")
    nota = datos["nota"]
    if nota == configuracion.SIN_NOTA:
        texto(superficie, "—", "grande", colores.TEXTO_SECUNDARIO, (NOTA.centerx, NOTA.y + 100), "center")
        texto(superficie, "sin nota", "chica", colores.TEXTO_SECUNDARIO, (NOTA.centerx, NOTA.y + 148), "center")
    else:
        texto(superficie, nombre_nota(nota), "grande", colores.COLORES_NOTAS[nota], (NOTA.centerx, NOTA.y + 104), "center")

    # Tira de 12 notas: la actual, resaltada con su color.
    ancho = (NOTA.w - 32) / 12
    for i in range(12):
        celda = pygame.Rect(NOTA.x + 16 + i * ancho, NOTA.bottom - 52, ancho - 3, 34)
        if i == nota:
            pygame.draw.rect(superficie, colores.COLORES_NOTAS[i], celda, border_radius=4)
            color_texto = colores.FONDO
        else:
            pygame.draw.rect(superficie, colores.BORDE, celda, width=1, border_radius=4)
            color_texto = colores.TEXTO_SECUNDARIO
        texto(superficie, configuracion.NOMBRES_NOTAS[i], "mono_chica", color_texto, celda.center, "center")


def afinador(superficie, datos):
    """Nota con octava, desvío en cents (verde dentro del margen), frecuencia y escala de −50 a +50."""
    tarjeta(superficie, NOTA, "Afinador", "−50 … +50 cents")
    frecuencia, cents, nota = datos["frecuencia"], datos["cents"], datos["nota"]
    escala = pygame.Rect(NOTA.x + 24, NOTA.bottom - 56, NOTA.w - 48, 10)

    # Zona afinada (verde) y marcas cada 25 cents.
    por_cent = escala.w / 100
    verde = pygame.Rect(0, 0, 2 * configuracion.MARGEN_AFINADO_CENTS * por_cent, escala.h)
    verde.center = escala.center
    pygame.draw.rect(superficie, colores.BORDE, escala, border_radius=5)
    pygame.draw.rect(superficie, colores.CONECTADO, verde, border_radius=3)
    for marca in (-50, -25, 0, 25, 50):
        x = escala.centerx + marca * por_cent
        pygame.draw.line(superficie, colores.TEXTO_SECUNDARIO, (x, escala.bottom + 2), (x, escala.bottom + 6))
        texto(superficie, f"{marca:+d}" if marca else "0", "mono_chica", colores.TEXTO_SECUNDARIO,
              (x, escala.bottom + 8), "midtop")

    if frecuencia is None or cents is None or nota == configuracion.SIN_NOTA:
        texto(superficie, "—", "grande", colores.TEXTO_SECUNDARIO, (NOTA.centerx, NOTA.y + 90), "center")
        texto(superficie, "sin señal clara", "chica", colores.TEXTO_SECUNDARIO, (NOTA.centerx, NOTA.y + 136), "center")
        return

    afinado = abs(cents) <= configuracion.MARGEN_AFINADO_CENTS
    color = colores.CONECTADO if afinado else colores.PAUSA
    texto(superficie, f"{nombre_nota(nota)}{octava(frecuencia)}", "grande", colores.TEXTO,
          (NOTA.centerx, NOTA.y + 86), "center")
    texto(superficie, f"{cents:+.0f} cents", "mediana", color, (NOTA.centerx - 8, NOTA.y + 134), "midright")
    texto(superficie, f"{frecuencia:.1f} Hz".replace(".", ","), "mono", colores.TEXTO_SECUNDARIO,
          (NOTA.centerx + 8, NOTA.y + 134), "midleft")
    x = escala.centerx + max(-50, min(50, cents)) * por_cent
    pygame.draw.rect(superficie, color, (x - 3, escala.y - 6, 6, escala.h + 12), border_radius=3)


# --- Panel de control ---------------------------------------------------------

# Animaciones del panel: clave → [valor actual, momento de la última vez].
_animaciones = {}


def animar(clave, objetivo, duracion=None):
    """
    Valor entre 0 y 1 que se acerca a `objetivo` (0 o 1) en unos `duracion`
    segundos (DURACION_BOTON si no se da), con el mismo acercamiento
    exponencial que los colores. `clave` identifica qué se anima (un botón
    y si es el mouse encima o el estar activo). La primera vez ya arranca
    en el objetivo, así al abrir la ventana no se anima nada.
    """
    duracion = duracion or configuracion.DURACION_BOTON
    ahora = time.monotonic()
    if clave not in _animaciones:
        _animaciones[clave] = [float(objetivo), ahora]
    animacion = _animaciones[clave]
    parte = 1 - math.exp(-3 * max(0.0, ahora - animacion[1]) / duracion)
    animacion[0] += (objetivo - animacion[0]) * parte
    animacion[1] = ahora
    return animacion[0]


def mezcla_texto(a, b, t):
    """Como colores.mezclar, pero en 16 escalones: cada color de texto se arma una vez y queda en el cache."""
    return colores.mezclar(a, b, round(t * 16) / 16)


def boton(superficie, rect, etiqueta, activo, accion, atajo=None, detalle=None, color_activo=colores.ACTIVO):
    """
    Dibuja un botón y lo anota en `botones`. Activo: borde y fondo del
    color `color_activo`. `atajo` es la tecla, en chiquito arriba a la
    derecha. Con el mouse encima se aclara, y al activarse o desactivarse
    pasa de un aspecto al otro en DURACION_BOTON segundos.
    """
    clave = (etiqueta, rect.x, rect.y)
    sobre = animar((clave, "sobre"), 1 if rect.collidepoint(pygame.mouse.get_pos()) else 0)
    prendido = animar((clave, "activo"), 1 if activo else 0)

    fondo_activo = colores.mezclar(colores.TARJETA, color_activo, 0.18)
    fondo = colores.mezclar(colores.FONDO, fondo_activo, prendido)
    fondo = colores.mezclar(fondo, colores.BORDE, 0.5 * sobre)
    borde = colores.mezclar(colores.BORDE, colores.TEXTO_SECUNDARIO, sobre)
    borde = colores.mezclar(borde, color_activo, prendido)
    color_texto = mezcla_texto(colores.TEXTO_SECUNDARIO, colores.TEXTO, max(prendido, 0.6 * sobre))
    pygame.draw.rect(superficie, fondo, rect, border_radius=8)
    pygame.draw.rect(superficie, borde, rect, width=1, border_radius=8)
    if detalle:
        texto(superficie, etiqueta, "negrita", color_texto, (rect.x + 12, rect.y + 9))
        texto(superficie, detalle, "chica", mezcla_texto(colores.TEXTO_SECUNDARIO, color_activo, prendido),
              (rect.x + 12, rect.bottom - 9), "bottomleft")
    else:
        texto(superficie, etiqueta, "normal", color_texto, rect.center, "center")
    if atajo:
        texto(superficie, atajo, "mono_chica", colores.TEXTO_SECUNDARIO, (rect.right - 8, rect.y + 6), "topright")
    botones.append((rect, accion))


def seccion(superficie, y, titulo, atajo=None):
    """Título de una sección del panel. Devuelve la y donde empieza su contenido."""
    texto(superficie, titulo.upper(), "chica", colores.TEXTO_SECUNDARIO, (PANEL.x + 16, y))
    if atajo:
        texto(superficie, atajo, "mono_chica", colores.TEXTO_SECUNDARIO, (PANEL.right - 16, y + 2), "topright")
    return y + 22


def grilla(x, y, columnas, ancho_total, alto, cantidad, separacion=8):
    """Rectángulos de una grilla de `columnas` columnas, de izquierda a derecha y de arriba abajo."""
    ancho = (ancho_total - separacion * (columnas - 1)) / columnas
    return [pygame.Rect(x + (i % columnas) * (ancho + separacion), y + (i // columnas) * (alto + separacion), ancho, alto)
            for i in range(cantidad)]


def panel(superficie):
    """Panel de control: fuente, caída, efectos, forma, color, muestras de color fijo y atajos."""
    tarjeta(superficie, PANEL)
    x = PANEL.x + 16
    ancho = PANEL.w - 32

    # Fuente: MIC o LINE. Al cambiarla, principal.py reabre el stream con
    # el dispositivo de configuracion.py que le corresponde.
    y = seccion(superficie, PANEL.y + 16, "Fuente", "I")
    fuentes_audio = [(configuracion.MODO_MIC, "MIC"), (configuracion.MODO_LINE, "LINE")]
    for (modo, etiqueta), rect in zip(fuentes_audio, grilla(x, y, 2, ancho, 32, 2)):
        boton(superficie, rect, etiqueta, estado.fuente == modo,
              lambda modo=modo: estado.cambiar("fuente", modo, "compu"))

    # Velocidad de caída: la que cambia el botón 1 del Arduino.
    y = seccion(superficie, y + 50, "Caída de las barras", "V")
    for i, rect in enumerate(grilla(x, y, 3, ancho, 32, 3)):
        boton(superficie, rect, estado.NOMBRES_VELOCIDADES[i].capitalize(), estado.velocidad == i,
              lambda i=i: estado.cambiar("velocidad", i, "compu"))

    y = seccion(superficie, y + 50, "Estado y efectos")
    efectos = [("pausa", "Pausa", "Espacio"), ("pico", "Peak", "P"), ("golpe", "Golpe", "G"), ("afinador", "Afinador", "A")]
    for (campo, etiqueta, atajo), rect in zip(efectos, grilla(x, y, 2, ancho, 56, 4)):
        activo = getattr(estado, campo)
        if campo == "pausa":
            detalle = "En pausa" if activo else "Enviando"
        else:
            detalle = "Activado" if activo else "Apagado"
        boton(superficie, rect, etiqueta, activo, lambda campo=campo: estado.alternar(campo, "compu"), atajo, detalle,
              colores.PAUSA if campo == "pausa" else colores.ACTIVO)

    y = seccion(superficie, y + 132, "Forma", "F")
    for forma, rect in zip(configuracion.FORMAS, grilla(x, y, 2, ancho, 44, 4)):
        boton(superficie, rect, NOMBRES_FORMAS[forma], estado.forma == forma,
              lambda forma=forma: estado.cambiar("forma", forma, "compu"))

    y = seccion(superficie, y + 112, "Color", "C")
    espectrograma = estado.forma == "espectrograma"
    for modo, rect in zip(configuracion.MODOS_COLOR, grilla(x, y, 3, ancho, 36, 3)):
        boton(superficie, rect, NOMBRES_COLORES[modo], estado.color == modo,
              lambda modo=modo: estado.cambiar("color", modo, "compu"))
    if espectrograma:
        texto(superficie, "En espectrograma el color es la intensidad", "chica", colores.TEXTO_SECUNDARIO, (x, y + 42))

    y = seccion(superficie, y + 66, "Color fijo")
    radio = 15
    paso = ancho / len(configuracion.COLORES_FIJOS)
    for i, (_, rgb) in enumerate(configuracion.COLORES_FIJOS):
        centro = (x + paso * (i + 0.5), y + radio + 2)
        rect = pygame.Rect(0, 0, 2 * radio + 8, 2 * radio + 8)
        rect.center = centro
        # Con el mouse encima crece un poco; el aro de la elegida aparece y se va animado.
        sobre = animar(("color_fijo", i, "sobre"), 1 if rect.collidepoint(pygame.mouse.get_pos()) else 0)
        elegido = animar(("color_fijo", i, "activo"), 1 if estado.color_fijo == i else 0)
        pygame.draw.circle(superficie, rgb, centro, radio + 2 * sobre)
        if elegido > 0.05:
            aro = colores.mezclar(colores.TARJETA, colores.TEXTO, elegido)
            pygame.draw.circle(superficie, aro, centro, radio + 2 + 2 * elegido, width=2)
        botones.append((rect, lambda i=i: estado.cambiar("color_fijo", i, "compu")))

    y = seccion(superficie, y + 54, "Atajos de teclado")
    for linea in ["Espacio pausa · P peak · G golpe", "A afinador · F forma · C color", "V caída · R recalibrar · I fuente",
                  "Z pantalla completa"]:
        texto(superficie, linea, "chica", colores.TEXTO_SECUNDARIO, (x, y))
        y += 20


def aviso_pantalla_completa(superficie):
    """En pantalla completa: recordatorio de cómo salir, abajo a la derecha."""
    texto(superficie, "Z o Esc para salir", "mono_chica", colores.TEXTO_SECUNDARIO,
          (ESPECTRO_COMPLETO.right - 4, ESPECTRO_COMPLETO.bottom + 7), "topright")


def pie(superficie, contenido):
    """Línea de estado abajo a la izquierda (FPS, datos simulados…)."""
    texto(superficie, contenido, "mono_chica", colores.TEXTO_SECUNDARIO, (24, 790))


if __name__ == "__main__":
    # Pruebas de suavizar(alturas, pasos): la curva de la forma "onda".
    errores = 0

    def revisar(bien, nombre, obtenido, esperado):
        """Imprime una línea OK / ERROR y cuenta los errores."""
        global errores
        errores += 0 if bien else 1
        print(f"{'OK   ' if bien else 'ERROR'} {nombre:<40} → {obtenido}   (esperado {esperado})")

    def caso(nombre, prueba):
        """Corre una prueba; si explota, cuenta como ERROR y sigue con las demás."""
        global errores
        try:
            prueba()
        except Exception as e:
            errores += 1
            print(f"ERROR {nombre:<40} → {type(e).__name__}: {e}")

    ALTURAS = [20, 27, 14, 22, 9, 17, 6, 12, 15, 4, 10, 3, 8, 2, 5, 1]
    PASOS = 12

    def largo():
        curva = suavizar(ALTURAS, PASOS)
        esperado = (len(ALTURAS) - 1) * PASOS + 1
        revisar(len(curva) == esperado, "cantidad de puntos", len(curva), esperado)

    def pasa_por_bandas():
        curva = suavizar(ALTURAS, PASOS)
        malos = [i for i in range(len(ALTURAS))
                 if abs(curva[i * PASOS][0] - i) > 1e-9 or abs(curva[i * PASOS][1] - ALTURAS[i]) > 1e-9]
        revisar(not malos, "pasa por el tope de cada banda", f"bandas mal: {malos}", "ninguna")

    def no_se_pasa():
        # Entre dos bandas la curva no puede salir del rango de esas dos:
        # nada por debajo del piso ni picos falsos más altos que la banda.
        curva = suavizar(ALTURAS, PASOS)
        fuera = []
        for i in range(len(ALTURAS) - 1):
            bajo, alto = sorted((ALTURAS[i], ALTURAS[i + 1]))
            tramo = curva[i * PASOS:(i + 1) * PASOS + 1]
            if any(a < bajo - 1e-9 or a > alto + 1e-9 for _, a in tramo):
                fuera.append(i)
        revisar(not fuera, "no inventa picos ni valles", f"tramos fuera: {fuera}", "ninguno")

    def posiciones_crecen():
        curva = suavizar(ALTURAS, PASOS)
        bien = all(curva[j][0] < curva[j + 1][0] for j in range(len(curva) - 1))
        revisar(bien, "posiciones en orden de 0 a 15", (curva[0][0], curva[-1][0]), (0, 15))

    def plano():
        curva = suavizar([10] * 16, PASOS)
        bien = all(abs(a - 10) < 1e-9 for _, a in curva)
        revisar(bien, "todo igual → línea recta", "recta" if bien else "se curva", "recta")

    def silencio():
        curva = suavizar([0] * 16, PASOS)
        bien = all(abs(a) < 1e-9 for _, a in curva)
        revisar(bien, "silencio → todo en el piso", "piso" if bien else "se despega", "piso")

    def rampa():
        # Subida pareja: la curva tiene que ser la misma recta, sin ondular.
        alturas = list(range(16))
        curva = suavizar(alturas, PASOS)
        bien = all(abs(a - p) < 1e-9 for p, a in curva)
        revisar(bien, "rampa pareja → recta", "recta" if bien else "ondula", "recta")

    def un_paso():
        curva = suavizar(ALTURAS, 1)
        revisar([a for _, a in curva] == ALTURAS, "pasos = 1 → los mismos puntos", len(curva), 16)

    def colores_primero():
        # La primera vez no hay de dónde venir: devuelve el objetivo tal cual.
        global _colores_mostrados
        _colores_mostrados = None
        obtenido = acercar_colores([(255, 0, 0)], 10.0)
        revisar(obtenido == [(255, 0, 0)], "color: primer cuadro = objetivo", obtenido, [(255, 0, 0)])

    def colores_transicion():
        # De negro a blanco: a los TRANSICION_COLOR s tiene que ir por el 95 %.
        global _colores_mostrados
        _colores_mostrados = None
        acercar_colores([(0, 0, 0)], 0.0)
        t = 0.0
        while t < configuracion.TRANSICION_COLOR - 1e-9:
            t += 1 / 30
            obtenido = acercar_colores([(255, 255, 255)], t)[0][0]
        revisar(235 <= obtenido <= 250, f"color: a los {configuracion.TRANSICION_COLOR:g} s va por el 95 %",
                obtenido, "≈ 242")

    def colores_fps():
        # Mismo tiempo con 30 o con 60 cuadros por segundo: casi el mismo color.
        global _colores_mostrados
        resultados = []
        for fps in (30, 60):
            _colores_mostrados = None
            acercar_colores([(0, 0, 0)], 0.0)
            for k in range(1, fps // 10 + 1):
                valor = acercar_colores([(200, 200, 200)], k / fps)[0][0]
            resultados.append(valor)
        revisar(abs(resultados[0] - resultados[1]) <= 1, "color: igual con 30 y 60 FPS", resultados, "iguales")

    def colores_llega():
        global _colores_mostrados
        _colores_mostrados = None
        acercar_colores([(10, 20, 30)], 0.0)
        for k in range(1, 61):
            obtenido = acercar_colores([(200, 100, 50)], k / 30)
        revisar(obtenido == [(200, 100, 50)], "color: a los 2 s llegó", obtenido, [(200, 100, 50)])

    def golpe_intensidad():
        d = configuracion.DURACION_DESTELLO_GOLPE
        obtenido = [round(intensidad_golpe(m, 10.0), 2) for m in (None, 10.0, 10.0 - d / 2, 10.0 - d, 11.0)]
        revisar(obtenido == [0, 1, 0.5, 0, 0], "golpe: intensidad 1 → 0 y nada sin golpe", obtenido, [0, 1, 0.5, 0, 0])

    def animar_primera():
        _animaciones.clear()
        obtenido = animar("prueba", 1)
        revisar(obtenido == 1, "animar: la primera vez ya está", obtenido, 1)

    def animar_transicion():
        # Se fuerza el momento anterior para no depender del reloj.
        _animaciones.clear()
        animar("prueba", 0)
        _animaciones["prueba"][1] -= configuracion.DURACION_BOTON
        obtenido = round(animar("prueba", 1), 2)
        revisar(0.93 <= obtenido <= 0.97, "animar: en DURACION_BOTON va por el 95 %", obtenido, "≈ 0,95")

    def degradado_barras():
        # Una barra de 10 px blanca desde el piso: tope blanco, base con BRILLO_BASE_BARRA.
        pygame.init()
        cuerpo = pygame.Surface((4, 20), pygame.SRCALPHA)
        cuerpo.fill((0, 0, 0, 0))
        pygame.draw.rect(cuerpo, (200, 200, 200), (0, 10, 4, 10))
        degradar_barras(cuerpo, numpy.full(4, 10.0), False)
        tope = cuerpo.get_at((1, 10))[0]
        base = cuerpo.get_at((1, 19))[0]
        esperado_base = 200 * (configuracion.BRILLO_BASE_BARRA + (1 - configuracion.BRILLO_BASE_BARRA) * 0.1)
        bien = abs(tope - 200) <= 1 and abs(base - esperado_base) <= 2 and tope > base
        revisar(bien, "barras: se oscurecen hacia la base", (tope, base), (200, round(esperado_base)))

    def degradado_centro():
        pygame.init()
        cuerpo = pygame.Surface((2, 20), pygame.SRCALPHA)
        pygame.draw.rect(cuerpo, (200, 200, 200), (0, 0, 2, 20))
        degradar_barras(cuerpo, numpy.full(2, 20.0), True)
        punta, medio, otra = cuerpo.get_at((0, 0))[0], cuerpo.get_at((0, 10))[0], cuerpo.get_at((0, 19))[0]
        bien = medio < punta and medio < otra and abs(punta - otra) <= 22
        revisar(bien, "centro: más oscuro en la línea media", (punta, medio, otra), "puntas > medio")

    for nombre, prueba in [("golpe intensidad", golpe_intensidad), ("animar primera", animar_primera),
                           ("animar transición", animar_transicion), ("degradado barras", degradado_barras),
                           ("degradado centro", degradado_centro),
                           ("color primer cuadro", colores_primero), ("color transición", colores_transicion),
                           ("color con distintos FPS", colores_fps), ("color llega", colores_llega),
                           ("cantidad de puntos", largo), ("pasa por las bandas", pasa_por_bandas),
                           ("no inventa picos", no_se_pasa), ("posiciones en orden", posiciones_crecen),
                           ("todo igual", plano), ("silencio", silencio), ("rampa", rampa),
                           ("pasos = 1", un_paso)]:
        caso(nombre, prueba)

    print("Todo bien" if errores == 0 else f"{errores} errores")
