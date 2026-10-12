import sounddevice
import numpy

def buscar_dispositivo(texto):
    lista = sounddevice.query_devices()
    for numero, dispositivo in enumerate(lista):
        if texto in dispositivo['name'] and dispositivo['max_input_channels'] > 0:
            return numero
    raise ValueError(f"No encontré ningún dispositivo de entrada con '{texto}'")


def grabar(numero_dispositivo, segundos):
    info = sounddevice.query_devices(numero_dispositivo)
    cantidad_canales = info['max_input_channels']
    muestreo = 48000
    cantidad_muestras = int(segundos * muestreo)
    audio = sounddevice.rec(cantidad_muestras, samplerate=muestreo, channels=cantidad_canales, device=numero_dispositivo)
    sounddevice.wait() 
    return audio

def nivel_rms(audio):
    audio_cuadrado = audio ** 2
    promedio_cuadrados = numpy.mean(audio_cuadrado)
    return numpy.sqrt(promedio_cuadrados)


