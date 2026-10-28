"""
estado.py — Estado compartido del analizador.

Guarda dos cosas:
1. El estado del sistema (velocidad, pausa, pico, golpe, afinador, forma,
   color...). La compu es la única dueña: el Arduino (con sus botones),
   Blynk y la ventana de la compu solo piden cambios, siempre con
   cambiar() (o aplicar_accion() para los códigos de botón). Así nunca hay
   dos versiones del modo actual, y ultimo_cambio dice quién lo cambió.
2. Los últimos resultados del audio (alturas, picos, destello, nota) y el
   último paquete enviado al Arduino. Los escribe el callback de audio y
   los lee la ventana.

Importante: usar siempre `import estado` y leer `estado.pausa`, nunca
`from estado import pausa`. Esa forma copia el valor en el momento de
importar y después no ve los cambios que hacen los botones.
"""

import time
import numpy
import configuracion

# --- Estado del sistema ----------------------------------------------------
velocidad = configuracion.VELOCIDAD_INICIAL
# 1 = no se envía al Arduino (la compu sigue capturando y mostrando).
pausa = 0
# 1 = se dibuja la marca de pico (en la OLED y en la compu).
pico = 1
# 1 = se llenan las barras de BARRAS_GOLPE cuando se detecta un golpe.
golpe = 0
# 1 = la tarjeta de nota muestra el afinador (solo en la compu).
afinador = 0

forma = "barras"
color = "nota"
color_fijo = 0

fuente = configuracion.FUENTE_AUDIO

# Conexiones: las actualiza principal.py (Arduino) y blynk_cliente.py (Blynk).
arduino_conectado = False
blynk_conectado = False

# Último cambio: (texto, origen, momento). Origen: "compu", "Arduino" o "Blynk".
ultimo_cambio = ("Inicio", None, time.monotonic())

# Funciones que se llaman después de cada cambio, con (campo, valor, origen).
# Ahí se va a enganchar Blynk para enterarse de los cambios de los demás.
suscriptores = []

# True = se pidió recalibrar y el callback de audio todavía no lo atendió.
pedido_recalibrar = False

# Valores permitidos de cada campo que se puede cambiar.
VALORES = {
    "velocidad": range(len(configuracion.VELOCIDADES_CAIDA)),
    "pausa": (0, 1),
    "pico": (0, 1),
    "golpe": (0, 1),
    "afinador": (0, 1),
    "forma": configuracion.FORMAS,
    "color": configuracion.MODOS_COLOR,
    "color_fijo": range(len(configuracion.COLORES_FIJOS)),
}

NOMBRES_VELOCIDADES = ["lenta", "normal", "rápida"]
NOMBRES_CAMPOS = {"pausa": "Pausa", "pico": "Peak", "golpe": "Golpe", "afinador": "Afinador"}

# --- Resultados del audio --------------------------------------------------
# El callback los reemplaza enteros con publicar_audio(): la ventana toma
# el diccionario de una vez y nunca ve una mezcla de dos bloques.
audio = {
    "alturas": numpy.zeros(configuracion.CANTIDAD_BARRAS),   # float 0–32
    "destello": numpy.zeros(configuracion.CANTIDAD_BARRAS),  # float 0–32, relleno de golpe
    "picos": numpy.zeros(configuracion.CANTIDAD_BARRAS),     # float 0–32
    "nota": configuracion.SIN_NOTA,                          # 0–11 o SIN_NOTA
    "frecuencia": None,                                      # Hz, para el afinador
    "cents": None,                                           # −50…+50, para el afinador
    "momento_golpe": None,                                   # time.monotonic() del último golpe
}
# Último paquete armado para el Arduino (bytes) y los picos de ese momento:
# el espejo de la OLED dibuja esto. None hasta el primer paquete.
ultimo_paquete = None
picos_enviados = None


def describir(campo, valor):
    """Texto corto de un cambio, para el encabezado: "Peak activado", "Forma: onda"…"""
    if campo in NOMBRES_CAMPOS:
        nombre = NOMBRES_CAMPOS[campo]
        terminacion = "a" if campo == "pausa" else "o"
        return f"{nombre} {'activad' if valor else 'desactivad'}{terminacion}"
    if campo == "velocidad":
        return f"Caída {NOMBRES_VELOCIDADES[valor]}"
    if campo == "color_fijo":
        return f"Color fijo: {configuracion.COLORES_FIJOS[valor][0]}"
    return f"{campo.capitalize()}: {valor}"


def cambiar(campo, valor, origen):
    """
    Única forma de cambiar el estado del sistema. La usan la ventana
    ("compu"), los botones del Arduino ("Arduino") y Blynk ("Blynk").

    Comprueba que el valor sea válido (si no, da ValueError), lo guarda,
    anota ultimo_cambio con su origen y avisa a los suscriptores.
    """
    global ultimo_cambio
    if campo not in VALORES:
        raise ValueError(f"Campo desconocido: {campo}")
    if valor not in VALORES[campo]:
        raise ValueError(f"Valor inválido para {campo}: {valor}")
    # globals() es el diccionario de las variables de este módulo: así se
    # cambia la variable por su nombre sin un if por cada campo.
    globals()[campo] = valor
    ultimo_cambio = (describir(campo, valor), origen, time.monotonic())
    for funcion in suscriptores:
        funcion(campo, valor, origen)


def alternar(campo, origen):
    """Pasa un campo de 0 a 1 o de 1 a 0 (pausa, pico, golpe, afinador)."""
    cambiar(campo, 1 - globals()[campo], origen)


def siguiente(campo, origen):
    """Pasa un campo al valor siguiente de su lista, y vuelve al primero después del último."""
    valores = list(VALORES[campo])
    posicion = valores.index(globals()[campo])
    cambiar(campo, valores[(posicion + 1) % len(valores)], origen)


def aplicar_accion(codigo, origen="Arduino"):
    """
    Aplica la acción del botón con código `codigo` (1 a 4, ver los
    BOTON_* de configuracion). La usan los botones del Arduino y Blynk.

    El código dice qué botón se apretó, no el valor nuevo: la velocidad
    pasa a la siguiente (y vuelve a 0 después de la última) y pausa, pico
    y golpe alternan entre 0 y 1. Un código desconocido se muestra y no
    cambia nada.
    """
    if codigo == configuracion.BOTON_CAIDA:
        siguiente("velocidad", origen)
    elif codigo == configuracion.BOTON_PAUSA:
        alternar("pausa", origen)
    elif codigo == configuracion.BOTON_PICO:
        alternar("pico", origen)
    elif codigo == configuracion.BOTON_GOLPE:
        alternar("golpe", origen)
    else:
        print(f"código desconocido: {codigo}")


def pedir_recalibracion(origen):
    """Pide recalibrar piso y techo desde lo que suena ahora."""
    global pedido_recalibrar, ultimo_cambio
    pedido_recalibrar = True
    ultimo_cambio = ("Recalibrando", origen, time.monotonic())


def publicar_audio(alturas, destello, picos, nota, frecuencia, cents, momento_golpe):
    """
    Guarda los resultados de un bloque de audio. La llama el callback
    (otro hilo): se copian los arreglos para que el callback los pueda
    seguir modificando sin que la ventana vea un valor a medias.
    """
    global audio
    audio = {
        "alturas": alturas.copy(),
        "destello": destello.copy(),
        "picos": picos.copy(),
        "nota": nota,
        "frecuencia": frecuencia,
        "cents": cents,
        "momento_golpe": momento_golpe,
    }


def publicar_paquete(paquete, picos):
    """Guarda el último paquete enviado (o que se habría enviado) y sus picos, para el espejo de la OLED."""
    global ultimo_paquete, picos_enviados
    picos_enviados = picos.copy()
    ultimo_paquete = paquete


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
    aplicar_accion(configuracion.BOTON_PAUSA, "Blynk")
    print(f"Pausa: {pausa}, último cambio: {ultimo_cambio[:2]}")
    # Un código que no existe: tiene que mostrar el aviso y no cambiar nada.
    aplicar_accion(99)
    # La forma rota entre las 4 y vuelve a la primera.
    for _ in range(4):
        siguiente("forma", "compu")
        print(f"Forma: {forma}")
    # Un valor inválido tiene que dar ValueError.
    try:
        cambiar("forma", "triangulo", "compu")
        print("ERROR: forma inválida no dio error")
    except ValueError as error:
        print(f"Error esperado: {error}")
    # Los suscriptores se enteran de cada cambio.
    suscriptores.append(lambda campo, valor, origen: print(f"Aviso: {campo}={valor} ({origen})"))
    alternar("golpe", "compu")
