# Configuración de parámetros de captura de audio
FRECUENCIA_MUESTREO = 48000
TAMANO_BLOQUE = 1024
TAMANO_VENTANA = 4096

# Dispositivos de audio
DISPOSITIVO_SISTEMA = "BlackHole 2ch"
DISPOSITIVO_MICROFONO = "Micrófono de MacBook Air"

# Bandas de frecuencia (en Hz) para el análisis
BANDAS = [(40, 60), (60, 90), (90, 130), (130, 190),
    (190, 280), (280, 410), (410, 610), (610, 900), (900, 1300), (1300, 1950),
    (1950, 2850), (2850, 4200), (4200, 6250), (6250, 9200), (9200, 13500), (13500, 20000)]

# Puerto serie
PUERTO_SERIE = "/dev/cu.usbmodem11401" # ajustar según el puerto al que esté conectado el Arduino
VELOCIDAD_SERIE = 115200

# Paquete al Arduino
BYTE_INICIO = 255
CANTIDAD_BARRAS = len(BANDAS)
ALTURA_MAXIMA = 32
MODO_MIC = 0
MODO_LINE = 1
SIN_NOTA = 12

# Parámetros de calibración de la señal de audio
RANGO_MINIMO_DB = 12.0
RANGO_MAXIMO_DB = 50.0
TECHO_MINIMO_DB = -70.0
VELOCIDAD_DB    = 0.3
TECHO_INICIAL_DB = 25.0
DISTANCIA_MAXIMA_DB = 35  