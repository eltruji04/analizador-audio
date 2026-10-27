"""
configuracion.py — Constantes del analizador de audio.

Todos los módulos leen de acá los valores fijos del programa: captura,
bandas, paquete serie, calibración, velocidades de caída, botones, picos,
notas, visualizador y detección de golpes.

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
PUERTO_SERIE = "/dev/cu.usbmodem11301" # ajustar según el puerto al que esté conectado el Arduino
VELOCIDAD_SERIE = 115200               # baudios; tiene que coincidir con Serial.begin() del Arduino

# --- Paquete al Arduino (ver docs/protocolo_serie.md) ---
BYTE_INICIO = 255               # marca el comienzo de cada paquete; ningún dato puede valer 255
CANTIDAD_BARRAS = len(BANDAS)   # una barra por banda (16)
ALTURA_MAXIMA = 32              # alto de la OLED en píxeles
# Fuente de audio (byte 17 del paquete).
MODO_MIC = 0
MODO_LINE = 1
# Fija durante toda la ejecución: cambiar a MODO_MIC para usar el micrófono
# en lugar de la entrada de línea.
FUENTE_AUDIO = MODO_LINE
SIN_NOTA = 12                   # valor de la nota (byte 18) cuando no hay una nota clara
INTERVALO_ENVIO = 1 / 30        # tiempo mínimo entre dos paquetes, en segundos

# --- Calibración automática (ver bandas.actualizar_niveles) ---
RANGO_MINIMO_DB = 12.0       # distancia mínima entre piso y techo de una banda
RANGO_MAXIMO_DB = 50.0       # distancia máxima entre piso y techo de una banda
TECHO_MINIMO_DB = -70.0      # el techo nunca baja de acá (protege del silencio)
VELOCIDAD_TECHO_DB = 0.005   # dB por bloque que baja el techo (~0,23 dB/s): casi fijo, así una parte suave se ve baja
# El piso se mueve despacio en las dos direcciones: así no persigue los
# pozos del ruido y el ruido de fondo queda por debajo de él (barras quietas).
VELOCIDAD_PISO_BAJA_DB = 0.02  # dB por bloque que baja el piso (~0,9 dB/s)
VELOCIDAD_PISO_SUBE_DB = 0.1   # dB por bloque que sube el piso (~4,7 dB/s)
# Peso del nivel anterior al promediar los dB entre bloques (0 = sin
# promedio). Con 0,7 el ruido deja de saltar de un bloque al otro; la
# mitad de un cambio se ve en unos 2 bloques (~40 ms).
PROMEDIO_DB = 0.7
TECHO_INICIAL_DB = 25.0      # techo con el que arranca cada banda
DISTANCIA_MAXIMA_DB = 35     # un techo no queda más de esto por debajo del techo más alto

# --- Caída de las barras ---
# Píxeles que baja cada barra por bloque, según la velocidad elegida con el
# botón de caída: 0 = lento, 1 = normal, 2 = rápido.
VELOCIDADES_CAIDA = [1.0, 2.0, 4.0]
VELOCIDAD_INICIAL = 1  # índice en VELOCIDADES_CAIDA: arranca en la velocidad normal

# --- Botones ---
# Código del byte que manda el Arduino al apretar cada botón.
BOTON_CAIDA = 1   # cambia la velocidad de caída de las barras
BOTON_PAUSA = 2   # pausa / reanuda el envío al Arduino
BOTON_PICO = 3    # muestra / oculta la marca de pico en la OLED y en el visualizador
BOTON_GOLPE = 4   # activa / desactiva el efecto de golpe
# Barras que se llenan cuando se detecta un golpe: la 1, 2, 15 y 16.
BARRAS_GOLPE = [0, 1, 14, 15]

# --- Picos ---
CAIDA_PICO = 0.25   # píxeles que baja la marca de pico por bloque (~12 px/s): más lento que las barras

# --- Notas ---
NOMBRES_NOTAS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MARGEN_AFINADO_CENTS = 5   # el afinador marca en verde dentro de ±5 cents

# --- Visualizador en la compu ---
ANCHO_VENTANA = 1280          # tamaño fijo de la ventana, en píxeles
ALTO_VENTANA = 840
INTERVALO_DIBUJO = 1 / 30    # tiempo mínimo entre dos cuadros del visualizador, en segundos
# Formas y modos de color, en el orden en que los rotan las teclas F y C.
FORMAS = ["barras", "centro", "onda", "espectrograma"]
MODOS_COLOR = ["fijo", "arcoiris", "nota"]
# Muestras del color fijo: (nombre, (R, G, B)). El estado guarda el índice.
COLORES_FIJOS = [("celeste", (92, 200, 255)), ("verde", (63, 185, 80)),
                 ("naranja", (245, 165, 36)), ("rosa", (247, 120, 186)),
                 ("violeta", (163, 113, 247))]
LARGO_HISTORIAL = 64          # cuadros que guarda el espectrograma
DURACION_HISTORIAL = 3.0      # segundos que abarcan esos 64 cuadros
OPACIDAD_GOLPE = 0.35         # opacidad del relleno de golpe sobre las barras
DURACION_DESTELLO_GOLPE = 0.25  # segundos que se ven encendidas las tiras laterales de golpe

# --- Detección de golpe (ver golpe.py) ---
BANDAS_DETECCION_GOLPE = [0, 1]   # bandas graves que se miran para detectar el golpe (40–90 Hz)
GOLPE_SUBIDA_DB = 6.0             # dB que tienen que subir los graves respecto del bloque anterior
GOLPE_DISTANCIA_TECHO_DB = 15.0   # los graves tienen que quedar a menos de esto de su techo
GOLPE_ESPERA = 0.15               # segundos sin aceptar otro golpe después de uno

RECALIBRAR_MARGEN_DB = 10.0
RECALIBRAR_RANGO_DB = 25.0
