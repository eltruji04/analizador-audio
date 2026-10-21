# Protocolo serie

Comunicación por USB entre la computadora (`pc/serie.py`) y el Arduino Uno. **Si se cambia este formato, hay que cambiar a la vez `pc/serie.py` y el código del Arduino.**

## Computadora → Arduino

115200 baudios. Cada paquete tiene **19 bytes**:

| Byte | Contenido | Valores |
|---|---|---|
| 0 | Inicio de paquete | `255` |
| 1 – 16 | Altura de cada barra, de la banda más grave a la más aguda | `0` a `32` |
| 17 | Fuente de audio | `0` = micrófono, `1` = audio del sistema |
| 18 | Nota | `0` a `11`; `12` = sin nota |

Como ningún otro byte puede valer 255, el Arduino lo usa para encontrar el comienzo de cada paquete.

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

**[A CONFIRMAR]** Mensajes con los cambios hechos desde los controles físicos (modo, color, brillo, encendido, pico, golpe), para sincronizarlos con la app y el visualizador.
