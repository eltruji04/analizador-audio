# Funcionamiento del código

Explica cómo está organizado el código, qué hacen las funciones más importantes y por qué están hechas así. Para el diseño general, ver [diseno.md](diseno.md); para el formato de los mensajes con el Arduino, [protocolo_serie.md](protocolo_serie.md).

## Contenido

- [Mapa de módulos](#mapa-de-módulos)
- [Los dos hilos](#los-dos-hilos)
- [Recorrido de un bloque de audio](#recorrido-de-un-bloque-de-audio)
- [Módulos de la computadora](#módulos-de-la-computadora)
  - [principal.py](#principalpy)
  - [captura.py](#capturapy)
  - [bandas.py](#bandaspy)
  - [golpe.py](#golpepy)
  - [nota.py](#notapy)
  - [estado.py](#estadopy)
  - [serie.py](#seriepy)
  - [visualizador.py, dibujo.py y colores.py](#visualizadorpy-dibujopy-y-colorespy)
  - [blynk_cliente.py](#blynk_clientepy)
  - [configuracion.py](#configuracionpy)
- [Firmware del Arduino](#firmware-del-arduino)
- [Decisiones de diseño del código](#decisiones-de-diseño-del-código)

---

## Mapa de módulos

```
                               principal.py
                                     │
        ┌───────────┬───────────┬────┴────┬──────────┬─────────────┐
        ▼           ▼           ▼         ▼          ▼             ▼
   captura.py   bandas.py   golpe.py   nota.py   serie.py   visualizador.py
                                                                   │
                                                                   ▼
                                                        dibujo.py · colores.py

   estado.py ◄── lo usan todos: estado del sistema y últimos resultados
   configuracion.py ◄── constantes que leen todos
   blynk_cliente.py ◄── se suscribe a los cambios de estado.py
```

| Módulo | Responsabilidad |
|---|---|
| `principal.py` | Punto de entrada. Une todo: abre el Arduino, arranca la captura y procesa cada bloque |
| `captura.py` | Busca el dispositivo de audio por nombre y captura de forma continua; reabre la captura cuando cambia la fuente |
| `bandas.py` | Matemática del análisis: FFT por bandas, calibración, alturas, suavizado y picos |
| `golpe.py` | Detecta golpes del bombo |
| `nota.py` | Estima la nota (pendiente) |
| `estado.py` | Estado del sistema (modos) y últimos resultados del audio. Única forma de cambiar un modo |
| `serie.py` | Busca el puerto del Arduino, arma el paquete y lee los botones |
| `visualizador.py` | Ventana: eventos, teclas y orden de dibujo |
| `dibujo.py` | Una función por zona de la ventana |
| `colores.py` | Paleta de la interfaz y color de cada banda |
| `blynk_cliente.py` | Conexión con Blynk, en un hilo propio |
| `configuracion.py` | Todas las constantes |

---

## Los dos hilos

El programa corre en **dos hilos** al mismo tiempo, más dos aparte: el de Blynk y el que vigila el Arduino:

| Hilo | Quién lo maneja | Qué hace | Frecuencia |
|---|---|---|---|
| **De audio** | `sounddevice` | Llama a `principal.al_recibir_bloque` con cada bloque: análisis, golpe, nota y envío al Arduino | ~47 veces/s (un bloque cada ~21 ms) |
| **Principal** | `captura.capturar_continuo` | Llama a `principal.en_cada_vuelta`: lee los botones y dibuja la ventana. Si cambió `estado.fuente`, cierra la captura y la vuelve a abrir con el otro dispositivo | ~100 vueltas/s; dibuja ~30 cuadros/s |
| **De Blynk** | `blynk_cliente.bucle` | Manda a la app los cambios que quedaron en la cola y aplica los que llegan de la app; si se corta, reconecta | Escucha a Blynk hasta 50 ms por vuelta |
| **Vigilante del Arduino** | `principal.vigilar_arduino` | Mientras `conexion` es `None`, busca el puerto y lo abre. Va en un hilo propio porque `conectar()` espera 2 s | Un intento cada `INTERVALO_BUSQUEDA` (1 s) |

**Por qué dos hilos:** el audio no puede esperar. Si el análisis se hiciera en el mismo bucle que la ventana, un cuadro lento haría perder audio. Y al revés, en macOS la ventana **solo** se puede manejar desde el hilo principal, así que no puede ir en el callback.

**Cómo se pasan los datos sin mezclarse:**

- El hilo de audio escribe los resultados con `estado.publicar_audio()`, que **reemplaza el diccionario `estado.audio` entero** con copias de los arreglos.
- El hilo principal lee `datos = estado.audio` **una sola vez** por cuadro.
- Como el reemplazo es de un solo paso, la ventana nunca ve la mitad de un bloque y la mitad del siguiente.
- La captura solo se cierra y se abre desde el hilo principal. `principal.elegir_dispositivo` reinicia la memoria, el promedio y la calibración justo antes de abrir la nueva, cuando la anterior ya está cerrada: así el callback no los está usando.
- `conexion` la publica el vigilante **recién después** de los 2 s de `conectar()`, en un solo paso. Así los otros hilos nunca le escriben a un Uno que todavía está arrancando: ven `None` o una conexión lista.
- Los modos (`estado.pausa`, `estado.forma`…) los cambia el hilo principal (o el de Blynk) y los lee el de audio. Por eso `al_recibir_bloque` lee `estado.pausa` **una sola vez** en una variable local: así el `if` y el paquete usan el mismo valor aunque el botón lo cambie en el medio.

---

## Recorrido de un bloque de audio

```
sounddevice ──► bloque (1024 muestras, estéreo)
                  │ a_mono                     │ (izquierdo − derecho) / 2
                  ▼                            ▼
                memoria (últimas 4096)     memoria_lados (últimas 4096)
                  │ calcular_bandas  (Hann + FFT + suma por banda)
                  ▼
                energías ──► dB ──┬──────────────► golpe.detectar ──► destello
                                  │ promediar (dos veces)
                                  ▼
                 db_suave (parejo) ──► actualizar_niveles (piso/techo)
                 db_barras (sin promedio al subir)
                                  │ a_alturas (con ese piso y techo)
                                  ▼
                               alturas 0–32
                                  │ suavizar (caída) · actualizar_picos
                                  ▼
                               mostradas, picos
                                  │
     nota.estimar(memoria,        │
                  memoria_lados)  │
                  ▼               ▼
            estado.publicar_audio ──► visualizador (hilo principal)
                                  │
                                  │ cada 1/30 s, si no está en pausa
                                  ▼
                 serie.armar_paquete(máx(mostradas, destello), …)
                                  │ enviar_paquete
                                  ▼
                 estado.publicar_paquete (espejo OLED) + Arduino
```

---

## Módulos de la computadora

### principal.py

Todo lo que tiene que durar de un bloque al siguiente (`memoria`, `memoria_lados`, `piso`, `techo`, `db_suave`, `mostradas`, `destello`, `picos`, `conexion`, `fuente_abierta`…) se crea **una sola vez** a nivel de módulo, fuera de las funciones. Las funciones lo modifican "por dentro" (con `[:]` o `global`).

| Función | Qué hace |
|---|---|
| `al_recibir_bloque(bloque, cantidad_muestras, tiempo, aviso)` | El callback de audio. Hace todo el recorrido de arriba para un bloque |
| `nombre_dispositivo(fuente)` | Devuelve `DISPOSITIVO_MICROFONO` o `DISPOSITIVO_SISTEMA` según la fuente; otra fuente da `ValueError` |
| `elegir_dispositivo(fuente)` | La llama `capturar_continuo` antes de abrir cada captura (al empezar y en cada cambio de fuente) y devuelve el número del dispositivo. En un cambio pone la memoria en ceros, `db_suave = None` y pide recalibrar. Si el dispositivo nuevo no está, vuelve `estado.fuente` a la anterior; al empezar no hay anterior y da `ValueError` |
| `vigilar_arduino()` | Corre en su propio hilo todo el programa. Mientras no hay Arduino, cada `INTERVALO_BUSQUEDA` busca el puerto con `serie.buscar_puerto()` y lo abre. Al conectar pone `pausa_enviada = False` y recién después publica `conexion` |
| `perder_arduino()` | La llaman `enviar_paquete` y `atender_botones` cuando falla el puerto: pone `conexion = None`, `estado.arduino_conectado = False` y cierra el puerto viejo |
| `enviar_paquete(paquete)` | Guarda el paquete para el espejo de la OLED y, si hay Arduino, lo manda. Si falla, llama a `perder_arduino()` |
| `en_cada_vuelta()` | La llama el hilo principal: atiende los botones y, cada `INTERVALO_DIBUJO`, dibuja un cuadro. Devuelve `False` si se cerró la ventana |
| `atender_botones()` | Lee un código de botón (si llegó) y lo aplica con `estado.aplicar_accion(codigo, "Arduino")` |
| Bloque `__main__` | Arranca el hilo `vigilar_arduino`, inicia Blynk, abre la ventana y arranca la captura con `elegir_dispositivo`. El `finally` cierra todo y muestra los paquetes por segundo |

**Lógica de `al_recibir_bloque`, en pseudocódigo:**

```
mono = a_mono(bloque)
correr memoria hacia la izquierda y poner mono al final
energias = calcular_bandas(memoria)
db = 10·log10(energias + 1e-12)              # silencio = −120 dB
db_suave  = promedio(db_suave, db, 0,7 al subir, 0,7 al bajar)   # calibración
db_barras = promedio(db_barras, db, 0 al subir, 0,7 al bajar)     # barras

si se pidió recalibrar:
    techo = db_suave + margen;  piso = techo − rango;  picos = 0

actualizar_niveles(piso, techo, db_suave)
alturas = a_alturas(db_barras, piso, techo)
suavizar(mostradas, alturas, caída elegida)
actualizar_picos(picos, mostradas)

suavizar(destello, ceros, caída)             # el destello baja como las barras
si golpe.detectar(db, techo) y efecto golpe activo:
    destello[barras de golpe] = 32

nota = nota.estimar(memoria)
estado.publicar_audio(...)

pausa = estado.pausa                         # se lee una sola vez
si pasó INTERVALO_ENVIO:
    si no está en pausa, o es el primer paquete de la pausa:
        paquete = armar_paquete(máx(mostradas, destello), estado.fuente, nota, pausa, pico, forma_oled)
        enviar_paquete(paquete)
        pausa_enviada = (pausa == 1)
```

**Cuidado:** `golpe.detectar()` va **antes** del `and` (`golpe.detectar(...) and estado.golpe`). Así se llama en todos los bloques y el detector sigue viendo el audio aunque el efecto esté apagado; si fuera al revés, al prender el efecto compararía contra un bloque viejo.

**Desconexión y reconexión del Arduino:** cualquier `OSError` al escribir o leer el puerto llama a `perder_arduino()`, que pone `conexion = None` y `estado.arduino_conectado = False`. Desde ahí el programa sigue igual, pero sin enviar (los paquetes se siguen armando para el espejo de la OLED), y `vigilar_arduino` lo vuelve a buscar. Al enchufarlo, en el mismo puerto USB o en otro, se conecta solo unos 3 s después: hasta 1 s hasta el próximo intento y 2 s de espera de `conectar()`. Lo mismo pasa si el programa arranca sin Arduino.

**Cuidado:** al abrir el puerto, el Uno se reinicia y se olvida de la pausa. Por eso `vigilar_arduino` pone `pausa_enviada = False` antes de publicar la conexión: así, si estaba en pausa, el primer paquete vuelve a ser el de pausa y la OLED queda congelada en vez de en cero.

### captura.py

| Función | Qué hace |
|---|---|
| `buscar_dispositivo(texto)` | Devuelve el número del primer dispositivo **de entrada** cuyo nombre contiene `texto`. Busca por nombre porque los números cambian al conectar o desconectar algo |
| `capturar_continuo(elegir_dispositivo, procesar_bloque, en_cada_vuelta)` | Le pide a `elegir_dispositivo(estado.fuente)` el número del dispositivo, abre un `sounddevice.InputStream` con `procesar_bloque` como callback y, mientras está abierto, llama a `en_cada_vuelta` cada ~10 ms. Si `estado.fuente` cambia, sale del `with` (se cierra la captura) y abre la de la fuente nueva (unos 0,15–0,2 s sin audio). Termina con `return` cuando `en_cada_vuelta` devuelve `False`, o con Ctrl+C |
| `grabar`, `nivel_rms` | Solo para pruebas |

### bandas.py

Toda la matemática del análisis. Las funciones que actualizan arreglos los modifican **por dentro** (`arreglo[:] = …`) para que el cambio se conserve en `principal.py`.

| Función | Qué hace |
|---|---|
| `a_mono(audio)` | Promedia los canales si el audio es estéreo |
| `preparar_analisis(n, fs)` | Se llama **una vez**. Calcula la ventana de Hann y, para cada banda, una máscara de `True`/`False` con los valores del espectro que le tocan |
| `calcular_bandas(muestras, ventana, mascaras)` | `rfft` de las muestras con la ventana, eleva al cuadrado (potencia) y suma la potencia de cada máscara. Devuelve 16 energías |
| `promediar(db_suave, db, subida, bajada)` | `db_suave = p·db_suave + (1 − p)·db`, con `p = subida` en las bandas que suben y `p = bajada` en las que bajan. Calma el ruido de los graves, que se calculan con solo 2 valores del espectro. Se usa parejo (0,7 y 0,7) para la calibración y sin promedio al subir (0 y 0,7) para las barras: así un aumento brusco se ve en ~64 ms y el ruido no empuja el techo |
| `niveles_iniciales()` | Techo en `TECHO_INICIAL_DB` y piso `RANGO_MAXIMO_DB` más abajo |
| `actualizar_niveles(piso, techo, db)` | Calibración automática (ver abajo) |
| `a_alturas(db, piso, techo)` | `(db − piso) / (techo − piso) · 32`, limitado a 0–32 |
| `suavizar(mostradas, alturas, caida)` | `mostradas = máx(alturas, mostradas − caida)`: sube enseguida, baja como mucho `caida` por bloque |
| `actualizar_picos(picos, mostradas)` | `picos = máx(mostradas, picos − CAIDA_PICO)` |
| `nivel_db(muestras)` | Nivel del bloque en dBFS (valor eficaz, sin calibración): 0 = ±1 todo el tiempo, −6 = mitad de amplitud, silencio = −240. Lo usa el medidor de nivel |

**Calibración automática (`actualizar_niveles`)**, por banda:

```
techo:  si db > techo → techo = db              (sube enseguida)
        si no         → techo −= 0,005 dB       (baja casi nada)
        techo ≥ −70 dB                          (protege del silencio)
        techo ≥ techo_más_alto − 35 dB          (una banda casi vacía no se "estira")

piso:   si db < piso → piso −= 0,02 dB          (baja despacio)
        si no        → piso += 0,1 dB           (sube despacio)

12 dB ≤ techo − piso ≤ 50 dB
```

Por qué así: si el piso siguiera enseguida cada pozo del ruido, el ruido de fondo se vería como barras que tiemblan. Moviéndose despacio, el ruido queda por debajo del piso y las barras quedan quietas en silencio.

**Por qué `suavizar` usa `máx` y no "bajar siempre `caida`":** con una nota que se apaga despacio, la barra quedaría por debajo de la altura real y en el bloque siguiente volvería a saltar: parpadearía.

### golpe.py

| Función | Qué hace |
|---|---|
| `detectar(db, techo, ahora)` | Devuelve `True` si en este bloque hubo un golpe, y anota su momento en `momentos` |
| `estimar_bpm(momentos, ahora)` | Tempo entero entre `BPM_MINIMO` y `BPM_MAXIMO`, o `None`: mediana baja (un intervalo de verdad) de los intervalos de los últimos `BPM_VENTANA` s, promedio de los que quedan a menos de `BPM_TOLERANCIA` de ella, y doblar o dividir por 2 |

```
subida = db[graves] − anterior[graves]
cerca  = db[graves] > techo[graves] − 15 dB
anterior = db                                  # SIEMPRE, antes de cualquier return

si pasaron menos de 0,15 s del último golpe → False
si algún grave subió > 6 dB y está cerca de su techo → golpe
```

- Usa los dB **sin promediar**: el promedio le quita unos 6 dB al bombo y no se detectaría.
- `anterior` se actualiza siempre, aun durante la espera. Si no, al terminar la espera compararía contra un bloque viejo.

### nota.py

| Función | Qué hace |
|---|---|
| `estimar(muestras, fs, afinador, lados=None)` | La llama `principal` en cada bloque. Devuelve `(nota, frecuencia, cents)`: nota 0–11 o `SIN_NOTA`; frecuencia y cents solo con el afinador (si no, `None`). Aplica la puerta de volumen y elige el método según `afinador` |
| `detectar_frecuencia(muestras, fs)` | Método YIN: devuelve `(frecuencia, claridad)`, o `(None, claridad)` si la onda no se repite con claridad o está fuera de `NOTA_FRECUENCIA_MINIMA`–`_MAXIMA`. La usa el afinador |
| `a_nota(frecuencia)` | Hz → `(nota 0–11, cents de −50 a +50)`, con `LA_REFERENCIA` = 440 Hz |
| `croma(muestras)` | Energía (potencia) del espectro entre `CROMA_FRECUENCIA_MINIMA` y `_MAXIMA`, sumada en las 12 notas |
| `perfil_armonicos(nota)` | Croma que deja una nota con sus 6 primeros armónicos; con esto se arman las 24 `plantillas` al importar |
| `puntajes_raiz(croma)` | Parecido (0–1) de la croma con un acorde de cada raíz (el mejor entre mayor y menor) |

Lo que dura entre bloques vive en variables del módulo que cambia `estimar()` con `global`: `croma_suave`, `nota_actual`, `bloques_plana`, `candidata`, `bloques_candidata` y `frecuencia_suave`. En silencio se reinician todas. Las constantes están en la sección `# --- Notas ---` de `configuracion.py`; cada una dice cómo se midió.

Las pruebas (`python pc/nota.py`) generan tonos, acordes de guitarra, ruido y voz sintéticos, y comprueban cada función y el modo nota en vivo (bloque a bloque).

### estado.py

Guarda dos cosas:

1. **Estado del sistema:** `velocidad`, `pausa`, `pico`, `golpe`, `afinador`, `forma`, `color`, `color_fijo`, `fuente`, las conexiones y `ultimo_cambio`.
2. **Últimos resultados:** `audio` (alturas, destello, picos, nota, frecuencia, cents, momento del golpe, nivel en dBFS y BPM) y `ultimo_paquete` con sus `picos_enviados`.

| Función | Qué hace |
|---|---|
| `cambiar(campo, valor, origen)` | **Única forma de cambiar un modo.** Comprueba que el campo y el valor estén en `VALORES` (si no, `ValueError`), lo guarda, anota `ultimo_cambio` con su origen y avisa a cada función de `suscriptores` |
| `alternar(campo, origen)` | 0 → 1 → 0 (pausa, pico, golpe, afinador y fuente: `MODO_MIC` = 0, `MODO_LINE` = 1) |
| `siguiente(campo, origen)` | Pasa al valor siguiente de la lista y vuelve al primero (velocidad, forma, color) |
| `aplicar_accion(codigo, origen)` | Traduce un código de botón (1 a 4) en `siguiente("velocidad")` o `alternar(...)`. La usan los botones del Arduino |
| `pedir_recalibracion(origen)` | Levanta `pedido_recalibrar`; el callback de audio lo atiende en el próximo bloque |
| `guardar_preferencias()` | La llama `cambiar()` cuando cambia uno de `CAMPOS_GUARDADOS`: escribe un `.tmp` y lo pone en lugar de `ARCHIVO_PREFERENCIAS`, con un candado porque los cambios llegan de varios hilos |
| `cargar_preferencias()` | Al arrancar (en `principal.py` y en la prueba de `visualizador.py`): aplica los campos válidos del archivo sin avisar a los suscriptores; ignora con un aviso los inválidos o un archivo roto |
| `publicar_audio(...)` | Reemplaza `audio` entero con copias (ver [Los dos hilos](#los-dos-hilos)) |
| `publicar_paquete(paquete, picos)` | Guarda el último paquete para el espejo de la OLED |

**Cuidado:** usar siempre `import estado` y leer `estado.pausa`. Con `from estado import pausa` se copia el valor al importar y después no se ven los cambios.

### serie.py

| Función | Qué hace |
|---|---|
| `buscar_puerto()` | Recorre `list_ports.comports()` y devuelve el `device` del primero cuyo VID:PID sea `VID_ARDUINO`:`PID_ARDUINO`. Si no hay ninguno, devuelve `PUERTO_SERIE` como plan B |
| `conectar(puerto)` | Abre el puerto y espera 2 s, porque el Uno se reinicia al abrirlo. Si no está, da `SerialException` |
| `armar_paquete(alturas, modo, nota, pausa, pico, forma_oled)` | Arma los 22 bytes. Las alturas se convierten a entero y se limitan a 0–32 (son mediciones); el resto, si está fuera de rango, da `ValueError` (es un error del programa). Así ningún dato puede valer 255 |
| `enviar(conexion, paquete)` | `conexion.write(paquete)` |
| `leer_boton(conexion)` | Si hay un byte esperando (`in_waiting`), lo lee y lo devuelve; si no, devuelve `None` sin quedarse esperando |

### visualizador.py, dibujo.py y colores.py

**`visualizador.py`** maneja la ventana:

| Función | Qué hace |
|---|---|
| `iniciar()` | Abre la ventana de 1280×840 (con `pygame.SCALED`, para poder pasar a pantalla completa sin cambiar el dibujo) y carga las fuentes |
| `alternar_pantalla_completa()` | Tecla `Z` (o `Esc` para salir): pone la ventana a pantalla completa y cambia `pantalla_completa`, que hace que `dibujar()` muestre solo el espectro en `dibujo.ESPECTRO_COMPLETO`. Es de la ventana, no del estado del sistema |
| `atender_eventos()` | Lee clics y teclas. Un clic se compara con `dibujo.botones` (los rectángulos del cuadro anterior); una tecla se busca en `TECLAS`. Devuelve `False` al cerrar |
| `dibujar()` | Atiende los eventos, toma `estado.audio` una vez, agrega un cuadro al historial del espectrograma cada ~47 ms y llama a cada zona de `dibujo.py`. Al final, `pygame.display.flip()` |
| `simular(...)` | Solo para `python pc/visualizador.py`: inventa barras, golpes y notas para probar la ventana sin audio |

**`dibujo.py`** tiene una función por zona (`encabezado`, `espectro`, `espejo_oled`, `tarjeta_nota`, `panel`, `pie`) y una por forma (`barras`, `onda`, `espectrograma`). `onda` dibuja la curva que arma `suavizar(alturas, pasos)`: una interpolación cúbica monótona (Fritsch–Carlson) con `PASOS_ONDA` puntos entre cada par de bandas, que pasa por cada tope y nunca sale del rango de las dos bandas vecinas. El relleno se dibuja opaco y `degradar_relleno` le baja la transparencia columna por columna (de la curva al piso); el brillo va en otra capa (`capa(..., "brillo")`) para no pisar ese degradado. Con el peak activo, `pico_curva` dibuja otra curva con `suavizar` sobre los picos (con `aalines`, para que no se vea escalonada), sin bajar nunca de la onda. `barras` dibuja en tres capas (halo, destello y cuerpo) y `degradar_barras` oscurece cada barra hacia su base. Barras y onda dejan abajo `ALTO_REFLEJO` del área para `reflejo`, que copia la parte de abajo del dibujo dada vuelta y cada vez más transparente. `fundido` guarda una foto del espectro en cada cuadro y, si cambió la forma, la desvanece encima de la nueva. `medidor_nivel` dibuja el vúmetro junto al título, y `intensidad_golpe` (1 → 0) la usan las tiras y el pulso del fondo. En el panel, `animar(clave, objetivo)` lleva cada botón hacia su aspecto de mouse encima o activo. `espectro(..., zona)` recibe la tarjeta donde dibujar (la normal o la de pantalla completa) y pasa los colores por `acercar_colores`, que los lleva al color nuevo en `TRANSICION_COLOR` segundos con un acercamiento exponencial (igual con cualquier FPS). Solo dibujan: leen el estado y los datos que les pasan. Los botones del panel se anotan en `dibujo.botones` como `(rectángulo, función)` mientras se dibujan, y se borran al empezar cada cuadro.

- `dibujar_oled(oled, paquete, picos)` reproduce la OLED **a partir del paquete**, no de los datos internos. Así lo que se ve en el espejo es exactamente lo que recibe el Arduino.
- El destello de golpe se dibuja en una capa transparente detrás de la barra, para que se siga viendo el nivel real. En la forma onda no se dibuja: solo se encienden las tiras de los costados.

**`colores.py`**: `color_banda(banda, modo, color_fijo, nota)` devuelve el color de una banda según el modo (fijo, arcoíris o nota; sin nota, el fijo). `MAPA_ESPECTROGRAMA` es una tabla de 256 colores de intensidad.

### blynk_cliente.py

Usa `BlynkLib` y lee el token `BLYNK_AUTH_TOKEN` del `.env`. `iniciar()` arranca el hilo `bucle()` (o devuelve `False` si no hay token). Ese hilo conecta con `blynk.cloud`, registra un handler por pin de `PINES` y, en cada vuelta, manda lo que quedó en la cola `pendientes` y escucha a Blynk; si se corta, espera `ESPERA_RECONEXION` (5 s) y reconecta. `al_conectar()` encola el estado completo, `al_recibir()` convierte el valor de la app (índice para forma y color) y llama a `estado.cambiar(..., "Blynk")`, y `avisar_cambio()` (suscriptor de `estado`) encola cada cambio que no vino de Blynk. Los campos que no están en `PINES`, como `fuente`, se ignoran. Ver [diseno.md → App en Blynk](diseno.md#app-en-blynk).

### configuracion.py

Solo constantes, agrupadas por tema (captura, bandas, puerto serie, paquete, calibración, caída, botones, picos, notas, visualizador y golpe). Ningún módulo debería tener números sueltos que dependan de estas decisiones. La tabla de los parámetros está en [instalacion.md → Configuración](instalacion.md#configuración).

---

## Firmware del Arduino

[`botones_oled.ino`](../arduino/botones_oled/botones_oled.ino):

| Función | Qué hace |
|---|---|
| `setup()` | Abre el serie a 115200, configura los botones con `INPUT_PULLUP`, inicia la OLED en `0x3C` con I2C a 400 kHz y muestra la pantalla de espera |
| `loop()` | Revisa los botones, lee todos los bytes que llegaron con `procesarByte` y, si se completó un paquete, redibuja |
| `procesarByte(b)` | Máquina de estados del paquete (ver abajo). Devuelve `true` cuando se completó uno |
| `dibujarPantalla()` | Dibuja las 16 barras en segmentos de 2 px, la marca de pico, el símbolo de pausa, `MIC`/`LINE` y la nota |
| `revisarBotones()` | Antirrebote de 50 ms; cuando un botón pasa a apretado (`LOW`), manda su código con `Serial.write` |
| `pantallaInicial()`, `CIRCULO()` | Pantalla de espera y símbolo de pausa |

**`procesarByte`:**

```
si b == 255 → empezar paquete nuevo (datonum = 0, leyendo = true)
si no estoy leyendo → ignorar
guardar b en datos[datonum]; datonum++
si todavía no llegaron 20 → seguir esperando
paquete completo:
    niveles = datos[0..15] / 2       # 0–32 → 0–16 segmentos
    modo, nota, pausa, pico = datos[16..19]
    actualizar alturaPico (sube con la barra, baja 1 cada 3 paquetes)
    leyendo = false
```

Como el 255 reinicia la cuenta, si se pierde un byte el Arduino se vuelve a sincronizar con el próximo paquete. Hoy lee 20 bytes y no el 21 (forma), así que siempre dibuja barras desde el piso: leer la forma está pendiente en el firmware (ver [Forma en la OLED](protocolo_serie.md#forma-en-la-oled-byte-21)).

---

## Decisiones de diseño del código

| Decisión | Por qué |
|---|---|
| Ventana deslizante de 4096 muestras sobre bloques de 1024 | Con 1024 la FFT separa cada 47 Hz y las bandas graves quedan vacías; con 4096 baja a 11,7 Hz, y como se analiza en cada bloque se sigue actualizando cada 21 ms |
| La compu es la única dueña del estado | Si el Arduino o Blynk cambiaran modos por su cuenta, habría dos versiones del estado que se desincronizan |
| Los botones mandan "qué se apretó", no el valor nuevo | El Arduino no necesita saber el estado; la compu decide |
| El Arduino se busca por VID:PID y no por nombre de puerto | El nombre (`/dev/cu.usbmodem…`) cambia según el USB donde se enchufa; el VID:PID es del chip y no cambia |
| El paquete se arma aunque no haya Arduino | El espejo de la OLED funciona igual y sirve para probar sin hardware |
| El 255 solo puede ser el inicio | El Arduino lo usa para encontrar el comienzo y resincronizarse |
| La detección de golpe usa dB sin promediar | El promedio achata el bombo (~6 dB) |
| El destello va en un arreglo aparte de las barras | El visualizador lo dibuja transparente detrás; al Arduino se le manda el máximo de los dos |
| Constantes en `configuracion.py` | Un solo lugar para ajustar; los módulos no tienen números sueltos |
| Cada módulo tiene su prueba en `if __name__ == "__main__"` | Se puede probar una parte sin el resto ni hardware |
