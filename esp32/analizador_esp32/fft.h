// fft.h — FFT real para el ESP32 (reemplaza a numpy.fft).
//
// En vez de devolver el espectro entero, calcula directamente lo que usa
// el análisis. Así no hacen falta arreglos grandes para la parte real y la
// imaginaria (en el ESP32, con WiFi, quedan ~150 KB de RAM libres):
// - potencia(): |X|² de cada valor del espectro (bandas y croma).
// - autocorrelacion(): r(τ) para el afinador (YIN).
//
// La FFT real de n valores se hace con una FFT compleja de n/2 (los pares
// como parte real y los impares como imaginaria) y después se separa: cuesta
// la mitad. Una sola tabla de senos (un cuarto de onda) sirve para todos los
// largos hasta LARGO_MAXIMO.

#pragma once
#include "configuracion.h"

namespace fft {

// Largo máximo de la FFT real: la autocorrelación rellena a 2 × 4096.
constexpr int LARGO_MAXIMO = 2 * TAMANO_VENTANA;

// Reserva la tabla y el espacio de trabajo. Se llama una vez, al empezar.
// Devuelve false si no hay memoria.
bool iniciar();

// pot[k] = |rfft(x · ventana)[k]|² para k de 0 a n/2 (n/2 + 1 valores).
// n potencia de 2, n ≤ LARGO_MAXIMO. ventana puede ser nullptr (sin ventana).
// Igual que numpy.abs(numpy.fft.rfft(x * ventana)) ** 2.
void potencia(const real_t* x, const real_t* ventana, int n, real_t* pot);

// Autocorrelación de (x − media): r[τ] = Σ (x[i] − media)(x[i+τ] − media)
// para τ de 0 a cantidad − 1. n ≤ LARGO_MAXIMO / 2. Igual que
// numpy.fft.irfft(numpy.abs(numpy.fft.rfft(x - media, 2 * n)) ** 2)[0:cantidad].
void autocorrelacion(const real_t* x, real_t media, int n, real_t* r, int cantidad);

}  // namespace fft
