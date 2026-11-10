"""
principal.py — Punto de entrada del analizador de audio.

Captura el audio de forma continua y, cada vez que llega un bloque nuevo:
1. lo agrega a una ventana deslizante con las últimas TAMANO_VENTANA muestras;
2. calcula la energía de las 16 bandas y la pasa a decibeles (dB);
3. ajusta solo el piso y el techo de cada banda (calibración automática);
4. convierte los dB en alturas de barra entre 0 y ALTURA_MAXIMA (32);
5. suaviza las barras: suben enseguida y bajan según la velocidad de
   caída elegida (estado.velocidad);
6. actualiza los picos, el destello de golpe (golpe.py) y la nota (nota.py)
   y los deja en estado.py para el visualizador;
7. si no está en pausa, arma el paquete de 22 bytes (unos 21 por segundo):
   lo guarda en el estado para el espejo de la OLED y, si hay un Arduino
   conectado, se lo manda por el puerto serie.

Mientras tanto, el bucle principal lee los botones del Arduino unas 100
veces por segundo y aplica cada uno con estado.aplicar_accion(), y dibuja
el visualizador unas 30 veces por segundo.

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
import golpe
import nota
import blynk_cliente
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
# Últimas n muestras de los "lados" del estéreo
memoria_lados = numpy.zeros(n)
# Piso y techo de cada banda, en dB. Se ajustan solos con la música.
piso, techo = bandas.niveles_iniciales()
# Nivel de cada banda (dB) promediado entre bloques. None hasta el primer
# bloque, que lo inicializa con su propio nivel.
db_suave = None
# Altura que se muestra de cada barra, ya suavizada. Empieza vacía.
mostradas = numpy.zeros(configuracion.CANTIDAD_BARRAS)
# Relleno de golpe: las BARRAS_GOLPE suben a ALTURA_MAXIMA con cada golpe y
# bajan con la misma caída que las barras. Va aparte de `mostradas` para
# que el visualizador lo dibuje transparente detrás de la barra real; al
# Arduino se le manda el máximo de los dos.
destello = numpy.zeros(configuracion.CANTIDAD_BARRAS)
# Marca de pico de cada barra (sube con la barra, baja despacio).
picos = numpy.zeros(configuracion.CANTIDAD_BARRAS)
# Momento (time.monotonic()) del último golpe con el efecto activo. None = ninguno.
momento_golpe = None

# --- Envío al Arduino ---
# Momento del último paquete enviado (time.monotonic(), en segundos).
# Empieza en 0 para que el primer bloque ya se pueda enviar.
ultimo_envio = 0
# Cantidad de paquetes enviados.
envios = 0
# Puerto serie abierto con el Arduino. None = no hay Arduino conectado:
# el análisis sigue funcionando, pero no se envía nada.
conexion = None
# True cuando ya se mandó el último paquete con pausa = 1: así, durante la
# pausa, ese paquete sale una sola vez. Vuelve a False al salir de la pausa.
pausa_enviada = False

# --- Visualizador ---
# Momento del último cuadro dibujado (time.monotonic()). Empieza en 0 para
# que el primer cuadro se dibuje enseguida.
ultimo_dibujo = 0

# --- Fuente de audio ---
# Fuente del stream abierto ahora (MODO_MIC o MODO_LINE). None hasta que
# elegir_dispositivo() abre el primero.
fuente_abierta = None

def al_recibir_bloque(bloque, cantidad_muestras, tiempo, aviso):
    """
    Función que llama sounddevice con cada bloque de audio (callback).

    Agrega el bloque a la memoria, analiza las últimas n muestras,
    actualiza la calibración y calcula la altura suavizada de cada barra,
    los picos, el destello de golpe y la nota, y los publica en el estado.
    Arma el paquete como mucho una vez cada INTERVALO_ENVIO (en pausa,
    solo el primero, con pausa = 1) y lo manda si hay Arduino conectado.

    Corre en un hilo aparte (el de sounddevice), no en el bucle principal.
    """
    global ultimo_envio, pausa_enviada, db_suave, momento_golpe

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
    # Lo mismo con los lados del estéreo (si el dispositivo tiene 2 canales o más).
    memoria_lados[:n-m] = memoria_lados[m:]
    if bloque.ndim == 2 and bloque.shape[1] >= 2:
        memoria_lados[-m:] = (bloque[:, 0] - bloque[:, 1]) / 2
    else:
        memoria_lados[-m:] = 0

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

    # Recalibración pedida con la tecla R
    if estado.pedido_recalibrar:
        techo[:] = db_suave + configuracion.RECALIBRAR_MARGEN_DB
        piso[:]  = techo - configuracion.RECALIBRAR_RANGO_DB
        picos[:] = 0
        estado.pedido_recalibrar = False

    # Calibración automática: cada banda ajusta su piso y su techo según
    # lo que está sonando, así se ve bien con música fuerte o suave.
    bandas.actualizar_niveles(piso, techo, db_suave)
    # dB → altura entre 0 (en el piso) y ALTURA_MAXIMA (en el techo).
    alturas = bandas.a_alturas(db_suave, piso, techo)
    caida = configuracion.VELOCIDADES_CAIDA[estado.velocidad]
    # Suavizado: las barras suben enseguida y bajan 'caida' px por bloque.
    bandas.suavizar(mostradas, alturas, caida)
    bandas.actualizar_picos(picos, mostradas)

    ahora = time.monotonic()
    # Golpe: el destello baja con la misma caída que las barras y, si
    # golpe.py detecta uno con el efecto activo, las BARRAS_GOLPE se llenan.
    # La detección usa los dB sin promediar: el promedio achata el bombo.
    bandas.suavizar(destello, numpy.zeros(len(destello)), caida)
    # detectar() va primero en el `and`: así se llama en todos los bloques
    # y golpe.py sigue viendo el audio aunque el efecto esté apagado.
    if golpe.detectar(db, techo, ahora) and estado.golpe:
        destello[configuracion.BARRAS_GOLPE] = configuracion.ALTURA_MAXIMA
        momento_golpe = ahora

    # Nota fundamental (byte 18 del paquete) y, para el afinador, su
    # frecuencia y el desvío en cents.
    numero_nota, frecuencia, cents = nota.estimar(memoria, fs, estado.afinador, memoria_lados)
    # Todo lo que dibuja el visualizador, de una sola vez.
    # Nivel general del bloque (sin calibración), para el medidor de la ventana.
    nivel = bandas.nivel_db(mono)
    estado.publicar_audio(mostradas, destello, picos, numero_nota, frecuencia, cents, momento_golpe, nivel)

    # Se lee una sola vez: el botón la cambia desde otro hilo, y así el
    # `if` y el paquete usan el mismo valor aunque cambie en el medio.
    pausa = estado.pausa
    # Forma de la OLED (byte 21): solo "centro" se dibuja desde el centro;
    # "onda" y "espectrograma" no existen en la OLED y se ven como barras.
    forma_oled = configuracion.FORMA_OLED_CENTRO if estado.forma == "centro" else configuracion.FORMA_OLED_BARRAS
    # Paquete: como mucho uno cada INTERVALO_ENVIO (así no se arma en
    # todos los bloques). Se arma aunque no haya Arduino, para el espejo
    # de la OLED. armar_paquete ya convierte a entero y limita entre 0 y
    # ALTURA_MAXIMA, por eso se le pasan las alturas con decimales.
    if (ahora - ultimo_envio) >= configuracion.INTERVALO_ENVIO:
        if pausa == 0 or not pausa_enviada:
            # Normal: se envía siempre. Recién entrado en pausa: un último
            # paquete (con pausa = 1) para que el Arduino congele la pantalla.
            salida = numpy.maximum(mostradas, destello)
            paquete = serie.armar_paquete(salida, estado.fuente, numero_nota, pausa, estado.pico, forma_oled)
            enviar_paquete(paquete)
            ultimo_envio = ahora
            pausa_enviada = pausa == 1
        # Si no: en pausa y el Arduino ya fue avisado, no se envía nada.


def nombre_dispositivo(fuente):
    """Nombre del dispositivo de configuracion.py que corresponde a la fuente."""
    if fuente == configuracion.MODO_MIC:
        return configuracion.DISPOSITIVO_MICROFONO
    if fuente == configuracion.MODO_LINE:
        return configuracion.DISPOSITIVO_SISTEMA
    raise ValueError(f"Fuente de audio desconocida: {fuente}")


def elegir_dispositivo(fuente):
    """
    La llama capturar_continuo() antes de abrir cada stream: al empezar y
    cada vez que cambia estado.fuente. Devuelve el número del dispositivo.

    Corre en el hilo principal con el stream anterior ya cerrado, así que
    el callback no está usando la memoria ni los niveles: se pueden
    reiniciar sin riesgo.

    Si el dispositivo nuevo no está (por ejemplo, BlackHole sin instalar),
    vuelve a la fuente anterior. Al empezar no hay anterior: da ValueError.
    """
    global fuente_abierta, db_suave
    nombre = nombre_dispositivo(fuente)
    try:
        numero = captura.buscar_dispositivo(nombre)
    except ValueError:
        if fuente_abierta is None or fuente_abierta == fuente:
            raise
        print(f"No encontré '{nombre}': sigo con la fuente anterior")
        # capturar_continuo() ve el cambio y vuelve a llamar con la anterior.
        estado.cambiar("fuente", fuente_abierta, "compu")
        nombre = nombre_dispositivo(fuente_abierta)
        numero = captura.buscar_dispositivo(nombre)
        fuente = fuente_abierta

    # Cambio de fuente (no al empezar): el micrófono y la línea tienen
    # niveles muy distintos, así que se descarta lo de la fuente anterior:
    # el audio de la ventana deslizante, el promedio de dB y la calibración.
    if fuente_abierta is not None and fuente != fuente_abierta:
        memoria[:] = 0
        memoria_lados[:] = 0
        db_suave = None
        estado.pedido_recalibrar = True
    fuente_abierta = fuente
    print(f"Usando dispositivo: {nombre}")
    return numero


def enviar_paquete(paquete):
    """
    Guarda el paquete para el espejo de la OLED y, si hay Arduino, lo
    manda. Si el Arduino se desconecta en el medio, se sigue sin él.
    """
    global conexion, envios
    estado.publicar_paquete(paquete, picos)
    if conexion is None:
        return
    try:
        serie.enviar(conexion, paquete)
        envios += 1
    except OSError:
        print("Se desconectó el Arduino: sigo sin enviar")
        conexion = None
        estado.arduino_conectado = False

def en_cada_vuelta():
    """
    La llama capturar_continuo(): lee los botones del Arduino y dibuja un cuadro cada
    INTERVALO_DIBUJO.
    """
    global ultimo_dibujo
    atender_botones()
    ahora = time.monotonic()
    if (ahora - ultimo_dibujo) >= configuracion.INTERVALO_DIBUJO:
        ultimo_dibujo = ahora
        return visualizador.dibujar()
    return True

def atender_botones():
    """
    Lee un botón del Arduino (si llegó alguno) y lo aplica al estado.

    La llama en_cada_vuelta(). Sin Arduino no hace nada. Si el
    Arduino se desconecta, se sigue sin él.
    """
    global conexion
    if conexion is None:
        return
    try:
        codigo = serie.leer_boton(conexion)
    except OSError:
        print("Se desconectó el Arduino: sigo sin enviar")
        conexion = None
        estado.arduino_conectado = False
        return
    if codigo is not None:
        estado.aplicar_accion(codigo, "Arduino")
        print(f"Botón recibido: {codigo}. Estado nuevo: velocidad={estado.velocidad}, "
              f"pausa={estado.pausa}, pico={estado.pico}, golpe={estado.golpe}")



# Solo se ejecuta con `python pc/principal.py`, no al importar el módulo.
if __name__ == "__main__":
    # Se intenta abrir el puerto del Arduino. Si no está enchufado (o el
    # Monitor Serie del IDE lo tiene ocupado), se sigue sin enviar en vez
    # de cortar el programa.
    try:
        conexion = serie.conectar(configuracion.PUERTO_SERIE)
        estado.arduino_conectado = True
        print("Arduino conectado")
    except serial.SerialException:
        print("No se encontró el Arduino: sigo sin enviar")
        # El visualizador muestra "Arduino: desconectado" y el espejo de la
        # OLED sigue andando con los paquetes que se habrían enviado.

    # Blynk se entera de cada cambio, venga de donde venga.
    if not blynk_cliente.iniciar():
        print("Blynk sin conectar: falta BLYNK_AUTH_TOKEN en el .env")
    estado.suscriptores.append(blynk_cliente.avisar_cambio)

    # Se empieza a medir después de conectar(), para que los paquetes por
    # segundo no incluyan su espera de 2 s. Va antes del `try` para que
    # `inicio` exista aunque se apriete Ctrl+C enseguida.
    inicio = time.monotonic()
    try:
        visualizador.iniciar()
        print("Analizando… (Ctrl+C o cerrar la ventana para salir)")
        # Abre el dispositivo de estado.fuente con elegir_dispositivo() y
        # lo reabre cada vez que cambia. Termina cuando en_cada_vuelta()
        # devuelve False (se cerró la ventana) o con Ctrl+C.
        captura.capturar_continuo(elegir_dispositivo, al_recibir_bloque, en_cada_vuelta)
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