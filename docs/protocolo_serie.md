# Protocolo serie

Comunicación por USB entre la computadora (`pc/serie.py`) y el Arduino Uno. **Si se cambia este formato, hay que cambiar a la vez `pc/serie.py` y el código del Arduino.**

## Computadora → Arduino

115200 baudios. Cada paquete tiene **22 bytes**:

| Byte | Contenido | Valores |
|---|---|---|
| 0 | Inicio de paquete | `255` |
| 1 – 16 | Altura de cada barra, de la banda más grave a la más aguda | `0` a `32` |
| 17 | Fuente de audio | `0` = micrófono (`MIC`), `1` = audio del sistema (`LINE`) |
| 18 | Nota | `0` a `11`; `12` = sin nota |
| 19 | Pausa | `0` = normal, `1` = en pausa |
| 20 | Pico | `0` = sin marca de pico, `1` = dibujar la marca de pico |
| 21 | Forma en la OLED | `0` = barras desde el piso, `1` = barras desde el centro |

Como ningún otro byte puede valer 255, el Arduino lo usa para encontrar el comienzo de cada paquete. `armar_paquete` lo garantiza: limita las alturas a `0`–`32` y da error si la fuente, la nota, la pausa, el pico o la forma están fuera de rango.

Ejemplo (salida de `python pc/serie.py`):

```
255  0 31 32 32 4 5 6 7 8 9 10 11 12 13 14 15  0  12  0  1  0
```

Inicio, las 16 alturas (la prueba manda a propósito −2, 34 y 300, que se corrigen a 0 y 32), micrófono, sin nota, sin pausa, con pico (el valor inicial de `estado.pico`) y forma barras.

### Frecuencia de envío

Como mucho un paquete cada `INTERVALO_ENVIO` (1/30 s). Medido con el Uno real: unos 21 paquetes por segundo. Cada paquete reemplaza al anterior.

### Pausa

Al entrar en pausa, la compu manda **un último paquete con pausa = 1** y después no manda nada más hasta salir de la pausa. El Arduino dibuja el símbolo de pausa sobre las barras y la pantalla queda congelada. Que no lleguen paquetes durante la pausa es lo esperado.

### Fuente de audio (byte 17)

La OLED muestra `MIC` o `LINE` según este byte, y los dos LEDs de la caja de control se alternan con él: siempre hay uno solo encendido. La compu arranca con `FUENTE_AUDIO` (en `configuracion.py`) y la fuente se puede cambiar con el programa andando (tecla `I` o panel): el byte cambia desde el paquete siguiente.

### Marca de pico (byte 20)

El byte solo dice si se dibuja la marca. La altura de cada marca la calcula el propio Arduino a partir de las alturas que recibe: sube con la barra y baja 1 segmento cada 3 paquetes. El espejo de la OLED en el visualizador usa los picos de la compu, así que puede diferir un poco del Arduino.

### Forma en la OLED (byte 21)

La compu tiene cuatro formas (`barras`, `centro`, `onda` y `espectrograma`), pero la OLED solo sabe dibujar dos:

| Forma en la compu | Byte 21 | La OLED muestra |
|---|---|---|
| `barras` | `0` | Barras desde el piso |
| `centro` | `1` | Barras desde el centro, hacia arriba y hacia abajo |
| `onda` | `0` | Barras desde el piso |
| `espectrograma` | `0` | Barras desde el piso |

Las alturas son las mismas en las dos formas: solo cambia desde dónde se dibujan. Con la marca de pico en centro se dibujan dos líneas, una arriba y otra abajo de la barra. El espejo de la OLED en el visualizador (`dibujo.dibujar_oled`) lee este mismo byte.

### Lo que no va en el paquete

- **Velocidad de caída y golpe:** la compu los aplica directamente en las alturas antes de enviarlas (al Arduino le llega la mayor entre la barra y el relleno de golpe).
- **Recalibración:** cambia el piso y el techo de las bandas en la compu; el Arduino solo ve el efecto en las alturas.
- **Color y afinador:** existen solo en el visualizador.

### Valores de la nota (byte 18)

| Valor | Nota | Nombre |
|---|---|---|
| `0` | C | Do |
| `1` | C# | Do# |
| `2` | D | Re |
| `3` | D# | Re# |
| `4` | E | Mi |
| `5` | F | Fa |
| `6` | F# | Fa# |
| `7` | G | Sol |
| `8` | G# | Sol# |
| `9` | A | La |
| `10` | A# | La# |
| `11` | B | Si |
| `12` | — | Sin nota |

## Arduino → computadora

Cada vez que se **aprieta** un botón (no mientras está apretado, y con antirrebote), el Arduino manda **un solo byte** con su código:

| Código | Botón | Qué hace la compu |
|---|---|---|
| `1` | Velocidad de caída | Pasa a la siguiente: lento → normal → rápido → lento |
| `2` | Pausa | Entra o sale de la pausa (byte 19) |
| `3` | Pico | Prende o apaga la marca de pico (byte 20) |
| `4` | Golpe | Prende o apaga el efecto de golpe en las barras |

- El byte dice **qué botón se apretó**, no el estado nuevo. La compu es la única dueña del estado: cambia el valor (`estado.aplicar_accion` en `pc/estado.py`) y lo refleja en el paquete, en el visualizador y en Blynk. El Arduino no cambia nada por su cuenta.
- Blynk no usa estos códigos: pide cada cambio por campo con `estado.cambiar` (ver [diseno.md → App en Blynk](diseno.md#app-en-blynk)).
- El Arduino tiene que usar `Serial.write(codigo)`, nunca `Serial.print`: `print` manda el carácter `'1'`, que es el byte `49`.
- Los botones siguen funcionando durante la pausa: este canal es independiente del paquete.
- La compu lee un byte cada ~10 ms con `leer_boton` (`pc/serie.py`), sin quedarse esperando.
