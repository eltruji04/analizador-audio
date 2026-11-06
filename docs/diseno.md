# Diseño del sistema

Documento de referencia del diseño acordado. Para instalar y usar el programa, ver el [README](../README.md) y la [guía de instalación](instalacion.md); para el detalle de las funciones, [Funcionamiento del código](codigo.md).

> Los puntos marcados **[SIN VERIFICAR]** todavía no se probaron, y los marcados **[A CONFIRMAR]** son decisiones pendientes.

## Contenido

- [Arquitectura](#arquitectura)
- [Hardware](#hardware)
- [Modos de visualización](#modos-de-visualización)
- [App en Blynk](#app-en-blynk)
- [Visualizador en pantalla](#visualizador-en-pantalla)
- [Procesamiento de audio](#procesamiento-de-audio)

---

## Arquitectura

```
Música ──► Computadora (Python)
           captura de audio · FFT por bandas · detección de golpe ·
           estimación de nota · visualizador en pantalla · cliente de Blynk
                │   USB (puerto serie, en los dos sentidos)
                ▼
           Arduino Uno
           OLED 128x32 I2C ·
           4 pulsadores · 2 LEDs indicadores
```

- **Computadora:** hace todo el procesamiento de audio, dibuja el visualizador y se conecta a Blynk. Le manda al Arduino un paquete con las alturas de las barras, la fuente de audio, la nota, la pausa, la marca de pico y la forma ([protocolo_serie.md](protocolo_serie.md)).
- **Arduino Uno:** dibuja la OLED, enciende los LEDs y lee los botones. Por cada botón apretado le manda a la computadora un byte con su código; no cambia nada por su cuenta.
- **Blynk:** se conecta **desde la computadora**, no desde la placa, con la librería `blynk-library-python` (`BlynkLib`) contra `blynk.cloud`, en un hilo propio. Necesita internet; sin conexión, el resto del programa sigue igual.

### Estado compartido

La computadora es la **única dueña del estado** (velocidad de caída, pausa, pico, golpe, afinador, forma, color, color fijo y fuente de audio), que vive en [`pc/estado.py`](../pc/estado.py). La ventana, los botones del Arduino y Blynk solo **piden** cambios, siempre con `estado.cambiar()` (o `estado.aplicar_accion()` para los códigos de botón). Así nunca hay dos versiones del modo actual.

Cada cambio queda anotado con su origen (`compu`, `Arduino` o `Blynk`), se muestra en el encabezado del visualizador y se avisa a los suscriptores (ahí se engancha Blynk). El cambio llega a la OLED con el próximo paquete.

### Hilos

- **Hilo de audio** (callback de `sounddevice`): analiza cada bloque, publica los resultados en `estado.audio` y manda el paquete al Arduino.
- **Hilo principal:** lee los botones del Arduino (~100 veces por segundo) y dibuja el visualizador (~30 cuadros por segundo). En macOS la ventana solo se puede manejar desde este hilo. También es el que cierra y vuelve a abrir la captura cuando cambia la fuente.
- **Hilo de Blynk** ([`blynk_cliente.py`](../pc/blynk_cliente.py)): mantiene la conexión con la app, manda los cambios de la compu y aplica los que llegan de la app. Si se corta, reintenta cada 5 s.

### Entrada de audio

| Modo | Fuente |
|---|---|
| Micrófono (`MIC`) | El micrófono de la computadora |
| Línea (`LINE`) | El audio que reproduce la propia computadora. En macOS se captura con BlackHole; en Linux, con la fuente "monitor" de PulseAudio/PipeWire **[SIN VERIFICAR]** |

El programa arranca con la fuente de `FUENTE_AUDIO` en `configuracion.py` y se puede cambiar **en vivo** con la tecla `I` o los botones `MIC` | `LINE` del panel. Siempre se elige entre los dos dispositivos de `configuracion.py` (`DISPOSITIVO_MICROFONO` y `DISPOSITIVO_SISTEMA`), no un dispositivo cualquiera. La fuente actual se informa al Arduino en el byte 17 del paquete.

Al cambiarla, el programa cierra la captura y abre el otro dispositivo (el audio se corta unos 0,15–0,2 s). Además descarta lo que quedaba de la fuente anterior (la ventana deslizante y el promedio de dB) y recalibra, porque el micrófono y la línea tienen niveles muy distintos. Si el dispositivo nuevo no está, vuelve a la fuente anterior.

Si el Arduino no está conectado al iniciar, o se desconecta en el medio, el programa sigue funcionando sin enviar.

---

## Hardware

### Pantalla

**OLED 128x32 I2C (SSD1306)**, dirección `0x3C`, en A4/A5 y 5 V, con el bus I2C a 400 kHz.

| Zona | Contenido |
|---|---|
| Izquierda (x 1–96) | 16 barras de 5 px de ancho con 1 px de separación |
| Línea vertical (x 99) | Separa las barras del texto |
| Derecha arriba | Fuente activa: `MIC` o `LINE` |
| Derecha abajo | Nota en letra grande (`C`…`B`, o `-` sin nota) |

- Las barras se dibujan en **16 segmentos de 2 px**: el Arduino divide por 2 las alturas del paquete (0–32).
- La **marca de pico** la calcula el propio Arduino: sube con la barra y baja 1 segmento cada 3 paquetes.
- En **pausa** dibuja un círculo con el símbolo de pausa sobre las barras y deja de recibir paquetes, así que la pantalla queda congelada.
- Antes del primer paquete muestra una pantalla de espera con `-` en lugar de la fuente y la nota.

### Controles físicos (caja de control)

| Control | Pin | Función |
|---|---|---|
| Pulsador 1 | 11 | Velocidad de caída: lenta → normal → rápida |
| Pulsador 2 | 10 | Pausa |
| Pulsador 3 | 9 | Marca de pico |
| Pulsador 4 | 6 | Efecto de golpe |
| LED micrófono | 4 | Encendido cuando la fuente es el micrófono |
| LED sistema | 2 | Encendido cuando la fuente es el audio de la computadora |

- Los pulsadores usan `INPUT_PULLUP` (apretado = `LOW`) con antirrebote por software de 50 ms. Mandan su código una sola vez por cada vez que se aprietan.
- Los **LEDs** se alternan según el byte 17 del paquete: siempre hay uno solo encendido. **Todavía no están en el firmware.**
- Los pines 0 y 1 los usa el USB y A4/A5 la OLED.

---

## Modos de visualización

La **forma** y el **color** se eligen por separado y se combinan libremente.

| Forma | En la computadora | En la OLED |
|---|---|---|
| Barras | Cada barra sube y baja según el volumen de su banda | Igual |
| Desde el centro | La barra crece desde el centro hacia arriba y hacia abajo | Igual |
| Onda | Una línea que une los topes de las bandas, con relleno suave abajo y un punto por banda | Barras |
| Espectrograma | Historial de los últimos ~3 s: tiempo en horizontal (lo más nuevo a la derecha), bandas en vertical (agudos arriba) e intensidad como color. Sin marca de pico ni modo de color | Barras |

La computadora le avisa al Arduino la forma en el byte 21 del paquete: solo distingue barras desde el piso y desde el centro ([protocolo_serie.md](protocolo_serie.md#forma-en-la-oled-byte-21)).

| Color | Descripción |
|---|---|
| Fijo | Uno de los 5 colores de `COLORES_FIJOS` (celeste, verde, naranja, rosa, violeta), elegido en el panel del visualizador |
| Arcoíris | Un tono distinto por banda, de rojo (graves) a violeta (agudos) |
| Por nota ("modo armónico") | Todas las barras toman el color de la nota predominante (12 tonos repartidos en el círculo de colores); sin nota, el color fijo. Necesita `nota.py`, que **todavía no está implementado**. |

El color solo existe en la computadora: la OLED es monocromática. En espectrograma el color representa la intensidad.

**Opciones** (funcionan con cualquier modo):

- **Velocidad de caída:** cuántos píxeles por bloque bajan las barras (lenta, normal o rápida). Siempre suben enseguida.
- **Marca de pico:** queda marcado el punto más alto que alcanzó cada barra y baja despacio. En "desde el centro" se marcan dos líneas, arriba y abajo.
- **Golpe:** detecta la pegada del bombo en las bandas graves (40–90 Hz) y en cada golpe llena las barras 1, 2, 15 y 16, que después bajan con la misma caída. En la computadora el relleno se ve transparente detrás de la barra real y se encienden dos tiras a los costados; a la OLED se le manda la mayor de las dos alturas.
- **Afinador** (solo en la computadora): la tarjeta de nota muestra la octava, la frecuencia y el desvío en cents (verde dentro de ±5 cents). Depende de `nota.py`.
- **Pausa:** deja de mandarle paquetes al Arduino; la computadora sigue analizando y dibujando.

---

## App en Blynk

La conexión está en [`pc/blynk_cliente.py`](../pc/blynk_cliente.py):

- `principal.py` llama a `blynk_cliente.iniciar()` al arrancar, que arranca el hilo de Blynk (si no hay token, devuelve `False` y el programa sigue sin Blynk).
- Al conectarse le manda a la app el estado completo: la compu es la dueña y la app tiene que mostrar lo que hay ahora.
- `estado.py` llama a `blynk_cliente.avisar_cambio()` después de cada cambio, para que la app muestre el estado actual (salvo que el cambio haya venido de Blynk). El valor queda en una cola y lo manda el hilo de Blynk, que es el único que usa la conexión.
- Cuando el usuario toca algo en la app, el módulo llama a `estado.cambiar(campo, valor, "Blynk")`.

Cada campo va en un pin virtual: `V0` velocidad, `V1` pausa, `V2` pico, `V3` golpe, `V4` afinador, `V5` forma, `V6` color y `V7` color fijo. La forma y el color viajan como índice de su lista (`FORMAS` y `MODOS_COLOR`).

Contenido previsto:

- **Controles:** pausa, marca de pico, golpe, velocidad de caída, afinador, forma, color y color fijo (hechos). La fuente de audio todavía no tiene pin.
- **Tablero de registro de uso** (pauta mínima).
- **Opcional:** guardar conjuntos de efectos.

### Token de Blynk

El token es una clave privada y **nunca se sube al repositorio**. Cada integrante lo guarda en un archivo `.env` en la raíz del proyecto (ya incluido en `.gitignore`), con una línea `BLYNK_AUTH_TOKEN=<token>`. `blynk_cliente.py` lo lee con `python-dotenv` (`load_dotenv()`).

---

## Visualizador en pantalla

Es parte del producto, no solo una herramienta de prueba. Es una ventana de **1280×840** hecha con **pygame-ce** que se dibuja unas 30 veces por segundo. [`visualizador.py`](../pc/visualizador.py) atiende el teclado y el mouse y [`dibujo.py`](../pc/dibujo.py) dibuja cada zona:

| Zona | Contenido |
|---|---|
| Encabezado | Título, rango de frecuencias, último cambio con su origen, conexión con el Arduino y Blynk, y fuente activa |
| Espectro | Las 16 bandas en la forma y el color elegidos, con altura continua (no en escalones), etiquetas de frecuencia y tiras de golpe a los costados |
| Espejo de la OLED | Réplica de lo que muestra la OLED, dibujada a partir del **mismo paquete** que se manda al Arduino, con sus bytes debajo. Funciona aunque no haya Arduino |
| Nota / afinador | La nota grande con la tira de 12 notas o, con el afinador activo, el afinador |
| Panel de control | Fuente (`MIC` \| `LINE`), velocidad de caída, pausa, pico, golpe, afinador, forma, color, muestras de color fijo y atajos de teclado |
| Pie | Cuadros por segundo reales |

Los clics y las teclas cambian el estado con `estado.cambiar(..., "compu")`, la misma función que usan los botones y Blynk. Las teclas están en el [README](../README.md#uso).

Como las reglas de cada modo quedan escritas dos veces (C++ en el Arduino y Python en el espejo de la OLED), cualquier cambio en cómo dibuja la OLED hay que hacerlo en los dos lados.

---

## Procesamiento de audio

Cada vez que llega un bloque de audio (1024 muestras a 48 kHz, unos 21 ms), `principal.al_recibir_bloque`:

1. **Pasa a mono** promediando los canales (BlackHole es estéreo).
2. **Ventana deslizante:** agrega el bloque a una memoria con las últimas 4096 muestras (unos 85 ms). Con solo 1024 muestras, la FFT separa frecuencias cada 47 Hz y las bandas graves quedarían vacías; con 4096 la separación baja a 11,7 Hz y se sigue actualizando con cada bloque.
3. **FFT por bandas:** aplica una ventana de Hann, calcula el espectro y suma la energía de las 16 bandas, entre 40 Hz y 20 kHz, repartidas en escala logarítmica.
4. **Decibeles:** pasa cada energía a dB (el silencio da −120 dB).
5. **Promedio entre bloques:** mezcla los dB nuevos con los anteriores (`PROMEDIO_DB` = 0,7) para que el ruido de los graves no salte de un bloque al otro.
6. **Recalibración** (solo si se apretó `R` o se cambió la fuente): pone el techo de cada banda `RECALIBRAR_MARGEN_DB` por encima de lo que suena y el piso `RECALIBRAR_RANGO_DB` por debajo del techo, y borra los picos.
7. **Calibración automática:** cada banda tiene un piso y un techo que se ajustan solos con la música. El techo sube enseguida y baja muy despacio; el piso se mueve despacio en las dos direcciones, así el ruido de fondo queda por debajo. La distancia entre los dos queda entre 12 y 50 dB, y ningún techo queda a más de 35 dB del más alto.
8. **Alturas:** convierte los dB en una altura entre 0 (en el piso) y 32 (en el techo).
9. **Suavizado y picos:** las barras suben enseguida y bajan según la velocidad de caída elegida; la marca de pico baja más despacio (`CAIDA_PICO`).
10. **Golpe:** [`golpe.py`](../pc/golpe.py) mira los dB **sin promediar** (el promedio achata el bombo) de las bandas 1 y 2. Hay golpe si alguna sube más de 6 dB respecto del bloque anterior y queda a menos de 15 dB de su techo, con una espera de 0,15 s entre golpes. Con el efecto activo, llena las `BARRAS_GOLPE`.
11. **Nota:** [`nota.py`](../pc/nota.py) estima la nota, su frecuencia y el desvío en cents. **Todavía no está implementado**: siempre devuelve "sin nota". Pendiente: con 11,7 Hz por valor del espectro no alcanza la precisión para el afinador en los graves; hace falta interpolar el pico o una ventana más larga.
12. **Publicación:** deja las alturas, el destello, los picos y la nota en `estado.audio` para el visualizador.
13. **Envío:** como mucho una vez cada `INTERVALO_ENVIO` (1/30 s) arma el paquete, lo guarda para el espejo de la OLED y, si hay Arduino, se lo manda. En pausa manda un último paquete y después nada.

El formato de los datos que se mandan al Arduino está en [protocolo_serie.md](protocolo_serie.md).
