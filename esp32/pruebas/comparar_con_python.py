"""
comparar_con_python.py — Compara el análisis del ESP32 (C++) con el de la
compu (pc/principal.al_recibir_bloque) bloque a bloque.

1. Arma una señal estéreo de prueba de 13 s (silencio, bombo a 120 BPM,
   acordes con y sin estéreo, un tono para el afinador, ruido y un tramo
   mono como el micrófono) y una lista de eventos (cambios de velocidad,
   forma, pico, afinador, pausa, recalibración y fuente).
2. La pasa por principal.al_recibir_bloque, con el reloj simulado.
3. Corre los ejecutables comparar_double y comparar_float (los compila
   correr_pruebas.sh) con la misma señal y los mismos eventos.
4. Compara alturas, picos, destello, nota, tempo, frecuencia y paquetes.

Uso (desde la raíz del proyecto, después de correr_pruebas.sh):
    .venv/bin/python esp32/pruebas/comparar_con_python.py
"""

import os
import subprocess
import sys
import tempfile

import numpy

AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(AQUI, "salida")
sys.path.insert(0, os.path.join(AQUI, "..", "..", "pc"))

import configuracion  # noqa: E402

# Las pruebas cambian el estado y cambiar() guarda las preferencias: se
# usa un archivo temporal para no pisar las de verdad.
configuracion.ARCHIVO_PREFERENCIAS = os.path.join(tempfile.mkdtemp(), "preferencias.json")

# Reloj simulado: principal.py usa time.monotonic() para la espera entre
# golpes, el tempo y el intervalo entre paquetes.
import time  # noqa: E402
reloj = [0.0]
time.monotonic = lambda: reloj[0]

import principal  # noqa: E402
import estado  # noqa: E402

FS = configuracion.FRECUENCIA_MUESTREO
M = configuracion.TAMANO_BLOQUE
DURACION = 13.0


def segundo_a_bloque(s):
    return int(round(s * FS / M))


def armar_senal():
    """Señal estéreo (muestras, 2) en float32, con semilla fija."""
    azar = numpy.random.default_rng(3)
    n = int(DURACION * FS) // M * M
    t = numpy.arange(n) / FS
    izq = numpy.zeros(n)
    der = numpy.zeros(n)

    def tono(f, desde, hasta, amplitud, armonicos=4):
        """Tono con armónicos entre `desde` y `hasta` segundos."""
        senal = numpy.zeros(n)
        tramo = (t >= desde) & (t < hasta)
        for h in range(1, armonicos + 1):
            senal[tramo] += amplitud * 0.6 ** (h - 1) * numpy.sin(2 * numpy.pi * f * h * t[tramo])
        return senal

    def bombo(desde, hasta):
        """Un golpe de 55 Hz que se apaga, cada 0,5 s (120 BPM)."""
        senal = numpy.zeros(n)
        for inicio in numpy.arange(desde, hasta, 0.5):
            tramo = (t >= inicio) & (t < inicio + 0.3)
            u = t[tramo] - inicio
            senal[tramo] += 0.8 * numpy.exp(-u / 0.08) * numpy.sin(2 * numpy.pi * 55 * u)
        return senal

    # 1–5 s: bombo al centro y C mayor abierto (C a la izquierda, E y G a la derecha).
    golpes = bombo(1, 5) + bombo(5, 7) + bombo(11, 13)
    izq += golpes
    der += golpes
    izq += tono(130.81, 1, 5, 0.15) + tono(261.63, 1, 5, 0.1)
    der += tono(164.81, 1, 5, 0.12) + tono(196.00, 1, 5, 0.12)
    # 5–7 s: A menor al centro (igual en los dos canales).
    for f in (220.0, 261.63, 329.63):
        a_menor = tono(f, 5, 7, 0.1)
        izq += a_menor
        der += a_menor
    # 7–9 s: un La 440 para el afinador. 9–11 s: Sol 196 y ruido suave.
    la = tono(440.0, 7, 9, 0.3)
    sol = tono(196.0, 9, 11, 0.2)
    izq += la + sol
    der += la + sol
    ruido = azar.normal(0, 0.02, n) * ((t >= 9) & (t < 11))
    izq += ruido
    der += ruido * 0.5
    # 11–13 s: E menor (solo cuenta el izquierdo: el micrófono es mono).
    for f in (164.81, 196.0, 246.94):
        izq += tono(f, 11, 13, 0.1)
    # Platillo: ruido agudo de fondo en toda la parte con música.
    platillo = azar.normal(0, 0.01, n) * ((t >= 1) & (t < 13))
    izq += platillo
    der += platillo
    return numpy.stack([izq, der], axis=1).astype(numpy.float32)


EVENTOS = [
    (0, "golpe", 1),
    (segundo_a_bloque(3), "velocidad", 2),
    (segundo_a_bloque(5), "forma", 1),
    (segundo_a_bloque(5), "pico", 0),
    (segundo_a_bloque(7), "afinador", 1),
    (segundo_a_bloque(9), "afinador", 0),
    (segundo_a_bloque(9.5), "pausa", 1),
    (segundo_a_bloque(10), "pausa", 0),
    (segundo_a_bloque(10.5), "recalibrar", 0),
    (segundo_a_bloque(11), "fuente", configuracion.MODO_MIC),
]


def aplicar_evento(accion, valor):
    """Lo mismo que hace comparar.cpp, con las funciones de la compu."""
    if accion == "recalibrar":
        estado.pedir_recalibracion("prueba")
    elif accion == "fuente":
        # Lo que hace principal.elegir_dispositivo() al cambiar de fuente.
        principal.memoria[:] = 0
        principal.memoria_lados[:] = 0
        principal.db_suave = None
        principal.db_barras = None
        estado.pedido_recalibrar = True
        estado.cambiar("fuente", valor, "prueba")
    elif accion == "forma":
        # En Python la forma es un texto; en el ESP32, su índice.
        estado.cambiar("forma", configuracion.FORMAS[valor], "prueba")
    else:
        estado.cambiar(accion, valor, "prueba")


def correr_python(senal, archivo):
    """Pasa la señal por principal.al_recibir_bloque y escribe una línea por bloque."""
    mono = False
    ultimo = None
    # La prueba arranca en LINE (señal estéreo) en los dos lados, sea cual
    # sea FUENTE_AUDIO: comparar.cpp hace lo mismo.
    estado.fuente = configuracion.MODO_LINE
    with open(archivo, "w") as salida:
        for b in range(len(senal) // M):
            for bloque_evento, accion, valor in EVENTOS:
                if bloque_evento == b:
                    aplicar_evento(accion, valor)
                    if accion == "fuente":
                        mono = valor == configuracion.MODO_MIC
            reloj[0] = 1000.0 + b * M / FS
            bloque = senal[b * M:(b + 1) * M]
            if mono:
                bloque = bloque[:, :1]
            principal.al_recibir_bloque(bloque, M, None, None)
            a = estado.audio
            nuevo = estado.ultimo_paquete is not ultimo
            ultimo = estado.ultimo_paquete
            numeros = list(a["alturas"]) + list(a["destello"]) + list(a["picos"])
            linea = " ".join(f"{x:.6f}" for x in numeros)
            frecuencia = a["frecuencia"] if a["frecuencia"] is not None else float("nan")
            cents = a["cents"] if a["cents"] is not None else float("nan")
            bpm = a["bpm"] if a["bpm"] is not None else -1
            linea += f" {a['nota']} {frecuencia:.6f} {cents:.6f} {bpm} {a['nivel']:.6f} {1 if nuevo else 0}"
            if nuevo:
                linea += " " + " ".join(str(x) for x in ultimo[1:])
            salida.write(linea + "\n")


def leer(archivo):
    filas = []
    with open(archivo) as entrada:
        for linea in entrada:
            partes = linea.split()
            valores = [float(x) for x in partes[:48]]
            nota, frecuencia, cents, bpm, nivel, nuevo = partes[48:54]
            paquete = [int(x) for x in partes[54:]] if nuevo == "1" else None
            filas.append({
                "barras": numpy.array(valores),
                "nota": int(nota), "frecuencia": float(frecuencia), "cents": float(cents),
                "bpm": int(bpm), "nivel": float(nivel), "paquete": paquete,
            })
    return filas


def comparar(nombre, python, cpp):
    """Imprime una tabla con las diferencias entre las dos corridas."""
    if len(python) != len(cpp):
        print(f"ERROR {nombre}: {len(python)} bloques en Python y {len(cpp)} en C++")
        return False
    n = len(python)
    dif_barras = numpy.array([numpy.max(numpy.abs(p["barras"] - c["barras"])) for p, c in zip(python, cpp)])
    notas = sum(p["nota"] != c["nota"] for p, c in zip(python, cpp))
    bpms = sum(p["bpm"] != c["bpm"] for p, c in zip(python, cpp))
    paquetes_python = sum(p["paquete"] is not None for p in python)
    momentos = sum((p["paquete"] is None) != (c["paquete"] is None) for p, c in zip(python, cpp))
    bytes_distintos = 0
    for p, c in zip(python, cpp):
        if p["paquete"] is not None and c["paquete"] is not None:
            bytes_distintos += sum(a != b for a, b in zip(p["paquete"], c["paquete"]))
    con_frecuencia = [(p["frecuencia"], c["frecuencia"]) for p, c in zip(python, cpp)
                      if not numpy.isnan(p["frecuencia"]) and not numpy.isnan(c["frecuencia"])]
    frecuencia_sola = sum(numpy.isnan(p["frecuencia"]) != numpy.isnan(c["frecuencia"]) for p, c in zip(python, cpp))
    dif_cents = max((abs(1200 * numpy.log2(a / b)) for a, b in con_frecuencia), default=0.0)
    dif_nivel = max(abs(p["nivel"] - c["nivel"]) for p, c in zip(python, cpp))

    print(f"\n=== Python vs C++ con {nombre} ({n} bloques, {paquetes_python} paquetes) ===")
    print(f"{'Qué':<44} {'Resultado':>14}")
    print(f"{'Barras/picos/destello: diferencia máxima (px)':<44} {dif_barras.max():>14.4f}")
    print(f"{'Barras: bloques con diferencia > 0,5 px':<44} {int(numpy.sum(dif_barras > 0.5)):>14}")
    print(f"{'Nota distinta (bloques)':<44} {notas:>14}")
    print(f"{'Tempo distinto (bloques)':<44} {bpms:>14}")
    print(f"{'Afinador: frecuencia en uno solo (bloques)':<44} {frecuencia_sola:>14}")
    print(f"{'Afinador: diferencia máxima (cents)':<44} {dif_cents:>14.4f}")
    print(f"{'Nivel: diferencia máxima (dB)':<44} {dif_nivel:>14.4f}")
    print(f"{'Paquete en un solo lado (bloques)':<44} {momentos:>14}")
    print(f"{'Bytes de paquete distintos':<44} {bytes_distintos:>14}")
    return dif_barras, notas, bpms, momentos, bytes_distintos, frecuencia_sola


def main():
    senal = armar_senal()
    archivo_senal = os.path.join(SALIDA, "senal.f32")
    archivo_eventos = os.path.join(SALIDA, "eventos.txt")
    senal.tofile(archivo_senal)
    with open(archivo_eventos, "w") as salida:
        for bloque, accion, valor in EVENTOS:
            salida.write(f"{bloque} {accion} {valor}\n")

    archivo_python = os.path.join(SALIDA, "resultado_python.txt")
    correr_python(senal, archivo_python)
    python = leer(archivo_python)

    errores = 0
    for tipo in ("double", "float"):
        archivo_cpp = os.path.join(SALIDA, f"resultado_{tipo}.txt")
        subprocess.run([os.path.join(SALIDA, f"comparar_{tipo}"), archivo_senal, archivo_eventos, archivo_cpp], check=True)
        dif_barras, notas, bpms, momentos, bytes_distintos, frecuencia_sola = comparar(tipo, python, leer(archivo_cpp))
        if tipo == "double":
            # Con double tiene que dar lo mismo que el Python (salvo redondeos).
            bien = (dif_barras.max() < 0.01 and notas == 0 and bpms == 0 and momentos == 0
                    and frecuencia_sola == 0 and bytes_distintos == 0)
        else:
            # Con float se aceptan diferencias chicas (se informan arriba).
            bien = (numpy.mean(dif_barras > 0.5) < 0.01 and notas <= 2 and bpms == 0 and momentos == 0
                    and bytes_distintos == 0)
        print("Resultado:", "OK" if bien else "ERROR")
        errores += 0 if bien else 1
    print("\nComparación: todo bien" if errores == 0 else f"\nComparación: {errores} con errores")
    return errores


if __name__ == "__main__":
    sys.exit(main())
