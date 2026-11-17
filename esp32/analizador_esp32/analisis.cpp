// analisis.cpp — Análisis de cada bloque de audio (ver analisis.h).

#include "analisis.h"
#include "bandas.h"
#include "estado.h"
#include "golpe.h"
#include "nota.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

namespace analisis {

namespace {

constexpr int N = TAMANO_VENTANA;

// Últimas N muestras de audio (mono) y de los "lados" del estéreo.
real_t* memoria = nullptr;
real_t* memoria_lados = nullptr;
// Piso y techo de cada banda, en dB.
real_t piso[CANTIDAD_BARRAS], techo[CANTIDAD_BARRAS];
// dB promediados: db_suave (parejo, calibración) y db_barras (sin
// promedio al subir, alturas). hay_promedios = false hasta el primer
// bloque (None en Python).
real_t db_suave[CANTIDAD_BARRAS], db_barras[CANTIDAD_BARRAS];
bool hay_promedios = false;

Resultados res;

// Envío a la OLED.
double ultimo_envio = 0;
bool pausa_enviada = false;

void poner_arranque() {
    if (memoria) memset(memoria, 0, N * sizeof(real_t));
    if (memoria_lados) memset(memoria_lados, 0, N * sizeof(real_t));
    bandas::niveles_iniciales(piso, techo);
    hay_promedios = false;
    for (int b = 0; b < CANTIDAD_BARRAS; b++) {
        res.alturas[b] = 0;
        res.destello[b] = 0;
        res.picos[b] = 0;
    }
    res.nota = SIN_NOTA;
    res.frecuencia = NAN;
    res.cents = NAN;
    res.momento_golpe = NAN;
    res.nivel = -240;
    res.bpm = -1;
    ultimo_envio = 0;
    pausa_enviada = false;
}

}  // namespace

bool iniciar() {
    if (memoria == nullptr) {
        memoria = (real_t*)malloc(N * sizeof(real_t));
        memoria_lados = (real_t*)malloc(N * sizeof(real_t));
        if (!memoria || !memoria_lados) return false;
    }
    if (!bandas::preparar_analisis() || !nota::iniciar()) return false;
    poner_arranque();
    return true;
}

bool procesar_bloque(const real_t* izquierdo, const real_t* derecho, int m, double ahora,
                     Paquete* paquete) {
    // Ventana deslizante: se descartan las m muestras más viejas y el
    // bloque nuevo ocupa las últimas m posiciones. Si es estéreo, la mezcla
    // es el promedio de los canales y los lados, (L − R) / 2.
    memmove(memoria, memoria + m, (N - m) * sizeof(real_t));
    memmove(memoria_lados, memoria_lados + m, (N - m) * sizeof(real_t));
    real_t* mono = memoria + (N - m);
    real_t* lados = memoria_lados + (N - m);
    for (int i = 0; i < m; i++) {
        if (derecho) {
            mono[i] = (izquierdo[i] + derecho[i]) / 2;
            lados[i] = (izquierdo[i] - derecho[i]) / 2;
        } else {
            mono[i] = izquierdo[i];
            lados[i] = 0;
        }
    }

    real_t energias[CANTIDAD_BARRAS], db[CANTIDAD_BARRAS];
    bandas::calcular_bandas(memoria, energias);
    // A decibeles (el silencio da −120 dB).
    for (int b = 0; b < CANTIDAD_BARRAS; b++) db[b] = (real_t)(10 * log10((double)energias[b] + 0.000000000001));

    // Promedio entre bloques. El primer bloque solo los inicializa.
    if (!hay_promedios) {
        memcpy(db_suave, db, sizeof db);
        memcpy(db_barras, db, sizeof db);
        hay_promedios = true;
    } else {
        bandas::promediar(db_suave, db, PROMEDIO_CALIBRACION_DB, PROMEDIO_CALIBRACION_DB);
        bandas::promediar(db_barras, db, PROMEDIO_SUBIDA_DB, PROMEDIO_BAJADA_DB);
    }

    // Recalibración pedida (Monitor Serie, Blynk o cambio de fuente).
    if (estado::pedido_recalibrar) {
        for (int b = 0; b < CANTIDAD_BARRAS; b++) {
            techo[b] = db_suave[b] + RECALIBRAR_MARGEN_DB;
            piso[b] = techo[b] - RECALIBRAR_RANGO_DB;
            res.picos[b] = 0;
        }
        estado::pedido_recalibrar = false;
    }

    // Calibración automática, alturas, suavizado y picos.
    bandas::actualizar_niveles(piso, techo, db_suave);
    real_t alturas[CANTIDAD_BARRAS];
    bandas::a_alturas(db_barras, piso, techo, alturas);
    real_t caida = VELOCIDADES_CAIDA[estado::valor(estado::VELOCIDAD)];
    bandas::suavizar(res.alturas, alturas, caida);
    bandas::actualizar_picos(res.picos, res.alturas);

    // Golpe: el destello baja con la misma caída que las barras. detectar()
    // se llama en todos los bloques, aunque el efecto esté apagado.
    real_t ceros[CANTIDAD_BARRAS] = {0};
    bandas::suavizar(res.destello, ceros, caida);
    if (golpe::detectar(db, techo, ahora) && estado::valor(estado::GOLPE)) {
        for (int i = 0; i < CANTIDAD_BARRAS_GOLPE; i++) res.destello[BARRAS_GOLPE[i]] = ALTURA_MAXIMA;
        res.momento_golpe = ahora;
    }

    // Nota y, con el afinador, frecuencia y cents.
    nota::Resultado r = nota::estimar(memoria, FRECUENCIA_MUESTREO, estado::valor(estado::AFINADOR),
                                      memoria_lados, true);
    res.nota = r.nota;
    res.frecuencia = r.frecuencia;
    res.cents = r.cents;
    res.nivel = bandas::nivel_db(mono, m);
    res.bpm = golpe::estimar_bpm(golpe::momentos, ahora);

    // Paquete: como mucho uno cada INTERVALO_ENVIO. En pausa, solo el
    // primero (con pausa = 1), para que la OLED congele la pantalla.
    int pausa = estado::valor(estado::PAUSA);
    if (ahora - ultimo_envio >= INTERVALO_ENVIO && (pausa == 0 || !pausa_enviada)) {
        for (int b = 0; b < CANTIDAD_BARRAS; b++) {
            real_t salida = res.alturas[b] > res.destello[b] ? res.alturas[b] : res.destello[b];
            int altura = (int)salida;   // int() de Python: corta los decimales
            if (altura < 0) altura = 0;
            if (altura > ALTURA_MAXIMA) altura = ALTURA_MAXIMA;
            paquete->alturas[b] = (uint8_t)altura;
        }
        paquete->fuente = (uint8_t)estado::valor(estado::FUENTE);
        paquete->nota = (uint8_t)res.nota;
        paquete->pausa = (uint8_t)pausa;
        paquete->pico = (uint8_t)estado::valor(estado::PICO);
        paquete->forma_oled = estado::valor(estado::FORMA) == FORMA_CENTRO ? FORMA_OLED_CENTRO : FORMA_OLED_BARRAS;
        ultimo_envio = ahora;
        pausa_enviada = pausa == 1;
        return true;
    }
    return false;
}

void cambio_de_fuente() {
    memset(memoria, 0, N * sizeof(real_t));
    memset(memoria_lados, 0, N * sizeof(real_t));
    hay_promedios = false;
    estado::pedido_recalibrar = true;
}

const Resultados& resultados() { return res; }

void reiniciar() {
    poner_arranque();
    golpe::reiniciar();
    nota::reiniciar();
}

}  // namespace analisis
