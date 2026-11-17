// analisis.h — Análisis de cada bloque de audio (traducción de
// principal.al_recibir_bloque y de la preparación de principal.py).
//
// Con cada bloque nuevo:
// 1. lo agrega a una ventana deslizante con las últimas TAMANO_VENTANA muestras;
// 2. calcula la energía de las 16 bandas y la pasa a dB;
// 3. ajusta solo el piso y el techo de cada banda (calibración automática);
// 4. convierte los dB en alturas de barra entre 0 y ALTURA_MAXIMA;
// 5. suaviza las barras según la velocidad de caída;
// 6. actualiza los picos, el destello de golpe, el tempo y la nota;
// 7. si no está en pausa, arma el "paquete" para la OLED (unos 21 por
//    segundo). Es el mismo paquete de 22 bytes que la compu le mandaba al
//    Arduino, ahora sin puerto serie: lo dibuja pantalla.cpp.
//
// No usa nada de Arduino: las pruebas en la compu lo corren igual.

#pragma once
#include "configuracion.h"
#include <stdint.h>

namespace analisis {

// Lo que antes viajaba por el puerto serie (ver docs/protocolo_serie.md).
struct Paquete {
    uint8_t alturas[CANTIDAD_BARRAS];   // 0 a 32
    uint8_t fuente;                     // MODO_MIC o MODO_LINE
    uint8_t nota;                       // 0 a 11 o SIN_NOTA
    uint8_t pausa;
    uint8_t pico;
    uint8_t forma_oled;                 // FORMA_OLED_BARRAS o FORMA_OLED_CENTRO
};

// Los últimos resultados (en la compu los dibujaba el visualizador; acá
// sirven para el Monitor Serie y las pruebas).
struct Resultados {
    real_t alturas[CANTIDAD_BARRAS];
    real_t destello[CANTIDAD_BARRAS];
    real_t picos[CANTIDAD_BARRAS];
    int nota;
    double frecuencia;      // NAN si no hay
    double cents;           // NAN si no hay
    double momento_golpe;   // NAN si no hubo ninguno
    real_t nivel;           // dBFS del último bloque
    int bpm;                // −1 si no hay
};

// Reserva memoria y prepara la FFT, las bandas y la nota. Una vez, al empezar.
bool iniciar();

// Analiza un bloque de m muestras. izquierdo: el canal izquierdo (o el
// único, si es mono). derecho: el canal derecho, o nullptr si es mono.
// ahora: el momento del bloque, en segundos. Devuelve true si armó un
// paquete nuevo para la OLED (lo deja en *paquete).
bool procesar_bloque(const real_t* izquierdo, const real_t* derecho, int m, double ahora,
                     Paquete* paquete);

// Al cambiar de fuente: el micrófono y la línea tienen niveles muy
// distintos, así que se descarta lo de la anterior (la ventana deslizante
// y el promedio de dB) y se recalibra.
void cambio_de_fuente();

const Resultados& resultados();

// Vuelve todo al estado de arranque (para las pruebas).
void reiniciar();

}  // namespace analisis
