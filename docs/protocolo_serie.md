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

C = 0
C# = 1
D = 2
D# = 3
E = 4
F = 5
F# = 6
G = 7
G# = 8
A = 9
A# = 10
B = 11.

## Arduino → computadora

**[A CONFIRMAR]** Mensajes con los cambios hechos desde los controles físicos (modo, color, brillo, encendido, pico, golpe), para sincronizarlos con la app y el visualizador.
