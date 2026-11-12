# Instalación y configuración

Guía detallada para preparar el entorno en macOS y Linux. El resumen está en el [README](../README.md).

> Los puntos marcados **[SIN VERIFICAR]** todavía no se probaron, y los marcados **[A CONFIRMAR]** son decisiones pendientes.

## Contenido

- [Requisitos](#requisitos)
- [Instalación en macOS (Apple Silicon)](#instalación-en-macos-apple-silicon)
- [Instalación en Linux](#instalación-en-linux)
- [Comprobación del entorno](#comprobación-del-entorno)
- [Configuración](#configuración)
  - [Programa de la computadora](#programa-de-la-computadora)
  - [Firmware del Arduino](#firmware-del-arduino)
  - [Blynk (opcional)](#blynk-opcional)
- [Pruebas por módulo](#pruebas-por-módulo)

---

## Requisitos

- **Python:** desarrollado con 3.14.
- **Git**, para clonar el repositorio.
- **Arduino IDE** para cargar el firmware en el Uno, con las librerías *Adafruit SSD1306* y *Adafruit GFX Library* (ver [Firmware del Arduino](#firmware-del-arduino)).
- **VS Code** (recomendado) con la extensión *Python* de Microsoft.

Las dependencias de Python están en [`requirements.txt`](../requirements.txt): `numpy`, `sounddevice`, `pyserial`, `pygame-ce`, `blynk-library-python` y `python-dotenv` (más las que estas usan).

---

## Instalación en macOS (Apple Silicon)

Probado en macOS 26.6 con Python 3.14.7 de Homebrew.

### 1. Clonar el repositorio y crear el entorno virtual

```bash
git clone https://github.com/eltruji04/analizador-audio.git
cd analizador-audio
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

El Python de Homebrew no permite instalar paquetes con `pip` de forma global, así que **siempre hay que trabajar con el entorno virtual activado**: el prompt empieza con `(.venv)`.

### 2. Captura del audio del sistema (BlackHole)

macOS no deja capturar directamente lo que suena en la computadora. Se usa el dispositivo de audio virtual **BlackHole**:

```bash
brew install --cask blackhole-2ch
```

Hay que **reiniciar** la Mac después de instalarlo. Luego:

1. Abrir **Configuración de Audio MIDI**.
2. Tocar **+** → **Crear dispositivo de salida múltiple**.
3. Marcar **BlackHole 2ch** y la salida en la que se escucha (por ejemplo, los parlantes de la Mac).
4. Elegir la salida real como **dispositivo principal** y activar **Corrección de deriva** en BlackHole.
5. En **Ajustes del Sistema → Sonido → Salida**, elegir el **dispositivo de salida múltiple**.

---

## Instalación en Linux

**[SIN VERIFICAR — todavía no se probó este apartado en Linux.]**

### 1. Dependencias del sistema

En Debian o Ubuntu probablemente haga falta:

```bash
sudo apt install python3-venv libportaudio2
```

- `python3-venv`: en algunas distribuciones `venv` viene en un paquete aparte.
- `libportaudio2`: `sounddevice` usa PortAudio, que en Linux probablemente no venga incluido.

### 2. Clonar el repositorio y crear el entorno virtual

```bash
git clone https://github.com/eltruji04/analizador-audio.git
cd analizador-audio
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Si `pip install` falla porque alguna versión de `requirements.txt` no existe para tu versión de Python, probá con Python 3.14 o abrí un [issue](https://github.com/eltruji04/analizador-audio/issues) con el error.

### 3. Permisos del puerto serie

Para usar el Arduino sin `sudo`, probablemente el usuario tenga que estar en el grupo `dialout`:

```bash
sudo usermod -aG dialout $USER
```

Hay que cerrar la sesión y volver a entrar para que el cambio tenga efecto.

### 4. Captura del audio del sistema

En Linux no se usa BlackHole. El audio del sistema suele estar disponible como una fuente **"monitor"** de PulseAudio o PipeWire. Para ver las fuentes disponibles:

```bash
pactl list short sources
```

Cómo elegir esa fuente desde `sounddevice` (qué texto poner en `DISPOSITIVO_SISTEMA`) queda por probar.

---

## Comprobación del entorno

Con el entorno virtual activado:

```bash
python -c "import numpy, sounddevice, serial, pygame, BlynkLib, dotenv; print('ok')"
python -m sounddevice                # lista los dispositivos de audio
python -m serial.tools.list_ports    # lista los puertos serie
```

- La primera línea tiene que imprimir `ok` (pygame y Blynk además imprimen su versión).
- En macOS, la lista de audio tiene que incluir **BlackHole 2ch** y el **dispositivo de salida múltiple**.
- Con el Arduino conectado, debería aparecer un puerto nuevo. Nombres probables:
  - macOS: `/dev/cu.usbmodem…` (Uno original) o `/dev/cu.usbserial…` (clon con chip CH340).
  - Linux: `/dev/ttyACM0` (Uno original) o `/dev/ttyUSB0` (clon).
- Con `python -m serial.tools.list_ports -v` se ve además el `VID:PID` de cada puerto. El Uno original aparece como `2341:0043`: así lo encuentra el programa en cualquier puerto USB.

**Importante:** los números de los dispositivos de audio cambian cuando se conecta o desconecta algo. Por eso el programa los busca por su nombre, nunca por su número.

---

## Configuración

### Programa de la computadora

Todos los parámetros están en [`pc/configuracion.py`](../pc/configuracion.py). Los que más probablemente haya que cambiar:

| Parámetro | Para qué |
|---|---|
| `PUERTO_SERIE` | Plan B para encontrar el Arduino. El programa lo busca solo por `VID_ARDUINO`/`PID_ARDUINO`, en cualquier puerto USB; este puerto fijo solo se usa si no aparece ninguno con ese VID:PID (por ejemplo, un clon con CH340). Verlo con `python -m serial.tools.list_ports`. |
| `FUENTE_AUDIO` | Fuente con la que arranca: `MODO_LINE` (audio del sistema) o `MODO_MIC` (micrófono). Después se cambia con la tecla `I` o el panel. |
| `DISPOSITIVO_SISTEMA`, `DISPOSITIVO_MICROFONO` | Parte del nombre de los dispositivos de audio (se buscan por nombre, no por número). Son los dos entre los que se alterna al cambiar la fuente. |

Para ajustar el comportamiento:

| Parámetro | Para qué |
|---|---|
| `BANDAS` | Límites en Hz de las 16 bandas. |
| `INTERVALO_ENVIO` | Tiempo mínimo entre paquetes al Arduino (1/30 s). |
| `VID_ARDUINO`, `PID_ARDUINO` | VID:PID del chip USB del Arduino (`2341:0043` = Uno original). Con eso se lo busca en cualquier puerto. |
| `INTERVALO_BUSQUEDA` | Cada cuántos segundos se intenta conectar el Arduino mientras no está (1 s). |
| `VELOCIDADES_CAIDA`, `VELOCIDAD_INICIAL` | Píxeles por bloque que bajan las barras en cada velocidad (lenta, normal, rápida) y con cuál arranca. |
| `CAIDA_PICO` | Qué tan rápido baja la marca de pico. |
| `PROMEDIO_SUBIDA_DB`, `PROMEDIO_BAJADA_DB` | Cuánto se promedia el nivel de las barras cuando sube y cuando baja (0 = sin promedio). Subir el de subida (por ejemplo a 0,3) calma el temblor de los graves a cambio de una subida un poco más lenta. |
| `PROMEDIO_CALIBRACION_DB` | Promedio parejo del nivel que usa la calibración automática del piso y el techo. |
| `RANGO_MINIMO_DB`, `RANGO_MAXIMO_DB`, `TECHO_MINIMO_DB`, `TECHO_INICIAL_DB`, `DISTANCIA_MAXIMA_DB` | Límites de la calibración automática (explicados en `bandas.actualizar_niveles`). |
| `VELOCIDAD_TECHO_DB`, `VELOCIDAD_PISO_BAJA_DB`, `VELOCIDAD_PISO_SUBE_DB` | Qué tan rápido se mueven el techo y el piso de cada banda. |
| `RECALIBRAR_MARGEN_DB`, `RECALIBRAR_RANGO_DB` | Dónde quedan el techo y el piso al recalibrar con la tecla `R`. |
| `BANDAS_DETECCION_GOLPE`, `GOLPE_SUBIDA_DB`, `GOLPE_DISTANCIA_TECHO_DB`, `GOLPE_ESPERA` | Detección de golpe (explicados en `golpe.py`). |
| `BARRAS_GOLPE` | Barras que se llenan con cada golpe (1, 2, 15 y 16). |
| `COLORES_FIJOS` | Muestras del modo de color fijo. |
| `PASOS_ONDA`, `OPACIDAD_RELLENO_ARRIBA`, `OPACIDAD_RELLENO_ABAJO`, `ANCHO_BRILLO_ONDA`, `OPACIDAD_BRILLO_ONDA` | Aspecto de la forma onda: qué tan suave es la curva, el degradado del relleno y el brillo detrás de la línea. |
| `ANCHO_TIRA_GOLPE` | Ancho en píxeles de las tiras de golpe a los costados del espectro. |
| `SEPARACION_PICO_ONDA`, `OPACIDAD_PICO_ONDA` | Curva de peak de la forma onda: cuántos píxeles queda por encima del pico y qué tan visible es. |
| `TRANSICION_COLOR` | Segundos que tarda el color de las bandas en pasar al nuevo al cambiar la nota o el modo de color. |
| `BRILLO_BASE_BARRA`, `ANCHO_BRILLO_BARRA`, `OPACIDAD_BRILLO_BARRA` | Aspecto de las barras: qué tan oscura es la base y el halo alrededor. |
| `ALTO_REFLEJO`, `OPACIDAD_REFLEJO` | Reflejo debajo de las barras y la onda (alto como parte del espectro y opacidad). |
| `OPACIDAD_PULSO_GOLPE` | Cuánto se aclara el fondo del espectro con cada golpe (0 lo apaga). |
| `DURACION_FUNDIDO_FORMA`, `DURACION_BOTON` | Segundos del fundido al cambiar de forma y de la animación de los botones. |
| `NIVEL_MINIMO_DB`, `NIVEL_AMARILLO_DB`, `NIVEL_ROJO_DB`, `NIVEL_CAIDA_DB` | Medidor de nivel: rango, zonas de color y qué tan rápido baja. |
| `BPM_VENTANA`, `BPM_MINIMO_GOLPES`, `BPM_SIN_GOLPES`, `BPM_MINIMO`, `BPM_MAXIMO`, `BPM_TOLERANCIA` | Cálculo del tempo (explicados en `golpe.estimar_bpm`). |
| `ARCHIVO_PREFERENCIAS` | Dónde se guarda la configuración elegida (`pc/preferencias.json`). Para volver a los valores de siempre, borrar ese archivo. |

### Firmware del Arduino

1. En el Arduino IDE, **Herramientas → Administrar bibliotecas**, instalar **Adafruit SSD1306** (acepta instalar también **Adafruit GFX Library**).
2. Abrir [`arduino/analizador_oled/analizador_oled.ino`](../arduino/analizador_oled/analizador_oled.ino).
3. Elegir la placa **Arduino Uno** y su puerto, y **cargar**.
4. **Cerrar el Monitor Serie** antes de correr `principal.py`: si está abierto, ocupa el puerto.

Las conexiones de la OLED, los botones y los LEDs están en [diseno.md → Hardware](diseno.md#hardware).

### Blynk (opcional)

Sin Blynk el programa funciona igual: al arrancar avisa `Blynk sin conectar` y sigue. Para controlarlo desde el celular:

1. En [blynk.cloud](https://blynk.cloud), crear una plantilla con estos **datastreams** (pines virtuales, tipo entero):

   | Pin | Campo | Valores |
   |---|---|---|
   | `V0` | Velocidad de caída | `0` lenta, `1` normal, `2` rápida |
   | `V1` | Pausa | `0` / `1` |
   | `V2` | Marca de pico | `0` / `1` |
   | `V3` | Golpe | `0` / `1` |
   | `V4` | Afinador | `0` / `1` |
   | `V5` | Forma | `0` barras, `1` centro, `2` onda, `3` espectrograma |
   | `V6` | Color | `0` fijo, `1` arcoíris, `2` nota |
   | `V7` | Color fijo | `0` a `4` (índice en `COLORES_FIJOS`) |

2. Crear un dispositivo con esa plantilla y copiar su **token**.
3. Crear un archivo `.env` en la raíz del proyecto con esta línea:

   ```
   BLYNK_AUTH_TOKEN=<tu token>
   ```

El `.env` está en `.gitignore`: el token es una clave privada y no se sube nunca al repositorio. Cómo se sincroniza la app con la compu: [diseno.md → App en Blynk](diseno.md#app-en-blynk).

---

## Pruebas por módulo

Cada módulo se puede correr por separado para probar una parte:

| Comando | Qué hace |
|---|---|
| `python pc/captura.py` | Muestra el nivel del audio del sistema como una barra de `#` en la terminal. |
| `python pc/bandas.py` | Prueba con tonos: cada tono tiene que caer en su banda (16 de 16), y muestra cuántos valores del espectro tiene cada banda con 1024 y 4096 muestras. |
| `python pc/serie.py` | Arma paquetes de prueba (sin Arduino), comprueba los errores por valores inválidos y prueba la lectura de botones con un puerto falso. |
| `python pc/estado.py` | Prueba los cambios de estado: códigos de botón, rotación de formas, valores inválidos y avisos a los suscriptores. |
| `python pc/golpe.py` | Prueba el detector de golpes con casos inventados; tiene que terminar con `Errores: 0 de 12`. |
| `python pc/visualizador.py` | Abre la ventana con datos simulados (sin audio ni Arduino): barras en movimiento, un golpe cada 0,5 s y una nota distinta cada 2 s. Se cierra con la ✕. |
