"""
configuracion.py — Constantes del analizador de audio.

Todos los módulos leen de acá los valores fijos del programa: captura,
bandas, paquete serie, calibración, velocidades de caída y botones.

Los nombres de los dispositivos de audio y PUERTO_SERIE dependen de cada
computadora: cada uno los ajusta en la suya.
"""

# --- Captura de audio ---
FRECUENCIA_MUESTREO = 48000   # muestras por segundo (Hz)
TAMANO_BLOQUE = 1024          # muestras por bloque que entrega sounddevice (~21 ms)
TAMANO_VENTANA = 4096         # muestras que se analizan con la FFT (~85 ms)

# --- Dispositivos de audio ---
DISPOSITIVO_SISTEMA = "BlackHole 2ch"
DISPOSITIVO_MICROFONO = "Micrófono de MacBook Air"

# --- Bandas de frecuencia (en Hz) para el análisis ---
BANDAS = [(40, 60), (60, 90), (90, 130), (130, 190),
    (190, 280), (280, 410), (410, 610), (610, 900), (900, 1300), (1300, 1950),
    (1950, 2850), (2850, 4200), (4200, 6250), (6250, 9200), (9200, 13500), (13500, 20000)]

# --- Puerto serie ---
PUERTO_SERIE = "/dev/cu.usbmodem11401" # ajustar según el puerto al que esté conectado el Arduino
VELOCIDAD_SERIE = 115200               # baudios; tiene que coincidir con Serial.begin() del Arduino

# --- Paquete al Arduino (ver docs/protocolo_serie.md) ---
BYTE_INICIO = 255               # marca el comienzo de cada paquete; ningún dato puede valer 255
CANTIDAD_BARRAS = len(BANDAS)
ALTURA_MAXIMA = 32              # alto de la OLED en píxeles
MODO_MIC = 0
MODO_LINE = 1
FUENTE_AUDIO = MODO_LINE # Cambiar a MODO_MIC si se quiere usar el micrófono en lugar de la entrada de línea
SIN_NOTA = 12
INTERVALO_ENVIO = 1 / 30        # tiempo mínimo entre dos paquetes, en segundos

# --- Calibración automática (ver bandas.actualizar_niveles) ---
RANGO_MINIMO_DB = 12.0       # distancia mínima entre piso y techo de una banda
RANGO_MAXIMO_DB = 50.0       # distancia máxima entre piso y techo de una banda
TECHO_MINIMO_DB = -70.0      # el techo nunca baja de acá (protege del silencio)
VELOCIDAD_DB    = 0.3        # dB por bloque que se acercan piso y techo a la música
TECHO_INICIAL_DB = 25.0      # techo con el que arranca cada banda
DISTANCIA_MAXIMA_DB = 35     # un techo no queda más de esto por debajo del techo más alto

# --- Visualización ---
# Píxeles que baja cada barra por bloque, según la velocidad elegida con el
# botón de caída: 0 = lento, 1 = normal, 2 = rápido.
VELOCIDADES_CAIDA = [1.0, 2.0, 4.0]
VELOCIDAD_INICIAL = 1 # índice en VELOCIDADES_CAIDA: arranca en la velocidad normal

# --- Botones ---
# Código del byte que manda el Arduino al apretar cada botón.
BOTON_CAIDA = 1   # cambia la velocidad de caída de las barras
BOTON_PAUSA = 2   # pausa / reanuda el envío al Arduino
BOTON_PICO = 3    # muestra / oculta la marca de pico en la OLED y en el vizualizador
BOTON_GOLPE = 4   # activa / desactiva el efecto de golpe
# Barras que se llenan cuando se detecta un golpe: la 1, 2, 15 y 16.
BARRAS_GOLPE = [0, 1, 14, 15]
