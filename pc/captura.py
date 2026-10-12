"""
captura.py — Captura de audio para el analizador.
 
Permite elegir un dispositivo de audio por su nombre, grabar un tramo fijo
de audio, medir su nivel (RMS) y capturar de forma continua por bloques.
"""

import sounddevice
import numpy
import time

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
    muestreo = 48000
    cantidad_muestras = int(segundos * muestreo)
    audio = sounddevice.rec(cantidad_muestras, samplerate=muestreo, channels=cantidad_canales, device=numero_dispositivo)
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
    (callback).
 
    Muestra el nivel del bloque como una barra de '#'.
    """
    if estado: 
        print(estado)
    nivel = nivel_rms(bloque)
    # Escala para que la barra tenga un largo visible (0 a 100 '#').
    cantidad = int(nivel * 100)
    print("#" * cantidad)    

def capturar_continuo(numero_dispositivo):
    """
    Captura audio de forma continua desde el dispositivo indicado.
 
    El audio llega en bloques de 1024 muestras y cada bloque se
    procesa en al_recibir_bloque(). 
    """
    info = sounddevice.query_devices(numero_dispositivo)
    canales = info['max_input_channels']
    # El flujo queda abierto mientras se está dentro del `with`
    with sounddevice.InputStream(
        device=numero_dispositivo, 
        channels=canales, 
        samplerate=48000, 
        blocksize=1024, 
        callback=al_recibir_bloque):
        while True:
            time.sleep(0.1)

# Esta parte solo se ejecuta si se corre este archivo directamente (python pc/captura.py)
# no cuando otro módulo lo importa.
if __name__ == "__main__":
    try:
        numero = buscar_dispositivo("BlackHole")
        print("Capturando… (Ctrl+C para salir)")
        capturar_continuo(numero)
    except KeyboardInterrupt:
        print("Captura detenida")
