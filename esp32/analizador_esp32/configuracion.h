// configuracion.h — Constantes del analizador en el ESP32.
//
// Traducción de pc/configuracion.py. Los valores del análisis son los
// mismos que en la compu; lo nuevo son los pines (I2S, OLED, botones y
// LEDs). Lo que en la compu era solo del visualizador (ventana, colores,
// dibujo) no está: el ESP32 no tiene ventana.
//
// Los valores de este archivo los usan también las pruebas en la compu
// (esp32/pruebas), así que no puede incluir nada de Arduino.

#pragma once
#include <stdint.h>

// Tipo de los cálculos del análisis. En el ESP32, float: tiene unidad de
// punto flotante solo para float y el double es ~10 veces más lento. Las
// pruebas en la compu compilan también con double (-DANALISIS_DOUBLE) para
// comprobar que la lógica da lo mismo que el Python.
#ifdef ANALISIS_DOUBLE
typedef double real_t;
#else
typedef float real_t;
#endif

// --- Captura de audio ---
constexpr int FRECUENCIA_MUESTREO = 48000;   // muestras por segundo (Hz)
constexpr int TAMANO_BLOQUE = 1024;          // muestras por bloque (~21 ms)
constexpr int TAMANO_VENTANA = 4096;         // muestras que se analizan con la FFT (~85 ms)

// --- Bandas de frecuencia (en Hz) ---
constexpr int CANTIDAD_BARRAS = 16;
constexpr double BANDAS[CANTIDAD_BARRAS][2] = {
    {40, 60}, {60, 90}, {90, 130}, {130, 190},
    {190, 280}, {280, 410}, {410, 610}, {610, 900}, {900, 1300}, {1300, 1950},
    {1950, 2850}, {2850, 4200}, {4200, 6250}, {6250, 9200}, {9200, 13500}, {13500, 20000}};

// --- "Paquete" para la OLED (lo mismo que se mandaba al Arduino) ---
constexpr int ALTURA_MAXIMA = 32;     // alto de la OLED en píxeles
constexpr int MODO_MIC = 0;
constexpr int MODO_LINE = 1;
constexpr int FUENTE_AUDIO = MODO_MIC;  // fuente con la que arranca (en el ESP32, el micrófono I2S)
constexpr int SIN_NOTA = 12;
constexpr double INTERVALO_ENVIO = 1.0 / 30;  // tiempo mínimo entre dos cuadros de la OLED (s)
constexpr int FORMA_OLED_BARRAS = 0;
constexpr int FORMA_OLED_CENTRO = 1;

// --- Calibración automática (ver bandas::actualizar_niveles) ---
constexpr real_t RANGO_MINIMO_DB = 12.0;
constexpr real_t RANGO_MAXIMO_DB = 50.0;
constexpr real_t TECHO_MINIMO_DB = -70.0;
constexpr real_t VELOCIDAD_TECHO_DB = 0.005;
constexpr real_t RECALIBRAR_MARGEN_DB = 10.0;
constexpr real_t RECALIBRAR_RANGO_DB = 25.0;
constexpr real_t VELOCIDAD_PISO_BAJA_DB = 0.02;
constexpr real_t VELOCIDAD_PISO_SUBE_DB = 0.1;
constexpr real_t PROMEDIO_CALIBRACION_DB = 0.7;
constexpr real_t PROMEDIO_SUBIDA_DB = 0.0;
constexpr real_t PROMEDIO_BAJADA_DB = 0.7;
constexpr real_t TECHO_INICIAL_DB = 25.0;
constexpr real_t DISTANCIA_MAXIMA_DB = 35;

// --- Caída de las barras ---
constexpr int CANTIDAD_VELOCIDADES = 3;
constexpr real_t VELOCIDADES_CAIDA[CANTIDAD_VELOCIDADES] = {0.7, 1.0, 2.0};
constexpr int VELOCIDAD_INICIAL = 1;

// --- Botones (códigos, los mismos que mandaba el Arduino) ---
constexpr int BOTON_CAIDA = 1;
constexpr int BOTON_PAUSA = 2;
constexpr int BOTON_PICO = 3;
constexpr int BOTON_GOLPE = 4;
constexpr int CANTIDAD_BARRAS_GOLPE = 4;
constexpr int BARRAS_GOLPE[CANTIDAD_BARRAS_GOLPE] = {0, 1, 14, 15};

// --- Picos ---
constexpr real_t CAIDA_PICO = 0.25;

// --- Notas ---
constexpr double LA_REFERENCIA = 440;
constexpr double NOTA_FRECUENCIA_MINIMA = 60;
constexpr double NOTA_FRECUENCIA_MAXIMA = 1000;
constexpr real_t NOTA_UMBRAL_CLARIDAD = 0.15;
constexpr real_t NOTA_VOLUMEN_MINIMO_DB = -60;
constexpr double CROMA_FRECUENCIA_MINIMA = 130;
constexpr double CROMA_FRECUENCIA_MAXIMA = 2000;
constexpr real_t PROMEDIO_CROMA = 0.85;
constexpr real_t CROMA_MINIMA = 0.19;
constexpr int CROMA_ESPERA_SIN_NOTA = 47;
constexpr double CROMA_DECAIMIENTO_ARMONICOS = 0.6;
constexpr double CROMA_PESO_RAIZ = 1.3;
constexpr real_t CROMA_MARGEN_CAMBIO = 0.03;
constexpr int CROMA_BLOQUES_CAMBIO = 5;
constexpr real_t CROMA_UMBRAL_LADOS_DB = -20;
constexpr double PROMEDIO_AFINADOR = 0.8;

// --- Formas y colores ---
// En el ESP32 solo importa si la forma es "centro" (la OLED dibuja desde
// el centro) o no. Los colores no hacen nada, pero se guardan igual para
// que la app de Blynk siga mostrando lo mismo que en la compu.
constexpr int CANTIDAD_FORMAS = 4;      // barras, centro, onda, espectrograma
constexpr int FORMA_CENTRO = 1;         // índice de "centro"
constexpr int CANTIDAD_MODOS_COLOR = 3; // fijo, arcoiris, nota
constexpr int CANTIDAD_COLORES_FIJOS = 5;

// --- Detección de golpe (ver golpe.cpp) ---
constexpr int CANTIDAD_BANDAS_DETECCION_GOLPE = 2;
constexpr int BANDAS_DETECCION_GOLPE[CANTIDAD_BANDAS_DETECCION_GOLPE] = {0, 1};
constexpr real_t GOLPE_SUBIDA_DB = 6.0;
constexpr real_t GOLPE_DISTANCIA_TECHO_DB = 15.0;
constexpr double GOLPE_ESPERA = 0.15;

// --- Tempo ---
constexpr double BPM_VENTANA = 8.0;
constexpr int BPM_MINIMO_GOLPES = 4;
constexpr double BPM_SIN_GOLPES = 3.0;
constexpr double BPM_MINIMO = 70;
constexpr double BPM_MAXIMO = 180;
constexpr double BPM_TOLERANCIA = 0.25;
constexpr int BPM_MAXIMO_MOMENTOS = 64;   // largo de golpe::momentos (el deque de Python)

// ===================================================================
// Hardware del ESP32 (no existe en la versión de la compu)
// ===================================================================
// Pines pensados para un ESP32 DevKit (ESP32-WROOM-32). Cambiarlos acá si
// se usa otra placa.

// --- Entrada de audio I2S ---
// Cada fuente tiene sus pines. Al cambiar de fuente se cierra el canal
// I2S y se vuelve a abrir con los pines de la otra. -1 = sin usar.
struct PinesI2S {
    int mclk;     // reloj maestro (solo lo necesita el ADC de línea)
    int bclk;     // reloj de bits (SCK)
    int ws;       // selección de canal (WS / LRCK)
    int din;      // datos que entran al ESP32 (SD / DOUT del ADC)
    bool estereo; // true = usa los dos canales (y los "lados" para la nota)
    int canal;    // si es mono: 0 = izquierdo, 1 = derecho
};
// MIC: micrófono INMP441 (mono, con L/R a GND → canal izquierdo).
constexpr PinesI2S PINES_MIC = {-1, 14, 27, 34, false, 0};
// LINE: ADC estéreo PCM1808 con una entrada de línea (jack). En el ESP32
// clásico el MCLK solo puede salir por GPIO 0, 1 o 3.
constexpr PinesI2S PINES_LINE = {0, 26, 25, 35, true, 0};

// --- OLED 128x32 I2C ---
constexpr int PIN_SDA = 21;
constexpr int PIN_SCL = 22;
constexpr uint8_t DIRECCION_OLED = 0x3C;

// --- Botones (INPUT_PULLUP: apretado = LOW) y LEDs ---
constexpr int PINES_BOTONES[4] = {32, 33, 18, 19};   // caída, pausa, pico, golpe
constexpr int PIN_LED_MIC = 4;
constexpr int PIN_LED_LINE = 2;

// --- Puerto serie (Monitor Serie) ---
constexpr long VELOCIDAD_SERIE = 115200;
