"""
principal.py — Punto de entrada del analizador de audio.

Captura el audio de forma continua y, cada vez que llega un bloque nuevo:
1. lo agrega a una ventana deslizante con las últimas TAMANO_VENTANA muestras;
2. calcula la energía de las 16 bandas y la pasa a decibeles (dB);
3. ajusta solo el piso y el techo de cada banda (calibración automática);
4. convierte los dB en alturas de barra entre 0 y ALTURA_MAXIMA (32);
5. suaviza las barras: suben enseguida y bajan despacio.

Por qué una ventana deslizante:
- Los bloques llegan de a TAMANO_BLOQUE muestras (1024, unos 21 ms):
  eso da una actualización rápida.
- Pero la FFT de solo 1024 muestras distingue frecuencias separadas por
  unos 47 Hz: la banda 2 (60–90 Hz) quedaría sin ningún valor y la
  banda 1 (40–60 Hz) con uno solo.
- Analizando las últimas 4096 muestras (unos 85 ms) la separación baja
  a unos 11,7 Hz, cada una de esas bandas tiene 2 valores, y el análisis
  se sigue repitiendo con cada bloque.
"""

import numpy
import serial
import time
import configuracion
import captura
import bandas
import serie


# --- Preparación: se hace una sola vez, al empezar ---------------------
# Todo esto va fuera de las funciones para que al_recibir_bloque() lo
# pueda usar y modificar bloque tras bloque sin crearlo de nuevo.
fs = configuracion.FRECUENCIA_MUESTREO
n = configuracion.TAMANO_VENTANA
# Ventana de Hann y máscaras de las bandas para tramos de largo n.
ventana, mascaras = bandas.preparar_analisis(n, fs)
# Últimas n muestras de audio (mono). Empieza en silencio (ceros).
memoria = numpy.zeros(n)
# Piso y techo de cada banda, en dB. Se ajustan solos con la música.
piso, techo = bandas.niveles_iniciales()
# Altura que se muestra de cada barra, ya suavizada. Empieza vacía.
mostradas = numpy.zeros(configuracion.CANTIDAD_BARRAS)
# Cantidad de bloques procesados (para imprimir solo uno de cada 5).
contador = 0

ultimo_envio = 0
envios = 0
modo = configuracion.MODO_LINE 
conexion = None

def al_recibir_bloque(bloque, cantidad_muestras, tiempo, estado):
    """
    Función que llama sounddevice con cada bloque de audio (callback).

    Agrega el bloque a la memoria, analiza las últimas n muestras,
    actualiza la calibración y calcula la altura suavizada de cada barra.
    Muestra las alturas uno de cada 5 bloques.
    """
    global contador, ultimo_envio, envios

    # `estado` está vacío si no hubo problemas; si se perdió audio, lo muestra.
    if estado:
        print(estado)

    # Si el dispositivo es estéreo (BlackHole), se promedian los canales.
    mono = bandas.a_mono(bloque)
    m = len(mono)

    # Ventana deslizante: se descartan las m muestras más viejas
    # corriendo el resto hacia la izquierda…
    memoria[:n-m] = memoria[m:]
    # …y el bloque nuevo ocupa las últimas m posiciones.
    memoria[-m:] = mono

    energias = bandas.calcular_bandas(memoria, ventana, mascaras)

    # Pasaje a decibeles: comprime el rango (los graves pueden tener miles
    # de veces más energía que los agudos). Se suma un número muy chico
    # para no calcular log10(0) en silencio; por eso el silencio da -120 dB.
    db = 10 * numpy.log10(energias + 0.000000000001)

    # Calibración automática: cada banda ajusta su piso y su techo según
    # lo que está sonando, así se ve bien con música fuerte o suave.
    bandas.actualizar_niveles(piso, techo, db)
    # dB → altura entre 0 (en el piso) y ALTURA_MAXIMA (en el techo).
    alturas = bandas.a_alturas(db, piso, techo)
    # Suavizado: las barras suben enseguida y bajan de a CAIDA_BARRAS.
    bandas.suavizar(mostradas, alturas)

    ahora = time.monotonic()
    if conexion is not None and (ahora - ultimo_envio) >= configuracion.INTERVALO_ENVIO:
        paquete = serie.armar_paquete(mostradas, modo, configuracion.SIN_NOTA)
        serie.enviar(conexion, paquete)
        ultimo_envio = ahora
        envios += 1

    contador += 1
    if contador % 5 == 0:
        print(f"Alturas: {mostradas.round().astype(int)}")


# Solo se ejecuta con `python pc/principal.py`, no al importar el módulo.
if __name__ == "__main__":
    try:
        conexion = serie.conectar(configuracion.PUERTO_SERIE)
        print("Arduino conectado")
    except serial.SerialException:
        print("No se encontró el Arduino: sigo sin enviar")
    
        inicio = time.monotonic()
    
    try:
        numero = captura.buscar_dispositivo(configuracion.DISPOSITIVO_SISTEMA)
        print("Analizando… (Ctrl+C para salir)")
        inicio = time.monotonic()
        captura.capturar_continuo(numero, al_recibir_bloque)
    except KeyboardInterrupt:
        print("Análisis detenido")
        segundos = time.monotonic() - inicio
        print(f"Envios: {envios}, Segundos: {segundos}, Paquetes por segundo: {envios / segundos}")
        if conexion is not None:
            conexion.close()