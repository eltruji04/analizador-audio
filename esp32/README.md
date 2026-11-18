# Analizador en ESP32

Traducción a C++ de todo el programa de la compu (`pc/`) y del Arduino (`arduino/analizador_oled`), para que el analizador funcione **solo, sin computadora**:

```
Micrófono I2S ─┐
               ├──► ESP32 ──► OLED 128x32 · 2 LEDs
ADC de línea ──┘      ▲  │
          4 botones ──┘  └──► Blynk (WiFi)
```

> **Estado:** el análisis (bandas, calibración, golpe, tempo, nota y afinador) está probado en la compu y da lo mismo que el Python (ver [Pruebas](#pruebas)). Todo el sketch compila sin warnings con el core **esp32 3.3.12** (placa "ESP32 Dev Module"), con y sin Blynk. **Todavía no se probó en una placa.**

## Qué se tradujo

| Python / Arduino | ESP32 | Cambios |
|---|---|---|
| `pc/configuracion.py` | `configuracion.h` | Mismos valores. Se agregaron los pines. Los dispositivos de audio por nombre se reemplazan por los pines I2S de cada fuente |
| `pc/estado.py` | `estado.h/.cpp` | Forma y color se guardan como índice. Las preferencias van a la flash (NVS) en vez de un JSON |
| `pc/captura.py` + `elegir_dispositivo()` | `captura.h/.cpp` | I2S en vez de sounddevice. Una tarea en el núcleo 1 lee y analiza cada bloque |
| `pc/principal.al_recibir_bloque()` | `analisis.h/.cpp` | Igual, paso por paso. El paquete ya no viaja por USB: lo dibuja `pantalla.cpp` |
| `pc/bandas.py` | `bandas.h/.cpp` | Igual |
| `pc/golpe.py` | `golpe.h/.cpp` | Igual. Sin tempo devuelve `-1` (era `None`) |
| `pc/nota.py` | `nota.h/.cpp` | Igual. La croma reutiliza el espectro de las bandas cuando analiza la mezcla |
| `numpy.fft` | `fft.h/.cpp` | FFT propia: calcula directo la potencia y la autocorrelación, para ahorrar RAM |
| `pc/blynk_cliente.py` | `blynk_cliente.h/.cpp` | Librería Blynk de C++. Se agregó `V8` para la fuente |
| `pc/serie.py` | — | Ya no hace falta: todo pasa adentro del ESP32 |
| `arduino/analizador_oled` (dibujo, LEDs) | `pantalla.h/.cpp` | El mismo dibujo. Si no encuentra la OLED, sigue sin pantalla en vez de colgarse |
| `arduino/analizador_oled` (botones) | `botones.h/.cpp` | Aplica el botón directo con `estado::aplicar_accion()` |
| Teclas de `pc/visualizador.py` | `analizador_esp32.ino` | Las mismas teclas, por el Monitor Serie |
| `pc/visualizador.py`, `dibujo.py`, `colores.py` | — | **No se tradujeron:** el ESP32 no tiene ventana. Color y color fijo se guardan igual, para que la app de Blynk muestre lo mismo |

## Hardware

| Pieza | Para qué |
|---|---|
| ESP32 DevKit (ESP32-WROOM-32) | Todo el programa |
| Micrófono I2S **INMP441** | Fuente `MIC` (mono) |
| ADC estéreo I2S **PCM1808** + jack de 3,5 mm | Fuente `LINE` (estéreo, para los "lados" del modo nota) |
| OLED 128x32 I2C (SSD1306) | La misma de antes |
| 4 pulsadores y 2 LEDs | Los mismos de antes |

Con solo el micrófono ya funciona. Sin el PCM1808, la fuente `LINE` no va a recibir audio.

### Conexiones

Los pines están en `configuracion.h` y se pueden cambiar ahí.

| Señal | GPIO | Nota |
|---|---|---|
| INMP441 SCK / WS / SD | 14 / 27 / 34 | L/R del micrófono a GND (canal izquierdo) |
| PCM1808 SCKI (MCLK) | 0 | En el ESP32 clásico el MCLK solo sale por GPIO 0, 1 o 3 |
| PCM1808 BCK / LRCK / DOUT | 26 / 25 / 35 | FMT a GND (I2S de 24 bits), MD0 y MD1 a GND (modo esclavo) |
| OLED SDA / SCL | 21 / 22 | 3,3 V |
| Botón caída / pausa / pico / golpe | 32 / 33 / 18 / 19 | A GND, sin resistencia (`INPUT_PULLUP`) |
| LED MIC / LED LINE | 4 / 2 | Con su resistencia |

## Cómo cargarlo

1. En el Arduino IDE, **Gestor de placas** → instalar **esp32 de Espressif** (versión 3.x, que trae ESP-IDF 5).
2. **Gestor de librerías** → instalar **Adafruit SSD1306**, **Adafruit GFX** y **Blynk**.
3. Para usar Blynk: copiar `analizador_esp32/secretos.h.ejemplo` como `analizador_esp32/secretos.h` y completar el WiFi y los datos de Blynk. Ese archivo no se sube al repositorio. Sin él, el programa anda igual, pero sin Blynk.
4. Abrir `analizador_esp32/analizador_esp32.ino`, elegir la placa **ESP32 Dev Module** y subir.

## Uso

Los botones y la app de Blynk funcionan igual que antes (`V0`–`V7`, más `V8` para la fuente). Desde el **Monitor Serie** (115200 baudios, "Sin ajuste de línea") se puede hacer lo mismo que con el teclado de la compu:

| Tecla | Acción |
|---|---|
| `espacio` | Pausa |
| `p` / `g` / `a` | Marca de pico / golpe / afinador |
| `f` / `c` / `v` | Forma / color / velocidad de caída |
| `r` | Recalibrar |
| `i` | Fuente `MIC` ↔ `LINE` |
| `t` | Prende o apaga el informe de tiempos |
| `h` | Ayuda |

Cada 5 s el Monitor Serie muestra cuánto tarda el análisis de un bloque, la nota, el tempo y la RAM libre:

```
Análisis: 6.2 ms promedio, 9.8 ms máximo (bloque: 21.3 ms) · 234 bloques · nivel -31 dB · nota A · 120 BPM · Blynk sí · RAM libre 98000
```

(Valores de ejemplo: todavía no hay mediciones reales.) El **máximo** tiene que quedar por debajo de 21,3 ms. Si lo pasa de vez en cuando, el DMA guarda ~43 ms de audio y no se pierde nada. Si lo pasa siempre, se pierde audio. En ese caso, la primera opción es una placa ESP32-S3.

## Pruebas

En la compu, sin placa:

```bash
sh esp32/pruebas/correr_pruebas.sh
```

```bash
.venv/bin/python esp32/pruebas/comparar_con_python.py
```

- `correr_pruebas.sh` compila el análisis dos veces, con `double` y con `float` (como en el ESP32), y corre `pruebas_unidad.cpp`. Son las mismas pruebas de los `__main__` de Python (tonos por banda, `nivel_db`, `promediar`, estado y preferencias, tempo, notas y YIN), más la FFT comparada contra una DFT hecha a mano.
- `comparar_con_python.py` arma una señal estéreo de 13 s (silencio, bombo a 120 BPM, acordes abiertos y al centro, un La para el afinador, ruido y un tramo mono) con cambios de velocidad, forma, pico, afinador, pausa, recalibración y fuente. La pasa por el `principal.al_recibir_bloque()` de verdad y por el C++, y compara bloque a bloque.

Resultado (609 bloques, 294 paquetes):

| Qué | `double` | `float` |
|---|---|---|
| Diferencia máxima en barras, picos y destello | 0 px | 0,001 px |
| Bloques con otra nota / otro tempo | 0 / 0 | 0 / 0 |
| Diferencia máxima en el afinador | 0 cents | 0,0001 cents |
| Bytes de paquete distintos | 0 | 0 |

## Memoria

Compilado para "ESP32 Dev Module":

| | Programa (flash) | Variables globales (RAM) |
|---|---|---|
| Sin Blynk | 366 KB (27 %) | 56 KB (17 %) |
| Con Blynk y WiFi | 1002 KB (76 %) | 81 KB (24 %) |

A las variables globales se suma lo que se reserva al arrancar. Lo que reserva el análisis (en `float`): unos 135 KB entre la FFT (40 KB), las bandas (24 KB), la nota (21 KB), la ventana deslizante (32 KB) y los buffers de I2S (16 KB), más ~16 KB del DMA. Con WiFi, un ESP32-WROOM deja ~150–200 KB libres, así que entra, pero con poco margen. Por eso la FFT calcula directo la potencia y la autocorrelación, sin arreglos intermedios. La RAM libre aparece en el informe del Monitor Serie.

## Sin verificar

- **[SIN VERIFICAR]** Cuánto tarda el análisis en el ESP32 real (en especial con el afinador, que hace dos FFT de 8192).
- **[SIN VERIFICAR]** El orden izquierdo/derecho del INMP441 en el ESP32 clásico (si no llega audio, probar `canal = 1` en `PINES_MIC`).
- **[SIN VERIFICAR]** El PCM1808 con MCLK por GPIO 0 (es un pin de arranque: si la placa no arranca con el PCM1808 conectado, desconectarlo para subir el programa).

