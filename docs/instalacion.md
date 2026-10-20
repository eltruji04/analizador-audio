# Instalación y configuración

Guía detallada para preparar el entorno en macOS y Linux. El resumen está en el [README](../README.md).

## Contenido

- [Requisitos](#requisitos)
- [macOS (Apple Silicon)](#macos-apple-silicon)
- [Linux](#linux)
- [Comprobación del entorno](#comprobación-del-entorno)
- [Configuración](#configuración)
- [Pruebas por módulo](#pruebas-por-módulo)

---

## Requisitos

- **Python:** desarrollado con 3.14. No usar funciones exclusivas de versiones recientes hasta definirlo.
- **Git** y una cuenta de GitHub con acceso al repositorio.
- **Arduino IDE** para cargar el código en el Uno.
- **VS Code** (recomendado) con la extensión *Python* de Microsoft.

---

## macOS (Apple Silicon)

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

**Limitaciones conocidas:**
- Con el dispositivo de salida múltiple, el volumen se controla desde la app de música, no con las teclas de la Mac.
- Con auriculares Bluetooth puede haber retardo o cortes; para pruebas, mejor usar los parlantes.
- **No usar el micrófono de auriculares Bluetooth** para el modo micrófono: al usarlo, macOS baja la calidad del audio y se pierden las bandas agudas. Usar el **Micrófono de MacBook Air**.

---

## Linux

**[SIN VERIFICAR — todo este apartado está pendiente de probar en las computadoras del equipo.]**

Antes de este apartado, completar la **configuración inicial de Git y GitHub** (ver la [guía de Git](guia_git.md#configuración-inicial-una-sola-vez-por-computadora)).

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

Si `pip install` falla por alguna versión de `requirements.txt` que no existe para su versión de Python, avisar al equipo en lugar de cambiar el archivo por su cuenta.

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

Cómo elegir esa fuente desde `sounddevice` queda por probar.

---

## Comprobación del entorno

Con el entorno virtual activado:

```bash
python -c "import numpy, sounddevice, serial, requests; print('ok')"
python -m sounddevice                # lista los dispositivos de audio
python -m serial.tools.list_ports    # lista los puertos serie
```

- La primera línea tiene que imprimir `ok`.
- En macOS, la lista de audio tiene que incluir **BlackHole 2ch** y el **dispositivo de salida múltiple**.
- Con el Arduino conectado, debería aparecer un puerto nuevo. Nombres probables **[SIN VERIFICAR]**:
  - macOS: `/dev/cu.usbmodem…` (Uno original) o `/dev/cu.usbserial…` (clon con chip CH340).
  - Linux: `/dev/ttyACM0` (Uno original) o `/dev/ttyUSB0` (clon).

**Importante:** los números de los dispositivos de audio cambian cuando se conecta o desconecta algo. El programa no debe elegir el dispositivo por su número.

---

## Configuración

Todos los parámetros están en [`pc/configuracion.py`](../pc/configuracion.py). Los que más probablemente haya que cambiar:

| Parámetro | Para qué |
|---|---|
| `PUERTO_SERIE` | Puerto del Arduino. Cambia según la computadora y el puerto USB: verlo con `python -m serial.tools.list_ports`. |
| `DISPOSITIVO_SISTEMA`, `DISPOSITIVO_MICROFONO` | Parte del nombre de los dispositivos de audio (se buscan por nombre, no por número). |
| `BANDAS` | Límites en Hz de las 16 bandas. |
| `INTERVALO_ENVIO` | Tiempo mínimo entre paquetes al Arduino. |
| `CAIDA_BARRAS` | Qué tan rápido bajan las barras. |
| `RANGO_MINIMO_DB`, `RANGO_MAXIMO_DB`, `TECHO_MINIMO_DB`, `VELOCIDAD_DB`, `DISTANCIA_MAXIMA_DB` | Calibración automática (explicados en `bandas.actualizar_niveles`). |

---

## Pruebas por módulo

Cada módulo se puede correr por separado para probar una parte:

| Comando | Qué hace |
|---|---|
| `python pc/captura.py` | Muestra el nivel del audio como una barra de `#` en la terminal. |
| `python pc/bandas.py` | Prueba con tonos: cada tono tiene que caer en su banda (16 de 16), y muestra cuántos valores del espectro tiene cada banda con 1024 y 4096 muestras. |
| `python pc/serie.py` | Arma un paquete de prueba (sin Arduino) y muestra sus bytes. |
