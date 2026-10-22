"""
captura.py — Captura de audio para el analizador.
 
Permite elegir un dispositivo de audio por su nombre, grabar un tramo fijo
de audio, medir su nivel (RMS) y capturar de forma continua por bloques.
"""

import sounddevice
import numpy
import time
import configuracion

def buscar_dispositivo(texto):
    """
    Devuelve el número del primer dispositivo de entrada cuyo nombre
    contiene `texto`.
    """
    lista = sounddevice.query_devices()
    for numero, dispositivo in enumerate(lista):
        # Tiene que contener el texto y además poder grabar (tener canales
        # de entrada); así se descartan las salidas, como los parlantes.
        if texto in dispositivo['name'] and dispositivo['max_input_channels'] > 0:
            return numero
    raise ValueError(f"No encontré ningún dispositivo de entrada con '{texto}'")


def grabar(numero_dispositivo, segundos):
    """
    Graba `segundos` de audio desde el dispositivo indicado y devuelve
    el audio como un arreglo de numpy con forma (muestras, canales).
 
    Detiene el programa hasta que termina la grabación. Sirve para pruebas;
    el programa final usa capturar_continuo().
    """
    info = sounddevice.query_devices(numero_dispositivo)
    cantidad_canales = info['max_input_channels']
    cantidad_muestras = int(segundos * configuracion.FRECUENCIA_MUESTREO)
    audio = sounddevice.rec(cantidad_muestras, samplerate=configuracion.FRECUENCIA_MUESTREO, channels=cantidad_canales, device=numero_dispositivo)
    sounddevice.wait() 
    return audio

def nivel_rms(audio):
    """
    Devuelve el nivel RMS (valor cuadrático medio) del audio.
 
    Con las muestras entre -1 y 1, el resultado está entre 0 (silencio)
    y 1.
    """
    audio_cuadrado = audio ** 2 # al elevar al cuadrado, todo queda positivo
    promedio_cuadrados = numpy.mean(audio_cuadrado)
    return numpy.sqrt(promedio_cuadrados)

def al_recibir_bloque(bloque, cantidad_muestras, tiempo, estado):
    """
    Función que llama sounddevice cada vez que hay un bloque de audio listo
    (callback). Es solo para la prueba de este archivo: el programa usa
    principal.al_recibir_bloque().

    Muestra el nivel del bloque como una barra de '#'.
    """
    if estado: 
        print(estado)
    nivel = nivel_rms(bloque)
    # Escala para que la barra tenga un largo visible (0 a 100 '#').
    cantidad = int(nivel * 100)
    print("#" * cantidad)    

def capturar_continuo(numero_dispositivo, procesar_bloque, en_cada_vuelta=None):
    """
    Captura audio de forma continua desde el dispositivo indicado.

    El audio llega en bloques y cada bloque se pasa a `procesar_bloque`,
    una función que recibe (bloque, cantidad_muestras, tiempo, aviso)
    y que llama sounddevice cada vez que hay un bloque listo. Corre en un
    hilo aparte.

    `en_cada_vuelta` (opcional) es una función sin parámetros que se llama
    unas 100 veces por segundo desde el hilo principal, no desde el
    callback. Sirve para lo que no puede ir en el callback, como leer los
    botones del Arduino.

    Termina cuando en_cada_vuelta() devuelve False (por ejemplo, porque se
    cerró la ventana) o con Ctrl+C (KeyboardInterrupt). Al salir del
    `with`, el stream se cierra.
    """
    info = sounddevice.query_devices(numero_dispositivo)
    canales = info['max_input_channels']
    # El flujo queda abierto mientras se está dentro del `with`.
    with sounddevice.InputStream(
        device=numero_dispositivo, 
        channels=canales, 
        samplerate=configuracion.FRECUENCIA_MUESTREO, 
        blocksize=configuracion.TAMANO_BLOQUE, 
        latency='low',
        callback=procesar_bloque):
        # El audio lo procesa el callback en otro hilo; este bucle solo
        # mantiene el stream abierto y atiende en_cada_vuelta cada ~10 ms.
        while True:
            if en_cada_vuelta is not None:
                if en_cada_vuelta() is False:
                    break
            time.sleep(0.01)

# Esta parte solo se ejecuta si se corre este archivo directamente (python pc/captura.py)
# no cuando otro módulo lo importa.
if __name__ == "__main__":
    try:
        numero = buscar_dispositivo(configuracion.DISPOSITIVO_SISTEMA)
        print("Capturando… (Ctrl+C para salir)")
        capturar_continuo(numero, al_recibir_bloque)
    except KeyboardInterrupt:
        print("Captura detenida")