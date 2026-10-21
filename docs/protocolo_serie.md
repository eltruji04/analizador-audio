# Protocolo serie

Comunicación por USB entre la computadora (`pc/serie.py`) y el Arduino Uno. **Si se cambia este formato, hay que cambiar a la vez `pc/serie.py` y el código del Arduino.**

## Computadora → Arduino

115200 baudios. Cada paquete tiene **21 bytes**:

| Byte | Contenido | Valores |
|---|---|---|
| 0 | Inicio de paquete | `255` |
| 1 – 16 | Altura de cada barra, de la banda más grave a la más aguda | `0` a `32` |
| 17 | Fuente de audio | `0` = micrófono, `1` = audio del sistema |
| 18 | Nota | `0` a `11`; `12` = sin nota |
| 19 | Pausa | `0` = normal, `1` = en pausa |
| 20 | Pico | `0` = sin marca de pico, `1` = dibujar la marca de pico |

Como ningún otro byte puede valer 255, el Arduino lo usa para encontrar el comienzo de cada paquete. `armar_paquete` lo garantiza: limita las alturas a `0`–`32` y da error si la fuente, la nota, la pausa o el pico están fuera de rango.

Ejemplo (salida de `python pc/serie.py`):

```
255  0 31 32 32 4 5 6 7 8 9 10 11 12 13 14 15  0  12  0  0
```

Inicio, las 16 alturas (la prueba manda a propósito −2, 34 y 300, que se corrigen a 0 y 32), micrófono, sin nota, sin pausa y sin pico.

### Frecuencia de envío

Como mucho un paquete cada `INTERVALO_ENVIO` (1/30 s). Medido con el Uno real: unos 21 paquetes por segundo. Cada paquete reemplaza al anterior.

### Pausa

Al entrar en pausa, la compu manda **un último paquete con pausa = 1** y después no manda nada más hasta salir de la pausa. El Arduino congela la pantalla o muestra "PAUSA". Que no lleguen paquetes durante la pausa es lo esperado.

### Velocidad de caída y golpe

No van en el paquete: la compu los aplica directamente en las alturas antes de enviarlas.

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
- Blynk pide los mismos cambios con los mismos códigos.
- El Arduino tiene que usar `Serial.write(codigo)`, nunca `Serial.print`: `print` manda el carácter `'1'`, que es el byte `49`. Por lo mismo, no puede mandar texto de depuración por el puerto.
- Los botones siguen funcionando durante la pausa: este canal es independiente del paquete.
- La compu lee un byte cada ~10 ms con `leer_boton` (`pc/serie.py`), sin quedarse esperando.
