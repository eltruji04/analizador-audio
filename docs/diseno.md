# Diseño del sistema

Documento de referencia del diseño acordado. Para instalar y usar el programa, ver el [README](../README.md).

> Los puntos marcados **[SIN VERIFICAR]** todavía no se probaron, y los marcados **[A CONFIRMAR]** son decisiones pendientes.

## Contenido

- [El proyecto](#el-proyecto)
- [Arquitectura](#arquitectura)
- [Hardware](#hardware)
- [Modos de visualización](#modos-de-visualización)
- [App en Blynk](#app-en-blynk)
- [Visualizador en pantalla](#visualizador-en-pantalla)
- [Procesamiento de audio](#procesamiento-de-audio)
- [Decisiones de diseño](#decisiones-de-diseño)
- [Calendario](#calendario)
- [Riesgos y pendientes](#riesgos-y-pendientes)

---

## El proyecto

Categoría *Audio* del proyecto final. El objetivo general:

> Desarrollar un sistema basado en Arduino Uno que, a partir del análisis en tiempo real de la música realizado en una computadora, la traduzca en patrones de luz, con varios modos de visualización seleccionables desde una aplicación que respondan a distintas características del sonido, como el volumen por banda de frecuencia o la nota o tonalidad predominante.

---

## Arquitectura

```
Música ──► Computadora (Python)
           captura de audio · FFT por bandas · detección de golpe ·
           estimación de nota · visualizador en pantalla · cliente de Blynk
                │   USB (puerto serie, en los dos sentidos)
                ▼
           Arduino Uno
           Oled 128x32 I2C ·
           4 pulsadores · 2 LEDs indicadores
```

- **Computadora:** hace todo el procesamiento de audio y se conecta a Blynk. Le manda al Arduino las alturas de las barras, la fuente de audio activa y la nota.
- **Arduino Uno:** actualiza el Oled y los indicadores, y lee los botones. Le devuelve a la computadora los cambios hechos con los controles físicos **[A CONFIRMAR: formato de ese mensaje]**.
- **Blynk:** se conecta **desde la computadora**, no desde la placa, usando su API HTTP **[SIN VERIFICAR: que permita leer y escribir los valores de la app desde Python, y qué incluye el plan gratuito]**. Necesita internet.
- **Sincronización:** un cambio hecho desde los botones o la app tiene que actualizar todo el sistema.

### Entrada de audio

| Modo | Fuente |
|---|---|
| Micrófono | El micrófono de la computadora |
| Línea | El audio que reproduce la propia computadora (referencia: Apple Music en ALAC, sin pérdida). En macOS se captura con BlackHole; en Linux, con la fuente "monitor" de PulseAudio/PipeWire **[SIN VERIFICAR]** |


---

## Hardware

### Pantalla

**Oled 128x32 I2C**, en A4/A5 y 5 V. Muestra las bandas de audio, la conexion activa (linea o microfono) y y la nota.

### Controles físicos (caja de control)

| Control | Función |
|---|---|
| Pulsador 1 | Modo de forma |
| Pulsador 2 | Pausar Arduino |
| Pulsador 3 | Marca de pico |
| Pulsador 4 | Modo golpe |
| 2 LEDs indicadores | Fuente de audio activa: micrófono o computadora |

Los pulsadores usan `INPUT_PULLUP` (apretado = `LOW`) con filtro de rebote por software. Los pines 0 y 1 los usa el USB y A4/A5 la Oled **[A CONFIRMAR: asignación del resto de los pines]**.

---

## Modos de visualización

La **forma** y el **color** se eligen por separado y se combinan libremente.

| Forma | Descripción |
|---|---|
| Barras verticales | Cada torre sube y baja según el volumen de su banda |
| Desde el centro | La luz sale del centro de la torre hacia arriba y hacia abajo |

| Color | Descripción |
|---|---|
| Fijo | Un color elegido en la app |
| Arcoíris | Colores aleatorios o en degradé |
| Por nota ("modo armónico") | El color depende de una estimación de la nota predominante, con respuesta lenta para ignorar notas rápidas. Es la parte de mayor riesgo del proyecto **[A CONFIRMAR: correspondencia nota → color]** |

**Opciones** (funcionan con cualquier modo):

- **Marca de pico:** queda marcado el punto más alto que alcanzó cada barra.
- **Modo golpe:** detecta la pegada del bombo en las bandas graves y en cada golpe enciende todos los LEDs de las torres 1, 2, 7 y 8 (solo esas, para limitar el consumo).

---

## App en Blynk

- **Controles:** encendido, brillo, modo de forma, modo de color, color fijo, marca de pico, modo golpe y fuente de audio.
- **Tablero de registro de uso** (pauta mínima de la cátedra) **[A CONFIRMAR: contenido]**.
- **Opcional:** guardar conjuntos de efectos.

### Token de Blynk

El token es una clave privada y **nunca se sube al repositorio**, aunque sea privado: queda en el historial de Git. Cada integrante lo guarda en un archivo `.env` en la raíz del proyecto (ya incluido en `.gitignore`) **[A CONFIRMAR: formato del archivo y cómo se lee desde Python, cuando se programe `blynk_cliente.py`]**.

---

## Visualizador en pantalla

Es parte del producto, no solo una herramienta de prueba. Muestra en la computadora un analizador de espectro que reproduce lo mismo que la Oled, con **altura continua** en vez de escalones, y respeta los mismos modos (forma, color, pico, golpe, brillo, encendido). Además muestra el estado: modos, fuente de audio, brillo, opciones activas y conexión con el Arduino y Blynk.

Como las reglas de cada modo quedan escritas dos veces (C++ en el Arduino y Python en la pantalla), conviene tener un documento común entre las dos partes. **[SIN VERIFICAR]** Qué librería de dibujo en Python rinde mejor a 30–60 cuadros por segundo.

---

## Procesamiento de audio

Cada vez que llega un bloque de audio (1024 muestras a 48 kHz, unos 21 ms), `principal.py`:

1. **Pasa a mono** promediando los canales (BlackHole es estéreo).
2. **Ventana deslizante:** agrega el bloque a una memoria con las últimas 4096 muestras (unos 85 ms). Con solo 1024 muestras, la FFT separa frecuencias cada 47 Hz y las bandas graves quedarían vacías; con 4096 la separación baja a 11,7 Hz y se sigue actualizando con cada bloque.
3. **FFT por bandas:** aplica una ventana de Hann, calcula el espectro y suma la energía de las 16 bandas, entre 40 Hz y 20 kHz, repartidas en escala logarítmica.
4. **Decibeles:** pasa cada energía a dB (el silencio da −120 dB).
5. **Calibración automática:** cada banda tiene un piso y un techo que se ajustan solos con la música (el techo sube enseguida y baja despacio; el piso al revés). Así las barras se ven bien con música fuerte o suave.
6. **Alturas:** convierte los dB en una altura entre 0 (en el piso) y 32 (en el techo).
7. **Suavizado:** las barras suben enseguida y bajan de a `CAIDA_BARRAS` por bloque, para que no parpadeen.
8. **Envío:** si hay Arduino, le manda un paquete como mucho una vez cada `INTERVALO_ENVIO`.

El formato de los datos que se mandan al Arduino está en [protocolo_serie.md](protocolo_serie.md).

---


## Calendario

| Fecha | Entrega |
|---|---|
| 13/10 | Revisión del marco de proyecto |
| **03/11** | **Hito 1:** diseño completo, materiales comprados y la cadena completa funcionando con una torre (audio → FFT → puerto serie → 8 LEDs) |
| **17/11** | **Hito 2:** las 8 torres armadas, todos los modos, controles físicos, LCD y app de Blynk |
| **24/11** | **Informe técnico y código final:** sistema integrado y probado |
| 07/12 | Entrega de la presentación |
| 08/12 | Presentación y demostración final |
| 14/12 | Entrega del video final |
| 15/12 | Devolución de materiales no usados |

---

## Riesgos y pendientes

**Riesgos técnicos**

1. **Modo por nota:** es la parte más difícil; conviene tener una versión simplificada como plan B.
2. **Blynk desde Python:** falta confirmar la API HTTP y los límites del plan gratuito.
3. **Micrófono de la computadora:** puede captar poco en los extremos del espectro; probarlo con tonos.
4. **Retardo entre sonido y luz:** medirlo en las pruebas finales.

**Decisiones pendientes**

- Mensajes del Arduino a la computadora (cambios hechos con los controles físicos).
- Correspondencia entre notas y colores.
