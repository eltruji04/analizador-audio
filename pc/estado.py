"""
estado.py — Estado compartido del analizador (velocidad, pausa, pico, golpe).

La compu es la única dueña del estado: el Arduino (con sus botones) y
Blynk solo piden cambios llamando a aplicar_accion(). La compu cambia el
valor y lo refleja en el paquete al Arduino, en el visualizador y en Blynk.

Importante: usar siempre `import estado` y leer `estado.pausa`, nunca
`from estado import pausa`. Esa forma copia el valor en el momento de
importar y después no ve los cambios que hacen los botones.
"""

import configuracion

velocidad = configuracion.VELOCIDAD_INICIAL
# 1 = no se envía al Arduino (la compu sigue capturando y mostrando).
pausa = 0
# 1 = el Arduino dibuja la marca de pico.
pico = 0
# 1 = se llenan las barras de BARRAS_GOLPE cuando se detecta un golpe.
golpe = 0

def aplicar_accion(codigo):
    """
    Aplica la acción del botón con código `codigo` (1 a 4, ver los
    BOTON_* de configuracion). La usan los botones del Arduino y Blynk.

    El código dice qué botón se apretó, no el valor nuevo: la velocidad
    pasa a la siguiente (y vuelve a 0 después de la última) y pausa, pico
    y golpe alternan entre 0 y 1. Un código desconocido se muestra y no
    cambia nada.
    """
    # Sin `global`, Python crearía variables locales y el estado no cambiaría.
    global velocidad, pausa, pico, golpe
    if codigo == configuracion.BOTON_CAIDA:
        velocidad = (velocidad + 1) % len(configuracion.VELOCIDADES_CAIDA)
    elif codigo == configuracion.BOTON_PAUSA:
        pausa = 1 - pausa
    elif codigo == configuracion.BOTON_PICO:
        pico = 1 - pico
    elif codigo == configuracion.BOTON_GOLPE:
        golpe = 1 - golpe
    else:
        print(f"código desconocido: {codigo}")

# Prueba sin Arduino: solo se ejecuta con `python pc/estado.py`.
if __name__ == "__main__":
    # La velocidad tiene que avanzar y volver a 0 después de la última.
    print(f"Velocidad: {velocidad}")
    for _ in range(4):
        aplicar_accion(configuracion.BOTON_CAIDA)
        print(f"Velocidad: {velocidad}")
    # La pausa tiene que alternar entre 1 y 0.
    aplicar_accion(configuracion.BOTON_PAUSA)
    print(f"Pausa: {pausa}")
    aplicar_accion(configuracion.BOTON_PAUSA)
    print(f"Pausa: {pausa}")
    aplicar_accion(configuracion.BOTON_PAUSA)
    print(f"Pausa: {pausa}")
    # Un código que no existe: tiene que mostrar el aviso y no cambiar nada.
    aplicar_accion(99)
