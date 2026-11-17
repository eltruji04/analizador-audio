// nota.cpp — Nota que suena y afinador (ver nota.h).

#include "nota.h"
#include "bandas.h"
#include "fft.h"
#include <math.h>
#include <stdlib.h>

namespace nota {

namespace {

constexpr int N = TAMANO_VENTANA;
constexpr int VALORES_ESPECTRO = N / 2 + 1;

// --- Croma ---
// Valores del espectro entre CROMA_FRECUENCIA_MINIMA y _MAXIMA: de
// desde_croma a hasta_croma − 1. clases[k − desde_croma] = nota (0-11).
int desde_croma = 0, hasta_croma = 0;
uint8_t* clases = nullptr;
real_t* potencia_lados = nullptr;   // espectro de los lados (cuando se usan)

// --- Plantillas: 24 acordes (C mayor, C menor, C# mayor…), largo 1 ---
real_t plantillas[24][12];

// --- YIN ---
constexpr int TAU_MINIMO = (int)(FRECUENCIA_MUESTREO / NOTA_FRECUENCIA_MAXIMA);   // 48
// ceil(48000 / 60) = 800; se escribe así porque ceil no es constexpr.
constexpr int TAU_MAXIMO = (FRECUENCIA_MUESTREO + (int)NOTA_FRECUENCIA_MINIMA - 1) / (int)NOTA_FRECUENCIA_MINIMA;
constexpr int LARGO_TAU = TAU_MAXIMO + 2;                       // τ de 0 a TAU_MAXIMO + 1
// En real_t (float en el ESP32): el double lo emula por software y es
// unas 50 veces más lento. La precisión alcanza: r ya viene de una FFT en float.
real_t r[LARGO_TAU];          // autocorrelación
real_t c_inicio[LARGO_TAU];   // c[τ]       = suma de x² de las primeras τ muestras
real_t c_final[LARGO_TAU];    // c[n − τ]
real_t dn[LARGO_TAU];         // diferencia normalizada

// --- Promedios entre bloques (los cambia estimar()) ---
real_t croma_suave[12];
int nota_actual = SIN_NOTA;
int bloques_plana = 0;
int candidata = -1;            // −1 = ninguna (None en Python)
int bloques_candidata = 0;
double frecuencia_suave = NAN; // NAN = sin promedio (None en Python)

// Python redondea los .5 al par (numpy.round y round): nearbyint también.
inline int redondear(double x) { return (int)nearbyint(x); }

real_t cuadrado_medio(const real_t* x, int n) {
    real_t suma = 0;
    for (int i = 0; i < n; i++) suma += x[i] * x[i];
    return suma / n;
}

// Croma que deja una nota con sus primeros 6 armónicos (ver nota.py).
void perfil_armonicos(int nota, double* perfil) {
    for (int i = 0; i < 12; i++) perfil[i] = 0;
    for (int armonico = 1; armonico <= 6; armonico++) {
        int semitonos = redondear(12 * log2((double)armonico));   // 0, 12, 19, 24, 28, 31
        perfil[(nota + semitonos) % 12] += pow(CROMA_DECAIMIENTO_ARMONICOS, 2 * (armonico - 1));
    }
}

void borrar_promedios() {
    for (int i = 0; i < 12; i++) croma_suave[i] = 0;
    nota_actual = SIN_NOTA;
    bloques_plana = 0;
    candidata = -1;
    bloques_candidata = 0;
    frecuencia_suave = NAN;
}

}  // namespace

bool iniciar() {
    if (clases != nullptr) return true;
    if (!fft::iniciar()) return false;
    // Frecuencias igual que numpy.fft.rfftfreq (ver bandas.cpp).
    double separacion = 1.0 / (N * (1.0 / FRECUENCIA_MUESTREO));
    desde_croma = VALORES_ESPECTRO;
    hasta_croma = 0;
    for (int k = 0; k < VALORES_ESPECTRO; k++) {
        double f = k * separacion;
        if (f >= CROMA_FRECUENCIA_MINIMA && f <= CROMA_FRECUENCIA_MAXIMA) {
            if (k < desde_croma) desde_croma = k;
            hasta_croma = k + 1;
        }
    }
    clases = (uint8_t*)malloc(hasta_croma - desde_croma);
    potencia_lados = (real_t*)malloc(VALORES_ESPECTRO * sizeof(real_t));
    if (!clases || !potencia_lados) return false;
    for (int k = desde_croma; k < hasta_croma; k++) {
        double f = k * separacion;
        clases[k - desde_croma] = (uint8_t)(redondear(69 + 12 * log2(f / LA_REFERENCIA)) % 12);
    }

    // Plantillas: raíz + tercera (mayor o menor) + quinta, con armónicos y largo 1.
    for (int raiz = 0; raiz < 12; raiz++) {
        const int terceras[2] = {4, 3};   // mayor, menor
        for (int t = 0; t < 2; t++) {
            double a[12], b[12], c[12], plantilla[12], norma = 0;
            perfil_armonicos(raiz, a);
            perfil_armonicos((raiz + terceras[t]) % 12, b);
            perfil_armonicos((raiz + 7) % 12, c);
            for (int i = 0; i < 12; i++) {
                plantilla[i] = CROMA_PESO_RAIZ * a[i] + b[i] + c[i];
                norma += plantilla[i] * plantilla[i];
            }
            norma = sqrt(norma);
            for (int i = 0; i < 12; i++) plantillas[2 * raiz + t][i] = (real_t)(plantilla[i] / norma);
        }
    }
    borrar_promedios();
    return true;
}

void croma_desde_potencia(const real_t* potencia, real_t* resultado) {
    for (int i = 0; i < 12; i++) resultado[i] = 0;
    for (int k = desde_croma; k < hasta_croma; k++) resultado[clases[k - desde_croma]] += potencia[k];
}

void croma(const real_t* muestras, real_t* resultado) {
    fft::potencia(muestras, bandas::ventana_hann(), N, potencia_lados);
    croma_desde_potencia(potencia_lados, resultado);
}

void puntajes_raiz(const real_t* croma_promediada, real_t* puntajes) {
    real_t norma = 0;
    for (int i = 0; i < 12; i++) norma += croma_promediada[i] * croma_promediada[i];
    norma = sqrt(norma);
    for (int raiz = 0; raiz < 12; raiz++) {
        real_t mejor = -1e30f;
        for (int t = 0; t < 2; t++) {
            real_t parecido = 0;
            for (int i = 0; i < 12; i++) parecido += plantillas[2 * raiz + t][i] * (croma_promediada[i] / norma);
            if (parecido > mejor) mejor = parecido;
        }
        puntajes[raiz] = mejor;
    }
}

void a_nota(double frecuencia, int* nota, double* cents) {
    double midi = 69 + 12 * log2(frecuencia / LA_REFERENCIA);
    int midi_cercano = redondear(midi);
    *cents = (midi - midi_cercano) * 100;
    *nota = midi_cercano % 12;
}

double detectar_frecuencia(const real_t* muestras, int n, double fs, real_t* claridad) {
    // En Python tau_min/tau_max salían de fs; acá fs siempre es
    // FRECUENCIA_MUESTREO y los arreglos tienen el largo justo.
    const int tau_min = TAU_MINIMO, tau_max = TAU_MAXIMO;

    // Sacar la continua.
    real_t media = 0;
    for (int i = 0; i < n; i++) media += muestras[i];
    media /= n;

    // 2. Energía acumulada.
    real_t total = 0;
    for (int i = 0; i < n; i++) {
        real_t x = muestras[i] - media;
        total += x * x;
    }
    // Silencio: sin energía parecería una repetición perfecta. No hay nota.
    if (total == 0) {
        *claridad = 1;
        return -1;
    }
    c_inicio[0] = 0;
    for (int t = 1; t < LARGO_TAU; t++) {
        real_t x = muestras[t - 1] - media;
        c_inicio[t] = c_inicio[t - 1] + x * x;
    }
    c_final[0] = total;
    for (int t = 1; t < LARGO_TAU; t++) {
        real_t x = muestras[n - t] - media;
        c_final[t] = c_final[t - 1] - x * x;
    }

    // 1. Autocorrelación r(τ) con FFT (relleno a 2n).
    fft::autocorrelacion(muestras, media, n, r, LARGO_TAU);

    // d(τ) y 3. normalizada: dn[τ] = d[τ] · τ / (d[1] + … + d[τ]).
    dn[0] = 1;
    real_t acumulada = 0;
    for (int t = 1; t < LARGO_TAU; t++) {
        real_t d = c_final[t] + (total - c_inicio[t]) - 2 * r[t];
        acumulada += d;
        dn[t] = d * t / (acumulada > (real_t)1e-12 ? acumulada : (real_t)1e-12);
    }

    // 4. Primer τ dentro del rango que baje del umbral.
    int k = -1;
    real_t minima = 1e30f;
    for (int t = tau_min; t <= tau_max; t++) {
        if (dn[t] < minima) minima = dn[t];
        if (k < 0 && dn[t] < NOTA_UMBRAL_CLARIDAD) k = t;
    }
    if (k < 0) {
        *claridad = minima;
        return -1;
    }
    while (k < tau_max && dn[k + 1] < dn[k]) k++;   // bajar hasta el fondo del pozo

    // 5. Parábola por los 3 puntos para tener τ con decimales.
    real_t a = dn[k - 1], b = dn[k], c3 = dn[k + 1];
    real_t denominador = a - 2 * b + c3;
    double k_fino = denominador != 0 ? k + 0.5 * (a - c3) / denominador : k;
    *claridad = dn[k];
    return fs / k_fino;
}

Resultado estimar(const real_t* muestras, double fs, int afinador, const real_t* lados,
                  bool misma_ventana) {
    Resultado sin_nota = {SIN_NOTA, NAN, NAN};

    // 1. Puerta de volumen: en silencio no hay nota y se borran los promedios.
    double volumen_db = 10 * log10((double)cuadrado_medio(muestras, N) + 1e-12);
    if (volumen_db < NOTA_VOLUMEN_MINIMO_DB) {
        borrar_promedios();
        return sin_nota;
    }

    if (afinador) {
        // 2. YIN y puerta de claridad.
        real_t claridad;
        double frecuencia = detectar_frecuencia(muestras, N, fs, &claridad);
        if (frecuencia < 0 || claridad > NOTA_UMBRAL_CLARIDAD) {
            frecuencia_suave = NAN;
            return sin_nota;
        }
        // 3. Promedio. Si saltó más de medio semitono, arranca de cero.
        if (isnan(frecuencia_suave) || fabs(1200 * log2(frecuencia / frecuencia_suave)) > 50) {
            frecuencia_suave = frecuencia;
        } else {
            frecuencia_suave = PROMEDIO_AFINADOR * frecuencia_suave + (1 - PROMEDIO_AFINADOR) * frecuencia;
        }
        Resultado resultado;
        resultado.frecuencia = frecuencia_suave;
        a_nota(frecuencia_suave, &resultado.nota, &resultado.cents);
        return resultado;
    }

    // Modo nota: si hay estéreo de verdad, se usan los lados (la voz al
    // centro se cancela). Si los lados están casi vacíos, la mezcla.
    real_t c[12];
    double lados_db = 10 * log10((double)cuadrado_medio(lados, N) + 1e-12);
    if (lados_db - volumen_db > CROMA_UMBRAL_LADOS_DB) {
        croma(lados, c);
    } else if (misma_ventana) {
        croma_desde_potencia(bandas::potencia(), c);   // mismo espectro que las bandas
    } else {
        croma(muestras, c);
    }

    // Croma repartida (suma 1) y promediada entre bloques.
    real_t suma = 0;
    for (int i = 0; i < 12; i++) suma += c[i];
    real_t suma_suave = 0;
    for (int i = 0; i < 12; i++) {
        croma_suave[i] = PROMEDIO_CROMA * croma_suave[i] + (1 - PROMEDIO_CROMA) * (c[i] / suma);
        suma_suave += croma_suave[i];
    }
    real_t reparto_maximo = 0;
    for (int i = 0; i < 12; i++) {
        if (croma_suave[i] / suma_suave > reparto_maximo) reparto_maximo = croma_suave[i] / suma_suave;
    }

    if (reparto_maximo < CROMA_MINIMA) {
        // Croma plana: la nota se apaga recién después de CROMA_ESPERA_SIN_NOTA bloques.
        bloques_plana++;
        if (bloques_plana >= CROMA_ESPERA_SIN_NOTA) nota_actual = SIN_NOTA;
    } else {
        bloques_plana = 0;
        // La nota es la raíz del acorde que mejor coincide.
        real_t puntajes[12];
        puntajes_raiz(croma_suave, puntajes);
        int lider = 0;
        for (int i = 1; i < 12; i++) {
            if (puntajes[i] > puntajes[lider]) lider = i;   // el primero si empatan (numpy.argmax)
        }
        if (nota_actual == SIN_NOTA) {
            nota_actual = lider;
            candidata = -1;
        } else if (lider != nota_actual && puntajes[lider] - puntajes[nota_actual] > CROMA_MARGEN_CAMBIO) {
            // Histéresis: la raíz nueva tiene que ganar CROMA_BLOQUES_CAMBIO bloques seguidos.
            if (lider == candidata) {
                bloques_candidata++;
            } else {
                candidata = lider;
                bloques_candidata = 1;
            }
            if (bloques_candidata >= CROMA_BLOQUES_CAMBIO) {
                nota_actual = lider;
                candidata = -1;
            }
        } else {
            candidata = -1;
        }
    }
    Resultado resultado = {nota_actual, NAN, NAN};
    return resultado;
}

void reiniciar() { borrar_promedios(); }

}  // namespace nota
