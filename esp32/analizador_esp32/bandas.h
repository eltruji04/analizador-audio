// bandas.h — Las 16 bandas y el cálculo de las barras (traducción de pc/bandas.py).
//
// 1. Calcula el espectro de un tramo con la FFT y suma la energía de las
//    frecuencias de cada banda (BANDAS).
// 2. Ajusta solo el piso y el techo de cada banda (calibración automática).
// 3. Convierte los dB en alturas de barra entre 0 y ALTURA_MAXIMA.
// 4. Suaviza las barras: suben enseguida y bajan a la velocidad elegida.
// 5. Mide el nivel general del bloque (dBFS), sin calibración.
//
// Los arreglos de 16 valores (db, piso, techo, alturas…) los tiene quien
// llama (analisis.cpp); estas funciones los modifican por dentro, como el
// [:] de Python.

#pragma once
#include "configuracion.h"

namespace bandas {

// Nivel del bloque en dBFS (0 = onda que llega a ±1 todo el tiempo;
// silencio = −240).
real_t nivel_db(const real_t* muestras, int n);

// Lo que en Python era preparar_analisis(): ventana de Hann y qué valores
// del espectro le tocan a cada banda. Reserva memoria: se llama una vez.
// Devuelve false si no hay memoria.
bool preparar_analisis();

// Energía de cada banda para las TAMANO_VENTANA muestras.
void calcular_bandas(const real_t* muestras, real_t* energias);

// Potencia (|X|²) de cada valor del espectro del último calcular_bandas(),
// TAMANO_VENTANA/2 + 1 valores. La croma (nota.cpp) la reutiliza: usa la
// misma ventana de Hann sobre las mismas muestras.
const real_t* potencia();

// Ventana de Hann de TAMANO_VENTANA valores (la croma de los lados la usa).
const real_t* ventana_hann();

// Primer y último+1 valor del espectro de la banda (para las pruebas).
void rango_banda(int banda, int* desde, int* hasta);

void promediar(real_t* db_suave, const real_t* db, real_t subida, real_t bajada);
void niveles_iniciales(real_t* piso, real_t* techo);
void actualizar_niveles(real_t* piso, real_t* techo, const real_t* db);
void a_alturas(const real_t* db, const real_t* piso, const real_t* techo, real_t* alturas);
void suavizar(real_t* mostradas, const real_t* alturas, real_t caida);
void actualizar_picos(real_t* picos, const real_t* mostradas);

}  // namespace bandas
