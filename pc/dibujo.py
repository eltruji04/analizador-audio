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
import numpy
import pygame
import configuracion
import colores
import estado

ESPECTRO = pygame.Rect(24, 88, 892, 426)
ESPEJO = pygame.Rect(24, 534, 572, 236)
NOTA = pygame.Rect(616, 534, 300, 236)
PANEL = pygame.Rect(936, 88, 320, 728)

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


def capa(ancho, alto):
    """Superficie transparente de ese tamaño, vacía, para dibujar con opacidad."""
    clave = (ancho, alto)
    if clave not in _capas:
        _capas[clave] = pygame.Surface(clave, pygame.SRCALPHA)
    _capas[clave].fill((0, 0, 0, 0))
    return _capas[clave]


def tarjeta(superficie, rect, titulo=None, detalle=None):
    """Fondo de una zona: rectángulo redondeado con borde y título opcional."""
    pygame.draw.rect(superficie, colores.TARJETA, rect, border_radius=10)
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

def espectro(superficie, datos, historial, ahora):
    """
    Dibuja las 16 bandas en la forma elegida, las etiquetas de frecuencia
    y las tiras laterales de golpe.
    """
    if estado.forma == "espectrograma":
        detalle = "intensidad como color"
    else:
        detalle = f"{NOMBRES_FORMAS[estado.forma]} · color {NOMBRES_COLORES[estado.color].lower()}"
    tarjeta(superficie, ESPECTRO, "Espectro", detalle)

    # Área de dibujo: deja lugar al título arriba, a las etiquetas abajo y
    # a las tiras de golpe a los costados.
    area = pygame.Rect(ESPECTRO.x + 34, ESPECTRO.y + 44, ESPECTRO.w - 68, ESPECTRO.h - 44 - 34)
    tiras_golpe(superficie, area, datos["momento_golpe"], ahora)

    if estado.forma == "espectrograma":
        espectrograma(superficie, area, historial)
        return

    colores_bandas = [colores.color_banda(i, estado.color, estado.color_fijo, datos["nota"])
                      for i in range(configuracion.CANTIDAD_BARRAS)]
    if estado.forma == "onda":
        onda(superficie, area, datos, colores_bandas)
    else:
        barras(superficie, area, datos, colores_bandas, estado.forma == "centro")

    # Etiquetas: el límite inferior de cada banda, debajo de su barra.
    ancho = area.w / configuracion.CANTIDAD_BARRAS
    for i, (minimo, _) in enumerate(configuracion.BANDAS):
        centro = (area.x + (i + 0.5) * ancho, area.bottom + 10)
        texto(superficie, nombre_frecuencia(minimo), "mono_chica", colores.TEXTO_SECUNDARIO, centro, "midtop")


def a_pixeles(altura, area):
    """Altura 0–32 → píxeles dentro del área."""
    return altura / configuracion.ALTURA_MAXIMA * area.h


def barras(superficie, area, datos, colores_bandas, desde_centro):
    """
    Forma "barras" (desde el piso) o "centro" (simétricas desde la línea
    media). Detrás de cada barra, el destello de golpe con OPACIDAD_GOLPE;
    encima, la marca de pico si está activa.
    """
    ancho = area.w / configuracion.CANTIDAD_BARRAS
    separacion = max(4, ancho * 0.18)
    transparente = capa(area.w, area.h)
    alfa = int(255 * configuracion.OPACIDAD_GOLPE)
    medio = area.h / 2

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
            pygame.draw.rect(transparente, (*color, alfa), rect(alto_destello), border_radius=3)
        r = rect(alto).move(area.x, area.y)
        if r.h > 0:
            pygame.draw.rect(superficie, color, r, border_radius=3)

        # Un pico de menos de 1 no se marca: sería una raya suelta en el piso.
        if estado.pico and datos["picos"][i] >= 1:
            pico = a_pixeles(datos["picos"][i], area)
            if desde_centro:
                marcas = [area.y + medio - pico / 2 - 3, area.y + medio + pico / 2]
            else:
                marcas = [area.bottom - pico - 3]
            for y in marcas:
                pygame.draw.rect(superficie, colores.BLANCO, (area.x + x, y, w, 3))

    superficie.blit(transparente, area.topleft)
    if desde_centro:
        pygame.draw.line(superficie, colores.BORDE, (area.x, area.centery), (area.right, area.centery))


def onda(superficie, area, datos, colores_bandas):
    """
    Forma "onda": una línea que une los topes de las bandas, con relleno
    suave abajo y un punto de color por banda. El golpe se ve como
    columnas transparentes detrás de la línea.
    """
    ancho = area.w / configuracion.CANTIDAD_BARRAS
    transparente = capa(area.w, area.h)
    alfa = int(255 * configuracion.OPACIDAD_GOLPE)
    puntos = []
    for i in range(configuracion.CANTIDAD_BARRAS):
        x = (i + 0.5) * ancho
        puntos.append((x, area.h - a_pixeles(datos["alturas"][i], area)))
        alto_destello = a_pixeles(datos["destello"][i], area)
        if alto_destello > 0:
            pygame.draw.rect(transparente, (*colores_bandas[i], alfa),
                             (i * ancho + 3, area.h - alto_destello, ancho - 6, alto_destello), border_radius=3)

    # Relleno: un trapecio entre cada par de puntos, con el color de los dos mezclado.
    for i in range(len(puntos) - 1):
        (x1, y1), (x2, y2) = puntos[i], puntos[i + 1]
        color = colores.mezclar(colores_bandas[i], colores_bandas[i + 1], 0.5)
        pygame.draw.polygon(transparente, (*color, 50), [(x1, y1), (x2, y2), (x2, area.h), (x1, area.h)])
    superficie.blit(transparente, area.topleft)

    en_ventana = [(x + area.x, y + area.y) for x, y in puntos]
    for i in range(len(en_ventana) - 1):
        pygame.draw.line(superficie, colores_bandas[i], en_ventana[i], en_ventana[i + 1], 3)
    for i, punto in enumerate(en_ventana):
        pygame.draw.circle(superficie, colores_bandas[i], punto, 5)

    if estado.pico:
        for i in range(configuracion.CANTIDAD_BARRAS):
            if datos["picos"][i] < 1:
                continue
            x = area.x + (i + 0.5) * ancho
            y = area.bottom - a_pixeles(datos["picos"][i], area) - 8
            pygame.draw.line(superficie, colores.BLANCO, (x - ancho * 0.25, y), (x + ancho * 0.25, y), 2)


def espectrograma(superficie, area, historial):
    """
    Forma "espectrograma": tiempo en horizontal (lo más nuevo a la
    derecha), bandas en vertical (agudos arriba) e intensidad como color.
    Se arma una imagen de LARGO_HISTORIAL × 16 píxeles y se estira al área.
    Sin peak y sin modo de color.
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
    superficie.blit(pygame.transform.scale(chica, area.size), area.topleft)

    segundos = configuracion.DURACION_HISTORIAL
    texto(superficie, f"−{segundos:g} s", "mono_chica", colores.TEXTO_SECUNDARIO, (area.x, area.bottom + 10))
    texto(superficie, "ahora", "mono_chica", colores.TEXTO_SECUNDARIO, (area.right, area.bottom + 10), "topright")
    texto(superficie, "agudos", "mono_chica", colores.TEXTO_SECUNDARIO, (area.x + 6, area.y + 4))
    texto(superficie, "graves", "mono_chica", colores.TEXTO_SECUNDARIO, (area.x + 6, area.bottom - 4), "bottomleft")


def tiras_golpe(superficie, area, momento_golpe, ahora):
    """
    Tiras a los costados del espectro que se encienden con cada golpe y se
    apagan en DURACION_DESTELLO_GOLPE. (Decisión abierta: pueden sobrar,
    porque el golpe ya se ve en las bandas 1, 2, 15 y 16.)
    """
    intensidad = 0
    if momento_golpe is not None:
        transcurrido = ahora - momento_golpe
        if 0 <= transcurrido < configuracion.DURACION_DESTELLO_GOLPE:
            intensidad = 1 - transcurrido / configuracion.DURACION_DESTELLO_GOLPE
    color = colores.mezclar(colores.BORDE, colores.ACTIVO, intensidad)
    for x in (ESPECTRO.x + 14, ESPECTRO.right - 20):
        pygame.draw.rect(superficie, color, (x, area.y, 6, area.h), border_radius=3)


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

    La forma "centro" no va en el paquete: se dibuja centrada según el
    estado de la compu (falta decidir con Lucía si la OLED también lo hace).
    """
    alturas = paquete[1:1 + configuracion.CANTIDAD_BARRAS]
    fuente, nota, _, pico = paquete[17], paquete[18], paquete[19], paquete[20]
    desde_centro = estado.forma == "centro"
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

def boton(superficie, rect, etiqueta, activo, accion, atajo=None, detalle=None, color_activo=colores.ACTIVO):
    """
    Dibuja un botón y lo anota en `botones`. Activo: borde y fondo del
    color `color_activo`. `atajo` es la tecla, en chiquito arriba a la derecha.
    """
    sobre = rect.collidepoint(pygame.mouse.get_pos())
    if activo:
        fondo = colores.mezclar(colores.TARJETA, color_activo, 0.18)
        borde = color_activo
        color_texto = colores.TEXTO
    else:
        fondo = colores.FONDO
        borde = colores.TEXTO_SECUNDARIO if sobre else colores.BORDE
        color_texto = colores.TEXTO_SECUNDARIO
    pygame.draw.rect(superficie, fondo, rect, border_radius=8)
    pygame.draw.rect(superficie, borde, rect, width=1, border_radius=8)
    if detalle:
        texto(superficie, etiqueta, "negrita", color_texto, (rect.x + 12, rect.y + 9))
        texto(superficie, detalle, "chica", color_activo if activo else colores.TEXTO_SECUNDARIO,
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

    # Fuente: solo se muestra, se elige en configuracion.py.
    y = seccion(superficie, PANEL.y + 16, "Fuente")
    fuente = "MIC" if estado.fuente == configuracion.MODO_MIC else "LINE"
    texto(superficie, fuente, "negrita", colores.TEXTO, (x, y))
    texto(superficie, "fija (configuracion.py)", "chica", colores.TEXTO_SECUNDARIO, (PANEL.right - 16, y + 2), "topright")

    # Velocidad de caída: la que cambia el botón 1 del Arduino.
    y = seccion(superficie, y + 34, "Caída de las barras", "V")
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
        pygame.draw.circle(superficie, rgb, centro, radio)
        if estado.color_fijo == i:
            pygame.draw.circle(superficie, colores.TEXTO, centro, radio + 4, width=2)
        botones.append((rect, lambda i=i: estado.cambiar("color_fijo", i, "compu")))

    y = seccion(superficie, y + 54, "Atajos de teclado")
    for linea in ["Espacio pausa · P peak · G golpe", "A afinador · F forma · C color", "V velocidad de caída"]:
        texto(superficie, linea, "chica", colores.TEXTO_SECUNDARIO, (x, y))
        y += 20


def pie(superficie, contenido):
    """Línea de estado abajo a la izquierda (FPS, datos simulados…)."""
    texto(superficie, contenido, "mono_chica", colores.TEXTO_SECUNDARIO, (24, 790))
