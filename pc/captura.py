import sounddevice
import numpy
import time

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

def al_recibir_bloque(bloque, cantidad_muestras, tiempo, estado):
    if estado: 
        print(estado)
    nivel = nivel_rms(bloque)
    cantidad = int(nivel * 100)
    print("#" * cantidad)    

def capturar_continuo(numero_dispositivo):
    info = sounddevice.query_devices(numero_dispositivo)
    canales = info['max_input_channels']
    with sounddevice.InputStream(
        device=numero_dispositivo, 
        channels=canales, 
        samplerate=48000, 
        blocksize=1024, 
        callback=al_recibir_bloque):
        while True:
            time.sleep(0.1)

if __name__ == "__main__":
    try:
        numero = buscar_dispositivo("BlackHole")
        print("Capturando… (Ctrl+C para salir)")
        capturar_continuo(numero)
    except KeyboardInterrupt:
        print("Captura detenida")
