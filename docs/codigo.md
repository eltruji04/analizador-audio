# Funcionamiento del código

Explica cómo está organizado el código, qué hacen las funciones más importantes y por qué están hechas así. Para el diseño general, ver [diseno.md](diseno.md); para el formato de los mensajes con el Arduino, [protocolo_serie.md](protocolo_serie.md).

> Los puntos marcados **[SIN VERIFICAR]** todavía no se probaron, y los marcados **[A CONFIRMAR]** son decisiones pendientes.

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
- [Cómo agregar cosas](#cómo-agregar-cosas)

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
| `captura.py` | Busca el dispositivo de audio por nombre y captura de forma continua |
| `bandas.py` | Matemática del análisis: FFT por bandas, calibración, alturas, suavizado y picos |
| `golpe.py` | Detecta golpes del bombo |
| `nota.py` | Estima la nota (pendiente) |
| `estado.py` | Estado del sistema (modos) y últimos resultados del audio. Única forma de cambiar un modo |
| `serie.py` | Arma el paquete para el Arduino y lee los botones |
| `visualizador.py` | Ventana: eventos, teclas y orden de dibujo |
| `dibujo.py` | Una función por zona de la ventana |
| `colores.py` | Paleta de la interfaz y color de cada banda |
| `blynk_cliente.py` | Conexión con Blynk (pendiente) |
| `configuracion.py` | Todas las constantes |

---

## Los dos hilos

El programa corre en **dos hilos** al mismo tiempo:

| Hilo | Quién lo maneja | Qué hace | Frecuencia |
|---|---|---|---|
| **De audio** | `sounddevice` | Llama a `principal.al_recibir_bloque` con cada bloque: análisis, golpe, nota y envío al Arduino | ~47 veces/s (un bloque cada ~21 ms) |
| **Principal** | `captura.capturar_continuo` | Llama a `principal.en_cada_vuelta`: lee los botones y dibuja la ventana | ~100 vueltas/s; dibuja ~30 cuadros/s |

**Por qué dos hilos:** el audio no puede esperar. Si el análisis se hiciera en el mismo bucle que la ventana, un cuadro lento haría perder audio. Y al revés, en macOS la ventana **solo** se puede manejar desde el hilo principal, así que no puede ir en el callback.

**Cómo se pasan los datos sin mezclarse:**

- El hilo de audio escribe los resultados con `estado.publicar_audio()`, que **reemplaza el diccionario `estado.audio` entero** con copias de los arreglos.
- El hilo principal lee `datos = estado.audio` **una sola vez** por cuadro.
- Como el reemplazo es de un solo paso, la ventana nunca ve la mitad de un bloque y la mitad del siguiente.
- Los modos (`estado.pausa`, `estado.forma`…) los cambia el hilo principal y los lee el de audio. Por eso `al_recibir_bloque` lee `estado.pausa` **una sola vez** en una variable local: así el `if` y el paquete usan el mismo valor aunque el botón lo cambie en el medio.

---

## Recorrido de un bloque de audio

```
sounddevice ──► bloque (1024 muestras, estéreo)
                  │ a_mono
                  ▼
                memoria (últimas 4096 muestras)
                  │ calcular_bandas  (Hann + FFT + suma por banda)
                  ▼
                energías ──► dB ──┬──────────────► golpe.detectar ──► destello
                                  │ promediar
                                  ▼
                               db_suave
                                  │ actualizar_niveles (piso/techo)
                                  │ a_alturas
                                  ▼
                               alturas 0–32
                                  │ suavizar (caída) · actualizar_picos
                                  ▼
                               mostradas, picos
                                  │
            nota.estimar(memoria) │
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

Todo lo que tiene que durar de un bloque al siguiente (`memoria`, `piso`, `techo`, `db_suave`, `mostradas`, `destello`, `picos`, `conexion`…) se crea **una sola vez** a nivel de módulo, fuera de las funciones. Las funciones lo modifican "por dentro" (con `[:]` o `global`).

| Función | Qué hace |
|---|---|
| `al_recibir_bloque(bloque, cantidad_muestras, tiempo, aviso)` | El callback de audio. Hace todo el recorrido de arriba para un bloque |
| `enviar_paquete(paquete)` | Guarda el paquete para el espejo de la OLED y, si hay Arduino, lo manda. Si falla, sigue sin Arduino |
| `en_cada_vuelta()` | La llama el hilo principal: atiende los botones y, cada `INTERVALO_DIBUJO`, dibuja un cuadro. Devuelve `False` si se cerró la ventana |
| `atender_botones()` | Lee un código de botón (si llegó) y lo aplica con `estado.aplicar_accion(codigo, "Arduino")` |
| Bloque `__main__` | Conecta el Arduino (o sigue sin él), inicia Blynk, busca el dispositivo de audio, abre la ventana y arranca la captura. El `finally` cierra todo y muestra los paquetes por segundo |

**Lógica de `al_recibir_bloque`, en pseudocódigo:**

```
mono = a_mono(bloque)
correr memoria hacia la izquierda y poner mono al final
energias = calcular_bandas(memoria)
db = 10·log10(energias + 1e-12)              # silencio = −120 dB
db_suave = promedio(db_suave, db)

si se pidió recalibrar:
    techo = db_suave + margen;  piso = techo − rango;  picos = 0

actualizar_niveles(piso, techo, db_suave)
alturas = a_alturas(db_suave, piso, techo)
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
        paquete = armar_paquete(máx(mostradas, destello), fuente, nota, pausa, pico, forma_oled)
        enviar_paquete(paquete)
        pausa_enviada = (pausa == 1)
```

**Cuidado:** `golpe.detectar()` va **antes** del `and` (`golpe.detectar(...) and estado.golpe`). Así se llama en todos los bloques y el detector sigue viendo el audio aunque el efecto esté apagado; si fuera al revés, al prender el efecto compararía contra un bloque viejo.

**Desconexión del Arduino:** cualquier `OSError` al escribir o leer el puerto pone `conexion = None` y `estado.arduino_conectado = False`. Desde ahí el programa sigue igual, pero sin enviar. Los paquetes se siguen armando para el espejo de la OLED.

### captura.py

| Función | Qué hace |
|---|---|
| `buscar_dispositivo(texto)` | Devuelve el número del primer dispositivo **de entrada** cuyo nombre contiene `texto`. Busca por nombre porque los números cambian al conectar o desconectar algo |
| `capturar_continuo(numero, procesar_bloque, en_cada_vuelta)` | Abre un `sounddevice.InputStream` con `procesar_bloque` como callback y, mientras está abierto, llama a `en_cada_vuelta` cada ~10 ms. Termina cuando esa función devuelve `False` o con Ctrl+C |
| `grabar`, `nivel_rms` | Solo para pruebas |

### bandas.py

Toda la matemática del análisis. Las funciones que actualizan arreglos los modifican **por dentro** (`arreglo[:] = …`) para que el cambio se conserve en `principal.py`.

| Función | Qué hace |
|---|---|
| `a_mono(audio)` | Promedia los canales si el audio es estéreo |
| `preparar_analisis(n, fs)` | Se llama **una vez**. Calcula la ventana de Hann y, para cada banda, una máscara de `True`/`False` con los valores del espectro que le tocan |
| `calcular_bandas(muestras, ventana, mascaras)` | `rfft` de las muestras con la ventana, eleva al cuadrado (potencia) y suma la potencia de cada máscara. Devuelve 16 energías |
| `promediar(db_suave, db)` | `db_suave = 0,7·db_suave + 0,3·db`. Calma el ruido de los graves, que se calculan con solo 2 valores del espectro |
| `niveles_iniciales()` | Techo en `TECHO_INICIAL_DB` y piso `RANGO_MAXIMO_DB` más abajo |
| `actualizar_niveles(piso, techo, db)` | Calibración automática (ver abajo) |
| `a_alturas(db, piso, techo)` | `(db − piso) / (techo − piso) · 32`, limitado a 0–32 |
| `suavizar(mostradas, alturas, caida)` | `mostradas = máx(alturas, mostradas − caida)`: sube enseguida, baja como mucho `caida` por bloque |
| `actualizar_picos(picos, mostradas)` | `picos = máx(mostradas, picos − CAIDA_PICO)` |

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
| `detectar(db, techo, ahora)` | Devuelve `True` si en este bloque hubo un golpe |

```
subida = db[graves] − anterior[graves]
cerca  = db[graves] > techo[graves] − 15 dB
anterior = db                                  # SIEMPRE, antes de cualquier return

si pasaron menos de 0,15 s del último golpe → False
si algún grave subió > 6 dB y está cerca de su techo → golpe
```

- Usa los dB **sin promediar**: el promedio le quita unos 6 dB al bombo y no se detectaría.
- `anterior` se actualiza siempre, aun durante la espera. Si no, al terminar la espera compararía contra un bloque viejo.
- Los valores están **[SIN VERIFICAR]** con golpes reales.

### nota.py

| Función | Qué hace |
|---|---|
| `estimar(muestras, fs)` | Tiene que devolver `(nota, frecuencia, cents)`. **Hoy siempre devuelve `(SIN_NOTA, None, None)`** |

Todo el resto ya está conectado: la nota va en el byte 18, el visualizador dibuja la tarjeta de nota, el color por nota y el afinador. Para implementarla alcanza con completar esta función.

### estado.py

Guarda dos cosas:

1. **Estado del sistema:** `velocidad`, `pausa`, `pico`, `golpe`, `afinador`, `forma`, `color`, `color_fijo`, `fuente`, las conexiones y `ultimo_cambio`.
2. **Últimos resultados:** `audio` (alturas, destello, picos, nota, frecuencia, cents, momento del golpe) y `ultimo_paquete` con sus `picos_enviados`.

| Función | Qué hace |
|---|---|
| `cambiar(campo, valor, origen)` | **Única forma de cambiar un modo.** Comprueba que el campo y el valor estén en `VALORES` (si no, `ValueError`), lo guarda, anota `ultimo_cambio` con su origen y avisa a cada función de `suscriptores` |
| `alternar(campo, origen)` | 0 → 1 → 0 (pausa, pico, golpe, afinador) |
| `siguiente(campo, origen)` | Pasa al valor siguiente de la lista y vuelve al primero (velocidad, forma, color) |
| `aplicar_accion(codigo, origen)` | Traduce un código de botón (1 a 4) en `siguiente("velocidad")` o `alternar(...)`. La usan el Arduino y Blynk |
| `pedir_recalibracion(origen)` | Levanta `pedido_recalibrar`; el callback de audio lo atiende en el próximo bloque |
| `publicar_audio(...)` | Reemplaza `audio` entero con copias (ver [Los dos hilos](#los-dos-hilos)) |
| `publicar_paquete(paquete, picos)` | Guarda el último paquete para el espejo de la OLED |

**Cuidado:** usar siempre `import estado` y leer `estado.pausa`. Con `from estado import pausa` se copia el valor al importar y después no se ven los cambios.

### serie.py

| Función | Qué hace |
|---|---|
| `conectar(puerto)` | Abre el puerto y espera 2 s, porque el Uno se reinicia al abrirlo. Si no está, da `SerialException` |
| `armar_paquete(alturas, modo, nota, pausa, pico, forma_oled)` | Arma los 22 bytes. Las alturas se convierten a entero y se limitan a 0–32 (son mediciones); el resto, si está fuera de rango, da `ValueError` (es un error del programa). Así ningún dato puede valer 255 |
| `enviar(conexion, paquete)` | `conexion.write(paquete)` |
| `leer_boton(conexion)` | Si hay un byte esperando (`in_waiting`), lo lee y lo devuelve; si no, devuelve `None` sin quedarse esperando |

### visualizador.py, dibujo.py y colores.py

**`visualizador.py`** maneja la ventana:

| Función | Qué hace |
|---|---|
| `iniciar()` | Abre la ventana de 1280×840 y carga las fuentes |
| `atender_eventos()` | Lee clics y teclas. Un clic se compara con `dibujo.botones` (los rectángulos del cuadro anterior); una tecla se busca en `TECLAS`. Devuelve `False` al cerrar |
| `dibujar()` | Atiende los eventos, toma `estado.audio` una vez, agrega un cuadro al historial del espectrograma cada ~47 ms y llama a cada zona de `dibujo.py`. Al final, `pygame.display.flip()` |
| `simular(...)` | Solo para `python pc/visualizador.py`: inventa barras, golpes y notas para probar la ventana sin audio |

**`dibujo.py`** tiene una función por zona (`encabezado`, `espectro`, `espejo_oled`, `tarjeta_nota`, `panel`, `pie`) y una por forma (`barras`, `onda`, `espectrograma`). Solo dibujan: leen el estado y los datos que les pasan. Los botones del panel se anotan en `dibujo.botones` como `(rectángulo, función)` mientras se dibujan, y se borran al empezar cada cuadro.

- `dibujar_oled(oled, paquete, picos)` reproduce la OLED **a partir del paquete**, no de los datos internos. Así lo que se ve en el espejo es exactamente lo que recibe el Arduino.
- El destello de golpe se dibuja en una capa transparente detrás de la barra, para que se siga viendo el nivel real.

**`colores.py`**: `color_banda(banda, modo, color_fijo, nota)` devuelve el color de una banda según el modo (fijo, arcoíris o nota; sin nota, el fijo). `MAPA_ESPECTROGRAMA` es una tabla de 256 colores de intensidad.

### blynk_cliente.py

Esqueleto vacío: `iniciar()` devuelve `False` y `avisar_cambio(campo, valor, origen)` no hace nada. Está enganchado como suscriptor de `estado`, así que al implementarlo recibe todos los cambios. Ver [diseno.md → App en Blynk](diseno.md#app-en-blynk).

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

Como el 255 reinicia la cuenta, si se pierde un byte el Arduino se vuelve a sincronizar con el próximo paquete. Hoy lee 20 bytes y no el 21 (forma): ver [protocolo_serie.md → Estado del firmware](protocolo_serie.md#estado-del-firmware).

---

## Decisiones de diseño del código

| Decisión | Por qué |
|---|---|
| Ventana deslizante de 4096 muestras sobre bloques de 1024 | Con 1024 la FFT separa cada 47 Hz y las bandas graves quedan vacías; con 4096 baja a 11,7 Hz, y como se analiza en cada bloque se sigue actualizando cada 21 ms |
| La compu es la única dueña del estado | Si el Arduino o Blynk cambiaran modos por su cuenta, habría dos versiones del estado que se desincronizan |
| Los botones mandan "qué se apretó", no el valor nuevo | El Arduino no necesita saber el estado; la compu decide |
| El paquete se arma aunque no haya Arduino | El espejo de la OLED funciona igual y sirve para probar sin hardware |
| El 255 solo puede ser el inicio | El Arduino lo usa para encontrar el comienzo y resincronizarse |
| La detección de golpe usa dB sin promediar | El promedio achata el bombo (~6 dB) |
| El destello va en un arreglo aparte de las barras | El visualizador lo dibuja transparente detrás; al Arduino se le manda el máximo de los dos |
| Constantes en `configuracion.py` | Un solo lugar para ajustar; los módulos no tienen números sueltos |
| Cada módulo tiene su prueba en `if __name__ == "__main__"` | Se puede probar una parte sin el resto ni hardware |

---

## Cómo agregar cosas

**Un modo nuevo en el estado** (por ejemplo, brillo):

1. Agregar la variable en `estado.py` y sus valores permitidos en `VALORES`.
2. Si tiene un texto especial para el encabezado, agregarlo en `describir()`.
3. Cambiarlo siempre con `estado.cambiar()`; agregar el botón en `dibujo.panel()` y, si hace falta, una tecla en `visualizador.TECLAS`.
4. Si lo tiene que saber el Arduino, ver el punto siguiente.

**Un byte nuevo en el paquete:**

1. Actualizar [protocolo_serie.md](protocolo_serie.md).
2. Agregar el parámetro y su comprobación en `serie.armar_paquete()`, y sus pruebas en el `__main__` de `serie.py`.
3. Pasar el valor desde `principal.al_recibir_bloque` y desde `visualizador.py` (prueba simulada).
4. Leerlo en `dibujo.dibujar_oled` si cambia lo que se ve.
5. En el firmware: agrandar `datos[]` y cambiar la cuenta en `procesarByte`. **Los dos lados tienen que cambiar a la vez.**

**La nota:** completar `nota.estimar()`. Pendiente de medir: con 11,7 Hz por valor del espectro, en G3 (196 Hz) un valor vale unos 100 cents; para el afinador hace falta interpolar el pico o una ventana más larga **[A CONFIRMAR: método]**.

**Blynk:** completar `blynk_cliente.iniciar()` (conectar y poner `estado.blynk_conectado`) y `avisar_cambio()` (mandar el valor salvo que `origen == "Blynk"`). Lo que llegue de la app se aplica con `estado.aplicar_accion(codigo, "Blynk")` o `estado.cambiar(campo, valor, "Blynk")`.
