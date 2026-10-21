"""
principal.py — Punto de entrada del analizador de audio.

Captura el audio de forma continua y, cada vez que llega un bloque nuevo:
1. lo agrega a una ventana deslizante con las últimas TAMANO_VENTANA muestras;
2. calcula la energía de las 16 bandas y la pasa a decibeles (dB);
3. ajusta solo el piso y el techo de cada banda (calibración automática);
4. convierte los dB en alturas de barra entre 0 y ALTURA_MAXIMA (32);
5. suaviza las barras: suben enseguida y bajan según la velocidad de
   caída elegida (estado.velocidad);
6. si hay un Arduino conectado y no está en pausa, le manda las alturas
   por el puerto serie (paquete de 21 bytes, unos 21 por segundo).

Mientras tanto, el bucle principal lee los botones del Arduino unas 100
veces por segundo y aplica cada uno con estado.aplicar_accion().

Pausa: al entrar en pausa se manda un último paquete con pausa = 1 y
después no se envía nada más hasta salir de la pausa. La compu sigue
capturando y analizando.

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
import estado
import visualizador


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
# Nivel de cada banda (dB) promediado entre bloques. None hasta el primer
# bloque, que lo inicializa con su propio nivel.
db_suave = None
# Altura que se muestra de cada barra, ya suavizada. Empieza vacía.
mostradas = numpy.zeros(configuracion.CANTIDAD_BARRAS)
# Cantidad de bloques procesados (para imprimir solo uno de cada 5).
contador = 0

# --- Envío al Arduino ---
# Momento del último paquete enviado (time.monotonic(), en segundos).
# Empieza en 0 para que el primer bloque ya se pueda enviar.
ultimo_envio = 0
# Cantidad de paquetes enviados.
envios = 0
# Fuente de audio que se informa en el paquete.
modo = configuracion.FUENTE_AUDIO
# Puerto serie abierto con el Arduino. None = no hay Arduino conectado:
# el análisis sigue funcionando, pero no se envía nada.
conexion = None
# True cuando ya se mandó el último paquete con pausa = 1: así, durante la
# pausa, ese paquete sale una sola vez. Vuelve a False al salir de la pausa.
pausa_enviada = False

ultimo_dibujo = 0     # momento del último cuadro dibujado (time.monotonic())

def al_recibir_bloque(bloque, cantidad_muestras, tiempo, aviso):
    """
    Función que llama sounddevice con cada bloque de audio (callback).

    Agrega el bloque a la memoria, analiza las últimas n muestras,
    actualiza la calibración y calcula la altura suavizada de cada barra.
    Si hay Arduino conectado, le manda las alturas como mucho una vez
    cada INTERVALO_ENVIO; en pausa, solo el primer paquete (con pausa = 1).
    Muestra las alturas uno de cada 5 bloques.

    Corre en un hilo aparte (el de sounddevice), no en el bucle principal.
    """
    global contador, ultimo_envio, envios, pausa_enviada, db_suave

    # `aviso` está vacío si no hubo problemas; si se perdió audio, lo muestra.
    if aviso:
        print(aviso)

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

    # Promedio entre bloques: calma los saltos del ruido, sobre todo en los
    # graves. El primer bloque solo inicializa el promedio.
    if db_suave is None:
        db_suave = db.copy()
    else:
        bandas.promediar(db_suave, db)

    # Calibración automática: cada banda ajusta su piso y su techo según
    # lo que está sonando, así se ve bien con música fuerte o suave.
    bandas.actualizar_niveles(piso, techo, db_suave)
    # dB → altura entre 0 (en el piso) y ALTURA_MAXIMA (en el techo).
    alturas = bandas.a_alturas(db_suave, piso, techo)
    caida = configuracion.VELOCIDADES_CAIDA[estado.velocidad]
    # Suavizado: las barras suben enseguida y bajan 'caida' px por bloque.
    bandas.suavizar(mostradas, alturas, caida)

    # Se lee una sola vez: el botón la cambia desde otro hilo, y así el
    # `if` y el paquete usan el mismo valor aunque cambie en el medio.
    pausa = estado.pausa
    # Envío al Arduino: solo si hay conexión y ya pasó INTERVALO_ENVIO desde
    # el último paquete (así no se manda en todos los bloques).
    # armar_paquete ya convierte a entero y limita entre 0 y ALTURA_MAXIMA,
    # por eso se le pasa `mostradas` con decimales.
    ahora = time.monotonic()
    if conexion is not None and (ahora - ultimo_envio) >= configuracion.INTERVALO_ENVIO:
        if pausa == 0:
            # Funcionamiento normal: se envía siempre.
            paquete = serie.armar_paquete(mostradas, modo, configuracion.SIN_NOTA, pausa, estado.pico)
            serie.enviar(conexion, paquete)
            ultimo_envio = ahora
            envios += 1
            pausa_enviada = False
        elif not pausa_enviada:
            # Recién se entró en pausa: un último paquete (con pausa = 1)
            # para que el Arduino sepa que tiene que congelar la pantalla.
            paquete = serie.armar_paquete(mostradas, modo, configuracion.SIN_NOTA, pausa, estado.pico)
            serie.enviar(conexion, paquete)
            ultimo_envio = ahora
            envios += 1
            pausa_enviada = True
        # Si no: en pausa y el Arduino ya fue avisado, no se envía nada.

    contador += 1
    if contador % 5 == 0:
        print(f"Alturas: {mostradas.round().astype(int)}")

def en_cada_vuelta():
    global ultimo_dibujo
    atender_botones()
    ahora = time.monotonic()
    if (ahora - ultimo_dibujo) >= configuracion.INTERVALO_DIBUJO:
        ultimo_dibujo = ahora
        alturas = mostradas.copy()
        return visualizador.dibujar(alturas, modo, configuracion.SIN_NOTA, estado.velocidad, estado.pausa)
    return True

def atender_botones():
    """
    Lee un botón del Arduino (si llegó alguno) y lo aplica al estado.

    La llama capturar_continuo() unas 100 veces por segundo desde el
    hilo principal, no desde el callback. Sin Arduino no hace nada.
    """
    if conexion is None:
        return
    codigo = serie.leer_boton(conexion)
    if codigo is not None:
        estado.aplicar_accion(codigo)
        print(f"Botón recibido: {codigo}. Estado nuevo: velocidad={estado.velocidad}, "
              f"pausa={estado.pausa}, pico={estado.pico}, golpe={estado.golpe}")



# Solo se ejecuta con `python pc/principal.py`, no al importar el módulo.
if __name__ == "__main__":
    # Se intenta abrir el puerto del Arduino. Si no está enchufado (o el
    # Monitor Serie del IDE lo tiene ocupado), se sigue sin enviar en vez
    # de cortar el programa.
    try:
        conexion = serie.conectar(configuracion.PUERTO_SERIE)
        print("Arduino conectado")
    except serial.SerialException:
        print("No se encontró el Arduino: sigo sin enviar")

    # Se empieza a medir después de conectar(), para que los paquetes por
    # segundo no incluyan su espera de 2 s. Va antes del `try` para que
    # `inicio` exista aunque se apriete Ctrl+C enseguida.
    inicio = time.monotonic()
    try:
        if configuracion.FUENTE_AUDIO == configuracion.MODO_MIC:
            nombre = configuracion.DISPOSITIVO_MICROFONO
        elif configuracion.FUENTE_AUDIO == configuracion.MODO_LINE:
            nombre = configuracion.DISPOSITIVO_SISTEMA
        else:
            raise ValueError(f"Fuente de audio desconocida: {configuracion.FUENTE_AUDIO}")
        print(f"Usando dispositivo: {nombre}")
        numero = captura.buscar_dispositivo(nombre)
        visualizador.iniciar()
        print("Analizando… (Ctrl+C o cerrar la ventana para salir)")
        # Termina cuando en_cada_vuelta() devuelve False (se cerró la
        # ventana) o con Ctrl+C.
        captura.capturar_continuo(numero, al_recibir_bloque, en_cada_vuelta)
    except KeyboardInterrupt:
        # Ctrl+C: no hay nada más que hacer acá; el cierre está en `finally`.
        pass
    finally:
        # Se ejecuta siempre, se haya salido con Ctrl+C, cerrando la
        # ventana o por un error. Al llegar acá ya se salió del `with` de
        # capturar_continuo(), así que el stream está cerrado y el callback
        # no usa más el puerto.
        print("Análisis detenido")
        segundos = time.monotonic() - inicio
        print(f"Envíos: {envios} en {segundos:.1f} s "
              f"({envios / segundos:.1f} paquetes por segundo)")
        if conexion is not None:
            conexion.close()
        visualizador.cerrar()