// bandas.cpp — Las 16 bandas y el cálculo de las barras (ver bandas.h).

#include "bandas.h"
#include "fft.h"
#include <math.h>
#include <stdlib.h>

namespace bandas {

namespace {

constexpr int N = TAMANO_VENTANA;
constexpr int VALORES_ESPECTRO = N / 2 + 1;

real_t* ventana = nullptr;     // Hann de N valores
real_t* potencias = nullptr;   // |X|² del último tramo
// Valores del espectro de cada banda: de desde[b] a hasta[b] − 1. En
// Python era una máscara de True/False; como las frecuencias van en
// orden, cada banda es un tramo seguido.
int desde[CANTIDAD_BARRAS];
int hasta[CANTIDAD_BARRAS];

inline real_t maximo(real_t a, real_t b) { return a > b ? a : b; }
inline real_t minimo(real_t a, real_t b) { return a < b ? a : b; }

}  // namespace

real_t nivel_db(const real_t* muestras, int n) {
    real_t suma = 0;
    for (int i = 0; i < n; i++) suma += muestras[i] * muestras[i];
    double rms = sqrt((double)suma / n);
    return (real_t)(20 * log10(rms + 0.000000000001));
}

bool preparar_analisis() {
    if (ventana != nullptr) return true;
    if (!fft::iniciar()) return false;
    ventana = (real_t*)malloc(N * sizeof(real_t));
    potencias = (real_t*)malloc(VALORES_ESPECTRO * sizeof(real_t));
    if (!ventana || !potencias) return false;
    // numpy.hanning(N): 0,5 − 0,5·cos(2πk / (N − 1)).
    for (int k = 0; k < N; k++) ventana[k] = (real_t)(0.5 - 0.5 * cos(2 * M_PI * k / (N - 1)));
    // Frecuencia de cada valor del espectro, calculada igual que
    // numpy.fft.rfftfreq(N, d=1/fs): k · (1 / (N · d)). Así los bordes
    // exactos (13500 Hz cae justo en el valor 1152) quedan del mismo lado.
    double separacion = 1.0 / (N * (1.0 / FRECUENCIA_MUESTREO));
    for (int b = 0; b < CANTIDAD_BARRAS; b++) {
        desde[b] = VALORES_ESPECTRO;
        hasta[b] = 0;
        for (int k = 0; k < VALORES_ESPECTRO; k++) {
            double f = k * separacion;
            if (f >= BANDAS[b][0] && f < BANDAS[b][1]) {
                if (k < desde[b]) desde[b] = k;
                hasta[b] = k + 1;
            }
        }
        if (desde[b] > hasta[b]) desde[b] = hasta[b];   // banda vacía
    }
    return true;
}

void calcular_bandas(const real_t* muestras, real_t* energias) {
    // La ventana suaviza los bordes del tramo para que la energía de un
    // tono no se desparrame hacia las bandas vecinas.
    // Potencia y no magnitud: se eleva al cuadrado una sola vez.
    fft::potencia(muestras, ventana, N, potencias);
    for (int b = 0; b < CANTIDAD_BARRAS; b++) {
        real_t suma = 0;
        for (int k = desde[b]; k < hasta[b]; k++) suma += potencias[k];
        energias[b] = suma;
    }
}

const real_t* potencia() { return potencias; }

const real_t* ventana_hann() { return ventana; }

void rango_banda(int banda, int* d, int* h) {
    *d = desde[banda];
    *h = hasta[banda];
}

void promediar(real_t* db_suave, const real_t* db, real_t subida, real_t bajada) {
    for (int b = 0; b < CANTIDAD_BARRAS; b++) {
        real_t p = db[b] > db_suave[b] ? subida : bajada;
        db_suave[b] = p * db_suave[b] + (1 - p) * db[b];
    }
}

void niveles_iniciales(real_t* piso, real_t* techo) {
    for (int b = 0; b < CANTIDAD_BARRAS; b++) {
        techo[b] = TECHO_INICIAL_DB;
        piso[b] = TECHO_INICIAL_DB - RANGO_MAXIMO_DB;
    }
}

void actualizar_niveles(real_t* piso, real_t* techo, const real_t* db) {
    // 1. Techo: sube enseguida, baja despacio, y nunca baja de TECHO_MINIMO_DB.
    real_t nuevo_techo[CANTIDAD_BARRAS];
    real_t techo_general = -1e30;
    for (int b = 0; b < CANTIDAD_BARRAS; b++) {
        nuevo_techo[b] = db[b] > techo[b] ? db[b] : techo[b] - VELOCIDAD_TECHO_DB;
        nuevo_techo[b] = maximo(nuevo_techo[b], TECHO_MINIMO_DB);
        techo_general = maximo(techo_general, nuevo_techo[b]);
    }
    for (int b = 0; b < CANTIDAD_BARRAS; b++) {
        // Límite relativo a la banda más fuerte: protege de las bandas casi vacías.
        nuevo_techo[b] = maximo(nuevo_techo[b], techo_general - DISTANCIA_MAXIMA_DB);
        // 2. Piso: baja y sube despacio.
        real_t nuevo_piso = db[b] < piso[b] ? piso[b] - VELOCIDAD_PISO_BAJA_DB
                                            : piso[b] + VELOCIDAD_PISO_SUBE_DB;
        // 3. Distancia entre piso y techo, entre RANGO_MINIMO y RANGO_MAXIMO
        // (numpy.clip: primero el mínimo, después el máximo).
        nuevo_piso = minimo(maximo(nuevo_piso, nuevo_techo[b] - RANGO_MAXIMO_DB),
                            nuevo_techo[b] - RANGO_MINIMO_DB);
        techo[b] = nuevo_techo[b];
        piso[b] = nuevo_piso;
    }
}

void a_alturas(const real_t* db, const real_t* piso, const real_t* techo, real_t* alturas) {
    for (int b = 0; b < CANTIDAD_BARRAS; b++) {
        real_t proporcion = (db[b] - piso[b]) / (techo[b] - piso[b]);
        alturas[b] = minimo(maximo(proporcion * ALTURA_MAXIMA, 0), ALTURA_MAXIMA);
    }
}

void suavizar(real_t* mostradas, const real_t* alturas, real_t caida) {
    for (int b = 0; b < CANTIDAD_BARRAS; b++) {
        mostradas[b] = maximo(maximo(alturas[b], mostradas[b] - caida), 0);
    }
}

void actualizar_picos(real_t* picos, const real_t* mostradas) {
    for (int b = 0; b < CANTIDAD_BARRAS; b++) {
        picos[b] = maximo(mostradas[b], picos[b] - CAIDA_PICO);
    }
}

}  // namespace bandas
