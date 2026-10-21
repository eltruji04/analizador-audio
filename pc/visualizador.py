"""
visualizador.py — Ventana de la compu que muestra lo mismo que la OLED.

Dibuja las 16 barras a la izquierda y, en un panel a la derecha, la
fuente (MIC/LINE), la nota, la velocidad de caída y si el Arduino está en
pausa. Usa pygame (paquete pygame-ce).

En macOS la ventana solo se puede manejar desde el hilo principal: por
eso dibujar() se llama desde el bucle principal, nunca desde el callback
de audio.
"""

import pygame
import numpy
import time
import configuracion


# Tamaño de la ventana, en píxeles. Las barras ocupan los primeros
# ANCHO_BARRAS; el resto es el panel de la derecha.
ANCHO = 960
ALTO = 360
ANCHO_BARRAS = 720
COLOR_FONDO = (0, 0, 0)
COLOR_BARRA = (255, 192, 203)
COLOR_PANEL = (50, 50, 50)
COLOR_TEXTO = (255, 255, 255)
# Textos que se muestran según el número: la nota (12 = sin nota) y la
# velocidad de caída (índice en configuracion.VELOCIDADES_CAIDA).
NOMBRES_NOTAS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B", "-"]
NOMBRES_VELOCIDADES = ["lento", "normal", "rápido"]

# Ventana y fuente de letra. Las crea iniciar(); empiezan vacías.
pantalla = None
fuente = None


def iniciar():
    """Abre la ventana y prepara la fuente de letra. Se llama una sola vez."""
    # Sin `global`, las asignaciones crearían variables locales y
    # dibujar() seguiría viendo pantalla y fuente en None.
    global pantalla, fuente
    pygame.init()
    pantalla = pygame.display.set_mode((ANCHO, ALTO))
    pygame.display.set_caption("Visualizador de Audio")
    # None = la fuente que trae pygame; 32 = tamaño en píxeles.
    fuente = pygame.font.Font(None, 32)


def dibujar(alturas, modo, nota, velocidad, pausa):
    """
    Dibuja un cuadro: las barras con `alturas` (de 0 a ALTURA_MAXIMA) y
    el panel con la fuente, la nota, la velocidad y la pausa.

    Devuelve False si se cerró la ventana (con la ✕), True si no.
    Los eventos se leen en cada cuadro: si no, macOS marca la ventana
    como "no responde".
    """
    for evento in pygame.event.get():
        if evento.type == pygame.QUIT:
            return False

    # Se borra el cuadro anterior: fondo negro y panel gris a la derecha.
    pantalla.fill(COLOR_FONDO)
    pygame.draw.rect(pantalla, COLOR_PANEL, (ANCHO_BARRAS, 0, ANCHO - ANCHO_BARRAS, ALTO))

    # Barras: como en la OLED, y crece hacia abajo, así que cada barra
    # empieza en ALTO − alto_px y llega hasta el piso de la ventana.
    ancho_barra = ANCHO_BARRAS / configuracion.CANTIDAD_BARRAS
    for i in range(len(alturas)):
        alto_px = alturas[i] * ALTO / configuracion.ALTURA_MAXIMA
        x = i * ancho_barra
        y = ALTO - alto_px
        # 2 px menos de ancho para que quede una separación entre barras.
        pygame.draw.rect(pantalla, COLOR_BARRA, (x, y, ancho_barra - 2, alto_px))

    # Panel derecho: cada texto alineado a la derecha, uno debajo del otro.
    texto = fuente.render("MIC" if modo == configuracion.MODO_MIC else "LINE", True, COLOR_TEXTO)
    pantalla.blit(texto, (ANCHO - texto.get_width() - 10, 10))
    texto = fuente.render(NOMBRES_NOTAS[nota], True, COLOR_TEXTO)
    pantalla.blit(texto, (ANCHO - texto.get_width() - 10, 40))
    texto = fuente.render(NOMBRES_VELOCIDADES[velocidad], True, COLOR_TEXTO)
    pantalla.blit(texto, (ANCHO - texto.get_width() - 10, 70))
    if pausa:
        texto = fuente.render("Arduino en pausa", True, COLOR_TEXTO)
        pantalla.blit(texto, (ANCHO - texto.get_width() - 10, 100))

    # Hasta acá todo se dibujó en memoria: flip() lo muestra en la ventana.
    pygame.display.flip()
    return True

def cerrar():
    """Cierra la ventana y libera pygame."""
    pygame.quit()


# Prueba sin audio: solo se ejecuta con `python pc/visualizador.py`.
# Barras inventadas que se mueven como ondas y, cada 2 segundos, cambian
# la fuente, la nota, la velocidad y la pausa, para ver todos los textos
# del panel. Dura 12 segundos o hasta que se cierra la ventana.
if __name__ == "__main__":
    iniciar()
    print("Prueba del visualizador: se cierra sola en 12 s o con la ✕ de la ventana")
    inicio = time.monotonic()
    while time.monotonic() - inicio < 12:
        t = time.monotonic() - inicio
        # Una onda que recorre las barras: cada barra va un poco atrasada
        # respecto de la anterior. Queda entre 1 y 31 (nunca vacía ni llena).
        posiciones = numpy.arange(configuracion.CANTIDAD_BARRAS)
        alturas = 16 + 15 * numpy.sin(3 * t - posiciones * 0.5)

        # Cada 2 s cambia el "paso" y, con él, lo que muestra el panel.
        paso = int(t // 2)
        modo = paso % 2                               # MIC, LINE, MIC, …
        nota = paso % len(NOMBRES_NOTAS)              # C, C#, D, … ("-" al final)
        velocidad = paso % len(configuracion.VELOCIDADES_CAIDA)  # 0, 1, 2, 0, …
        pausa = 1 if paso % 4 == 3 else 0             # pausa de 2 s cada 8 s

        if not dibujar(alturas, modo, nota, velocidad, pausa):
            print("Ventana cerrada")
            break
        time.sleep(configuracion.INTERVALO_DIBUJO)
    cerrar()

