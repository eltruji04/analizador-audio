# Analizador de Espectro de Frecuencias

![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![Arduino](https://img.shields.io/badge/Arduino-Uno-00878F?logo=arduino&logoColor=white)
![Blynk](https://img.shields.io/badge/App-Blynk-23C48E)
![Estado](https://img.shields.io/badge/estado-en%20desarrollo-orange)

Sistema que traduce la música en luz. Un programa en Python analiza en tiempo real el audio de la computadora y un **Arduino Uno** lo muestra en **una pantalla OLED**, con varios modos de visualización controlables desde una app de **Blynk** y desde una caja de controles físicos.

Proyecto final del **Taller de Introducción a la Ingeniería Eléctrica (TallerInE Robótico)** — IIE, Facultad de Ingeniería, Universidad de la República.

---

## Características

- **Análisis de espectro en tiempo real:** FFT de 16 bandas entre 40 Hz y 20 kHz, con calibración automática para que se vea bien con música fuerte o suave.
- **Dos fuentes de audio:** el micrófono o lo que suena en la propia computadora.
- **Modos combinables:** forma (barras o desde el centro) × color (fijo, arcoíris o según la nota que suena).
- **Efectos:** marca de pico y destello con cada golpe del bombo.
- **Control desde tres lugares sincronizados:** app de Blynk, botones, y programa en la computadora.
- **Visualizador en pantalla de computadora** muestra las bandas de forma continua y con alta resolución.

## Arquitectura

```
Audio ──► Computadora (Python)              USB serie              Arduino Uno
          FFT · golpe · nota       ◄──────────────────────►        OLED 128x32
          visualizador · Blynk                                       botones 
```

Todo el procesamiento de audio se hace en la computadora; el Arduino solo dibuja y lee los controles. Más detalles en [docs/diseno.md](docs/diseno.md).

## Estado del proyecto

| Componente | Estado |
|---|---|
| Captura de audio y análisis por bandas | ✅ Funciona |
| Envío de datos al Arduino | ✅ Funciona |
| Selección micrófono / audio del sistema | 🚧 En desarrollo |
| Detección de golpe y estimación de nota | 🚧 En desarrollo |
| Visualizador en pantalla | 🚧 En desarrollo |
| App de Blynk | 🚧 En desarrollo |
| Firmware del Arduino | 🚧 En desarrollo |

## Inicio rápido

**Requisitos:** Python 3.14, macOS o Linux, Arduino IDE y un Arduino Uno (opcional para probar el análisis).

```bash
git clone https://github.com/eltruji04/analizador-audio.git
cd analizador-audio
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Para analizar el audio del sistema en macOS hace falta **BlackHole**, y en Linux algunas dependencias extra. Los pasos completos están en [docs/instalacion.md](docs/instalacion.md).

## Uso

```bash
source .venv/bin/activate
python pc/principal.py
```

El programa empieza a analizar el audio y, si encuentra el Arduino, le manda los datos; si no, sigue funcionando sin él. Se detiene con **Ctrl+C**.

> El Monitor Serie del Arduino IDE tiene que estar cerrado: si no, ocupa el puerto.

Los parámetros (puerto serie, dispositivos de audio, bandas, calibración) están en [`pc/configuracion.py`](pc/configuracion.py). Ver [Configuración](docs/instalacion.md#configuración).

## Estructura del repositorio

```
analizador-audio/
├── pc/                 # Programa de la computadora (Python)
├── arduino/            # Firmware del Arduino Uno
├── docs/               # Documentación del proyecto
└── requirements.txt    # Dependencias de Python
```

## Documentación

| Documento | Contenido |
|---|---|
| [Instalación y configuración](docs/instalacion.md) | Entorno en macOS y Linux, captura del audio del sistema, parámetros y pruebas |
| [Diseño del sistema](docs/diseno.md) | Arquitectura, hardware, modos, Blynk, decisiones de diseño, calendario y riesgos |
| [Protocolo serie](docs/protocolo_serie.md) | Formato de los mensajes entre la computadora y el Arduino |
| [Guía de Git](docs/guia_git.md) | Cómo trabaja el equipo con Git y GitHub |

## Hardware

| Componente | Cantidad |
|---|---|
| Arduino Uno | 1 |
| OLED 128x32 I2C | 1 |
| Pulsadores | 4 |
| LEDs indicadores con resistencia | 2 |
| Caja de control | 1 |

## Equipo

| Integrante | Área |
|---|---|
| Santiago Trujillo | Software en la computadora (Python) |
| Lucía Hernández | Firmware del Arduino y protocolo serie y pantalla OLED|
| Benjamín Cabrera | Hardware, construcción y Blynk |
