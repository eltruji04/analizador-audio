// fft.cpp — FFT real (ver fft.h).
//
// Cuentas de la FFT real con una compleja de m = n/2:
//   z[j] = x[2j] + i·x[2j+1]   →   Z = FFT_m(z)
//   X[k] = E[k] + W^k · O[k],  con W = exp(−2πi/n),
//   E[k] = (Z[k] + conj(Z[m−k])) / 2   y   O[k] = (Z[k] − conj(Z[m−k])) / 2i.
// X[k] y X[m−k] salen del mismo par (Z[k], Z[m−k]): por eso se recorren de a pares.

#include "fft.h"
#include <math.h>
#include <stdlib.h>

namespace fft {

namespace {

constexpr int CUARTO = LARGO_MAXIMO / 4;

// sen(2πk / LARGO_MAXIMO) para k de 0 a CUARTO (un cuarto de onda).
real_t* seno = nullptr;
// Espacio de trabajo de la FFT compleja (hasta LARGO_MAXIMO/2 valores).
real_t* zr = nullptr;
real_t* zi = nullptr;

// cos y sen de 2πk / LARGO_MAXIMO, para k de 0 a LARGO_MAXIMO/2 − 1.
inline void giro(int k, real_t& c, real_t& s) {
    if (k <= CUARTO) {
        s = seno[k];
        c = seno[CUARTO - k];
    } else {
        s = seno[2 * CUARTO - k];
        c = -seno[k - CUARTO];
    }
}

// FFT compleja de m valores (m potencia de 2) sobre zr/zi, en el lugar.
void fft_compleja(int m) {
    // 1. Reordenar por bits invertidos.
    for (int i = 1, j = 0; i < m; i++) {
        int bit = m >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) {
            real_t t = zr[i]; zr[i] = zr[j]; zr[j] = t;
            t = zi[i]; zi[i] = zi[j]; zi[j] = t;
        }
    }
    // 2. Mariposas: W_largo^k = exp(−2πi k/largo) = giro(k · LARGO_MAXIMO/largo).
    for (int largo = 2; largo <= m; largo <<= 1) {
        int mitad = largo >> 1;
        int paso = LARGO_MAXIMO / largo;
        for (int k = 0; k < mitad; k++) {
            real_t wr, wi;
            giro(k * paso, wr, wi);
            wi = -wi;
            for (int i = k; i < m; i += largo) {
                int b = i + mitad;
                real_t vr = zr[b] * wr - zi[b] * wi;
                real_t vi = zr[b] * wi + zi[b] * wr;
                zr[b] = zr[i] - vr;
                zi[b] = zi[i] - vi;
                zr[i] += vr;
                zi[i] += vi;
            }
        }
    }
}

// X[k] a partir de a = Z[k] y b = Z[m−k] (ver arriba). paso: LARGO_MAXIMO / n.
inline void separar(int k, int paso, real_t ar, real_t ai, real_t br, real_t bi,
                    real_t& xr, real_t& xi) {
    real_t er = (ar + br) / 2, ei = (ai - bi) / 2;
    real_t or_ = (ai + bi) / 2, oi = -(ar - br) / 2;
    real_t c, s;
    giro(k * paso, c, s);
    // W^k = c − i·s
    xr = er + c * or_ + s * oi;
    xi = ei + c * oi - s * or_;
}

}  // namespace

bool iniciar() {
    if (seno != nullptr) return true;
    seno = (real_t*)malloc((CUARTO + 1) * sizeof(real_t));
    zr = (real_t*)malloc(LARGO_MAXIMO / 2 * sizeof(real_t));
    zi = (real_t*)malloc(LARGO_MAXIMO / 2 * sizeof(real_t));
    if (!seno || !zr || !zi) return false;
    // En double y después a real_t: la tabla queda lo más exacta posible.
    for (int k = 0; k <= CUARTO; k++) seno[k] = (real_t)sin(2 * M_PI * k / LARGO_MAXIMO);
    return true;
}

void potencia(const real_t* x, const real_t* ventana, int n, real_t* pot) {
    int m = n / 2;
    int paso = LARGO_MAXIMO / n;
    for (int j = 0; j < m; j++) {
        zr[j] = ventana ? x[2 * j] * ventana[2 * j] : x[2 * j];
        zi[j] = ventana ? x[2 * j + 1] * ventana[2 * j + 1] : x[2 * j + 1];
    }
    fft_compleja(m);
    pot[0] = (zr[0] + zi[0]) * (zr[0] + zi[0]);
    pot[m] = (zr[0] - zi[0]) * (zr[0] - zi[0]);
    for (int k = 1; k < m; k++) {
        real_t xr, xi;
        separar(k, paso, zr[k], zi[k], zr[m - k], zi[m - k], xr, xi);
        pot[k] = xr * xr + xi * xi;
    }
}

void autocorrelacion(const real_t* x, real_t media, int n, real_t* r, int cantidad) {
    // FFT real de 2n valores (x y después n ceros) → compleja de m = n.
    int m = n;
    int paso = LARGO_MAXIMO / (2 * n);
    for (int j = 0; j < m; j++) {
        if (2 * j < n) {
            zr[j] = x[2 * j] - media;
            zi[j] = x[2 * j + 1] - media;
        } else {
            zr[j] = 0;
            zi[j] = 0;
        }
    }
    fft_compleja(m);

    // 1. Potencia P[k] = |X[k]|², guardada en zr[k] (P[m] aparte).
    real_t p_ultima = (zr[0] - zi[0]) * (zr[0] - zi[0]);
    zr[0] = (zr[0] + zi[0]) * (zr[0] + zi[0]);
    for (int k = 1; k <= m / 2; k++) {
        int q = m - k;
        real_t ar = zr[k], ai = zi[k], br = zr[q], bi = zi[q];
        real_t xr, xi;
        separar(k, paso, ar, ai, br, bi, xr, xi);
        real_t pk = xr * xr + xi * xi;
        separar(q, paso, br, bi, ar, ai, xr, xi);
        real_t pq = xr * xr + xi * xi;
        zr[k] = pk;
        zr[q] = pq;
    }

    // 2. Inversa de P (real): se rearma Z' = E + i·O con
    //    E = (P[k] + P[m−k]) / 2  y  O = (P[k] − P[m−k]) / 2 · exp(+iθ_k),
    //    y se guarda conj(Z') para hacer la inversa con la FFT directa.
    {
        real_t e = (zr[0] + p_ultima) / 2, d = (zr[0] - p_ultima) / 2;
        zr[0] = e;
        zi[0] = -d;
    }
    for (int k = 1; k <= m / 2; k++) {
        int q = m - k;
        real_t pk = zr[k], pq = zr[q];
        real_t c, s;
        // Z'[k]
        real_t e = (pk + pq) / 2, d = (pk - pq) / 2;
        giro(k * paso, c, s);
        zr[k] = e - d * s;
        zi[k] = -(d * c);
        // Z'[m−k]: lo mismo con los papeles cambiados.
        if (q != k) {
            real_t e2 = (pq + pk) / 2, d2 = (pq - pk) / 2;
            giro(q * paso, c, s);
            zr[q] = e2 - d2 * s;
            zi[q] = -(d2 * c);
        }
    }
    fft_compleja(m);
    // z = conj(FFT(conj(Z'))) / m: pares = parte real, impares = imaginaria.
    for (int t = 0; t < cantidad; t++) {
        r[t] = (t % 2 == 0) ? zr[t / 2] / m : -zi[t / 2] / m;
    }
}

}  // namespace fft
