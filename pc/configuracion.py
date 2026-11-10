"""
configuracion.py — Constantes del analizador de audio.

Todos los módulos leen de acá los valores fijos del programa: captura,
bandas, paquete serie, calibración, velocidades de caída, botones, picos,
notas, visualizador y detección de golpes.

Los nombres de los dispositivos de audio y PUERTO_SERIE dependen de cada
computadora: cada uno los ajusta en la suya.
"""

import os

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
# Fuente con la que arranca el programa. Después se cambia con la tecla I
# o los botones MIC | LINE del panel.
FUENTE_AUDIO = MODO_LINE
SIN_NOTA = 12                   # valor de la nota (byte 18) cuando no hay una nota clara
INTERVALO_ENVIO = 1 / 30        # tiempo mínimo entre dos paquetes, en segundos
# Forma de las barras en la OLED (byte 21 del paquete). La OLED solo sabe
# dibujar barras y centro: con "onda" y "espectrograma" muestra barras.
FORMA_OLED_BARRAS = 0           # desde el piso (formas "barras", "onda" y "espectrograma")
FORMA_OLED_CENTRO = 1           # desde el centro (forma "centro")

# --- Calibración automática (ver bandas.actualizar_niveles) ---
RANGO_MINIMO_DB = 12.0       # distancia mínima entre piso y techo de una banda
RANGO_MAXIMO_DB = 50.0       # distancia máxima entre piso y techo de una banda
TECHO_MINIMO_DB = -70.0      # el techo nunca baja de acá (protege del silencio)
VELOCIDAD_TECHO_DB = 0.005   # dB por bloque que baja el techo (~0,23 dB/s): casi fijo, así una parte suave se ve baja
RECALIBRAR_MARGEN_DB = 10.0
RECALIBRAR_RANGO_DB = 25.0
# El piso se mueve despacio en las dos direcciones: así no persigue los
# pozos del ruido y el ruido de fondo queda por debajo de él (barras quietas).
VELOCIDAD_PISO_BAJA_DB = 0.02  # dB por bloque que baja el piso (~0,9 dB/s)
VELOCIDAD_PISO_SUBE_DB = 0.1   # dB por bloque que sube el piso (~4,7 dB/s)
# Peso del nivel anterior al promediar los dB entre bloques (0 = sin
# promedio, ver bandas.promediar). Hay dos promedios:
# - Calibración (piso y techo): parejo, 0,7 al subir y al bajar. Con 0,7 el
#   ruido de los graves deja de saltar y no empuja el techo para arriba.
# - Barras: sin promedio al subir, así un aumento brusco de volumen se ve
#   en ~64 ms (con 0,7 tardaba 190 a 450 ms); al bajar, 0,7. Los graves
#   tiemblan un poco más (medido con ruido rosa: p95 de 4,4 a 9 px).
PROMEDIO_CALIBRACION_DB = 0.7
PROMEDIO_SUBIDA_DB = 0.0
PROMEDIO_BAJADA_DB = 0.7
TECHO_INICIAL_DB = 25.0      # techo con el que arranca cada banda
DISTANCIA_MAXIMA_DB = 35     # un techo no queda más de esto por debajo del techo más alto

# --- Caída de las barras ---
# Píxeles que baja cada barra por bloque, según la velocidad elegida con el
# botón de caída: 0 = lento, 1 = normal, 2 = rápido.
VELOCIDADES_CAIDA = [0.7, 1.0, 2.0]
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
MARGEN_AFINADO_CENTS = 5        # el afinador marca en verde dentro de ±5 cents
LA_REFERENCIA = 440             # Hz del A4; todas las notas se calculan desde acá
NOTA_FRECUENCIA_MINIMA = 60     # nota mas grave que busca (B1)
NOTA_FRECUENCIA_MAXIMA = 1000   # nota mas aguda que busca (B5)
NOTA_UMBRAL_CLARIDAD = 0.15     # Por encima de esto, “sin nota”
NOTA_VOLUMEN_MINIMO_DB = -60    # Por debajo, silencio
CROMA_FRECUENCIA_MINIMA = 130   # Hz: debajo, cada valor de la FFT abarca más de un semitono
CROMA_FRECUENCIA_MAXIMA = 2000  # Hz: arriba casi no hay notas, solo armónicos y platillos
PROMEDIO_CROMA = 0.85           # Mezcla el croma anterior con el nuevo, evita el parpadeo
# Parte mínima de la nota más fuerte en la croma promediada (en potencia)
# para que haya nota.
CROMA_MINIMA = 0.19
CROMA_ESPERA_SIN_NOTA = 47      # bloques con la croma plana (~1 s) antes de apagar la nota
# Plantillas de acordes (ver nota.py): cada una suma sus 3 notas con sus
# armónicos. Medido con guitarra simulada: raíz correcta 94–99% (la nota
# más fuerte daba 28–36%: mostraba la quinta, G en un C).
CROMA_DECAIMIENTO_ARMONICOS = 0.6   # amplitud de cada armónico respecto del anterior
CROMA_PESO_RAIZ = 1.3               # la raíz pesa más que la tercera y la quinta
# Puntaje que la raíz nueva le tiene que sacar a la actual para reemplazarla.
# Los puntajes van de 0 a 1 y están cerca entre sí (0,8–0,95): sin margen
# daba 23 cambios para 7 reales con ruido; con 0,03, 15.
CROMA_MARGEN_CAMBIO = 0.03
# Bloques seguidos (~0,2 s) que la raíz nueva tiene que liderar (con el
# margen) para reemplazar a la actual.
CROMA_BLOQUES_CAMBIO = 5
# Lados del estéreo ((izquierdo − derecho) / 2) respecto de la mezcla, en dB.
# Por encima, el modo nota usa los lados y así ignora la voz, que va al
# centro.
CROMA_UMBRAL_LADOS_DB = -20
PROMEDIO_AFINADOR = 0.8         # Peso de la frecuencia anterior en el afinador

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
PASOS_ONDA = 12               # puntos de la curva entre dos bandas en la forma "onda"
OPACIDAD_RELLENO_ARRIBA = 0.45  # relleno de la onda justo debajo de la curva
OPACIDAD_RELLENO_ABAJO = 0.03   # relleno de la onda en el piso
ANCHO_BRILLO_ONDA = 11        # píxeles del brillo detrás de la curva (la línea mide 3)
OPACIDAD_BRILLO_ONDA = 0.22   # opacidad de ese brillo
ANCHO_TIRA_GOLPE = 10         # píxeles de las tiras de golpe a los costados (antes 6)
SEPARACION_PICO_ONDA = 6      # píxeles entre la curva de peak y el pico real, en la forma onda
OPACIDAD_PICO_ONDA = 0.7      # opacidad de esa curva
TRANSICION_COLOR = 0.2        # segundos que tarda el color de las bandas en pasar al nuevo (nota o modo)
BRILLO_BASE_BARRA = 0.5       # en la base, cada barra tiene este brillo de su color (1 en el tope)
ANCHO_BRILLO_BARRA = 5        # píxeles que sobresale el brillo alrededor de cada barra
OPACIDAD_BRILLO_BARRA = 0.14  # opacidad de ese brillo
ALTO_REFLEJO = 0.14           # parte del alto del espectro que ocupa el reflejo (barras y onda)
OPACIDAD_REFLEJO = 0.22       # opacidad del reflejo junto al piso (se desvanece hacia abajo)
OPACIDAD_PULSO_GOLPE = 0.07   # cuánto se aclara el fondo del espectro con cada golpe
DURACION_FUNDIDO_FORMA = 0.3  # segundos del fundido al cambiar de forma
DURACION_BOTON = 0.15         # segundos de la animación de los botones (mouse encima y activar)
NIVEL_MINIMO_DB = -60         # medidor de nivel: de este valor (dBFS) a 0
NIVEL_AMARILLO_DB = -12       # desde acá el medidor se pone amarillo
NIVEL_ROJO_DB = -3            # y desde acá, rojo (cerca de saturar)
NIVEL_CAIDA_DB = 20           # dB por segundo que baja el medidor (sube enseguida)
OPACIDAD_GOLPE = 0.35         # opacidad del relleno de golpe sobre las barras
DURACION_DESTELLO_GOLPE = 0.25  # segundos que se ven encendidas las tiras laterales de golpe

# --- Detección de golpe (ver golpe.py) ---
BANDAS_DETECCION_GOLPE = [0, 1]   # bandas graves que se miran para detectar el golpe (40–90 Hz)
GOLPE_SUBIDA_DB = 6.0             # dB que tienen que subir los graves respecto del bloque anterior
GOLPE_DISTANCIA_TECHO_DB = 15.0   # los graves tienen que quedar a menos de esto de su techo
GOLPE_ESPERA = 0.15               # segundos sin aceptar otro golpe después de uno

# --- Tempo (BPM, ver golpe.estimar_bpm) ---
BPM_VENTANA = 8.0                 # segundos de golpes que se usan para calcular el tempo
BPM_MINIMO_GOLPES = 4             # con menos golpes en la ventana no se muestra tempo
BPM_SIN_GOLPES = 3.0              # si pasa esto sin golpes, el tempo se borra (la música paró)
BPM_MINIMO = 70                   # el tempo se dobla o se divide por 2 hasta quedar
BPM_MAXIMO = 180                  # entre BPM_MINIMO y BPM_MAXIMO (evita 60 o 240 por un bombo cada 2 tiempos)
BPM_TOLERANCIA = 0.25             # se promedian los intervalos a menos de este 25 % de la mediana

# --- Preferencias guardadas (ver estado.guardar_preferencias) ---
# Archivo donde se guarda la configuración elegida, al lado de este .py.
# No va al repositorio (está en .gitignore): es de cada computadora.
ARCHIVO_PREFERENCIAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preferencias.json")
