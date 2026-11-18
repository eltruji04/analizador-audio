// pruebas_unidad.cpp — Pruebas del análisis del ESP32, corridas en la compu.
//
// Son las mismas ideas que los __main__ de pc/*.py: tonos en cada banda,
// valores conocidos de nivel_db, casos de promediar, estado y preferencias,
// tempo y notas. Además se compara la FFT contra una DFT hecha a mano.
//
// Se compila y corre con esp32/pruebas/correr_pruebas.sh.

#include "../analizador_esp32/analisis.h"
#include "../analizador_esp32/bandas.h"
#include "../analizador_esp32/estado.h"
#include "../analizador_esp32/fft.h"
#include "../analizador_esp32/golpe.h"
#include "../analizador_esp32/nota.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <vector>

static int errores = 0;

static void revisar(bool bien, const char* nombre, const char* detalle) {
    if (!bien) errores++;
    printf("%s %-52s %s\n", bien ? "OK   " : "ERROR", nombre, detalle);
}

// --- FFT contra una DFT directa ---------------------------------------
static void pruebas_fft() {
    printf("\n--- FFT ---\n");
    srand(1);
    for (int n : {16, 256, 4096}) {
        std::vector<real_t> x(n), ventana(n), pot(n / 2 + 1);
        for (int i = 0; i < n; i++) {
            x[i] = (real_t)(rand() / (double)RAND_MAX * 2 - 1);
            ventana[i] = (real_t)(0.5 - 0.5 * cos(2 * M_PI * i / (n - 1)));
        }
        fft::potencia(x.data(), ventana.data(), n, pot.data());
        double error = 0, escala = 0;
        for (int k = 0; k <= n / 2; k++) {
            double re = 0, im = 0;
            for (int i = 0; i < n; i++) {
                re += x[i] * ventana[i] * cos(2 * M_PI * k * i / n);
                im -= x[i] * ventana[i] * sin(2 * M_PI * k * i / n);
            }
            double esperado = re * re + im * im;
            error = fmax(error, fabs(pot[k] - esperado));
            escala = fmax(escala, esperado);
        }
        char detalle[80];
        snprintf(detalle, sizeof detalle, "error relativo %.1e", error / escala);
        char nombre[60];
        snprintf(nombre, sizeof nombre, "potencia() = DFT directa, n = %d", n);
        revisar(error / escala < 1e-4, nombre, detalle);
    }
    for (int n : {64, 4096}) {
        std::vector<real_t> x(n);
        for (int i = 0; i < n; i++) x[i] = (real_t)(rand() / (double)RAND_MAX * 2 - 1 + 0.3);
        double media = 0;
        for (int i = 0; i < n; i++) media += x[i];
        media /= n;
        int cantidad = n < 802 ? n : 802;
        std::vector<real_t> r(cantidad);
        fft::autocorrelacion(x.data(), (real_t)media, n, r.data(), cantidad);
        double error = 0, escala = 0;
        for (int t = 0; t < cantidad; t++) {
            double esperado = 0;
            for (int i = 0; i + t < n; i++) esperado += (x[i] - media) * (x[i + t] - media);
            error = fmax(error, fabs(r[t] - esperado));
            escala = fmax(escala, fabs(esperado));
        }
        char detalle[80], nombre[60];
        snprintf(detalle, sizeof detalle, "error relativo %.1e", error / escala);
        snprintf(nombre, sizeof nombre, "autocorrelacion() = suma directa, n = %d", n);
        revisar(error / escala < 1e-4, nombre, detalle);
    }
}

// --- Bandas -------------------------------------------------------------
static void pruebas_bandas() {
    printf("\n--- Bandas ---\n");
    const int n = TAMANO_VENTANA;
    std::vector<real_t> tono(n);
    real_t energias[CANTIDAD_BARRAS];
    int aciertos = 0;
    for (int b = 0; b < CANTIDAD_BARRAS; b++) {
        double f = sqrt(BANDAS[b][0] * BANDAS[b][1]);   // centro "logarítmico"
        for (int i = 0; i < n; i++) tono[i] = (real_t)sin(2 * M_PI * f * i / FRECUENCIA_MUESTREO);
        bandas::calcular_bandas(tono.data(), energias);
        int ganadora = 0;
        for (int k = 1; k < CANTIDAD_BARRAS; k++) if (energias[k] > energias[ganadora]) ganadora = k;
        if (ganadora == b) aciertos++;
    }
    char detalle[40];
    snprintf(detalle, sizeof detalle, "%d de 16", aciertos);
    revisar(aciertos == 16, "tono en el centro de cada banda → gana esa banda", detalle);

    // Valores del espectro por banda con n = 4096 (los de bandas.py).
    const int esperados[CANTIDAD_BARRAS] = {2, 2, 4, 5, 7, 11, 18, 24, 34, 56, 77, 115, 175, 252, 366, 555};
    bool iguales = true;
    char lista[200] = "";
    for (int b = 0; b < CANTIDAD_BARRAS; b++) {
        int d, h;
        bandas::rango_banda(b, &d, &h);
        if (h - d != esperados[b]) iguales = false;
        char numero[8];
        snprintf(numero, sizeof numero, "%d ", h - d);
        strncat(lista, numero, sizeof lista - strlen(lista) - 1);
    }
    revisar(iguales, "valores del espectro por banda (como numpy)", lista);

    // nivel_db: valores conocidos.
    std::vector<real_t> cuadrada(1024), seno(1024), silencio(1024, 0);
    for (int i = 0; i < 1024; i++) {
        cuadrada[i] = i % 2 == 0 ? 1 : -1;
        seno[i] = (real_t)sin(2 * M_PI * 440 * i / FRECUENCIA_MUESTREO);
    }
    struct { const char* nombre; std::vector<real_t> m; double escala, esperado; } casos[] = {
        {"nivel_db: cuadrada ±1 → 0 dB", cuadrada, 1, 0.0},
        {"nivel_db: cuadrada ±0,5 → −6 dB", cuadrada, 0.5, -6.02},
        {"nivel_db: seno de amplitud 1 → −3 dB", seno, 1, -3.01},
        {"nivel_db: silencio → −240 dB", silencio, 1, -240.0},
    };
    for (auto& c : casos) {
        for (auto& v : c.m) v = (real_t)(v * c.escala);
        real_t obtenido = bandas::nivel_db(c.m.data(), 1024);
        snprintf(detalle, sizeof detalle, "%.2f (esperado %.2f)", obtenido, c.esperado);
        revisar(fabs(obtenido - c.esperado) < 0.05, c.nombre, detalle);
    }

    // promediar(db_suave, db, subida, bajada), con una sola banda usada.
    struct { const char* nombre; real_t anterior, nuevo, subida, bajada, esperado; } promedios[] = {
        {"promediar: sin promedio al subir toma el nuevo", -40, -10, 0.0, 0.7, -10},
        {"promediar: al bajar promedia con 0,7", -10, -40, 0.0, 0.7, -19},
        {"promediar: parejo 0,7 al subir", -40, -10, 0.7, 0.7, -31},
        {"promediar: igual que antes no cambia", -20, -20, 0.0, 0.7, -20},
    };
    for (auto& p : promedios) {
        real_t suave[CANTIDAD_BARRAS], db[CANTIDAD_BARRAS];
        for (int b = 0; b < CANTIDAD_BARRAS; b++) { suave[b] = p.anterior; db[b] = p.nuevo; }
        bandas::promediar(suave, db, p.subida, p.bajada);
        snprintf(detalle, sizeof detalle, "%.2f (esperado %.2f)", suave[0], p.esperado);
        revisar(fabs(suave[0] - p.esperado) < 1e-4, p.nombre, detalle);
    }
}

// --- Estado y preferencias ---------------------------------------------
static int avisos = 0;
static void contar_aviso(estado::Campo, int, const char*) { avisos++; }

static void pruebas_estado() {
    printf("\n--- Estado ---\n");
    estado::reiniciar();
    estado::prueba_borrar_preferencias();
    char detalle[80];

    int vistas[5];
    for (int i = 0; i < 5; i++) {
        vistas[i] = estado::valor(estado::VELOCIDAD);
        estado::aplicar_accion(BOTON_CAIDA, "botón");
    }
    snprintf(detalle, sizeof detalle, "%d %d %d %d %d", vistas[0], vistas[1], vistas[2], vistas[3], vistas[4]);
    revisar(vistas[0] == 1 && vistas[1] == 2 && vistas[2] == 0 && vistas[3] == 1, "la velocidad avanza y vuelve a 0", detalle);

    estado::aplicar_accion(BOTON_PAUSA, "botón");
    int p1 = estado::valor(estado::PAUSA);
    estado::aplicar_accion(BOTON_PAUSA, "botón");
    snprintf(detalle, sizeof detalle, "%d → %d", p1, estado::valor(estado::PAUSA));
    revisar(p1 == 1 && estado::valor(estado::PAUSA) == 0, "la pausa alterna", detalle);

    int forma = estado::valor(estado::FORMA);
    bool aceptado = estado::cambiar(estado::FORMA, 7, "compu");
    revisar(!aceptado && estado::valor(estado::FORMA) == forma, "forma inválida: no cambia nada", "");

    estado::suscribir(contar_aviso);
    estado::alternar(estado::GOLPE, "compu");
    revisar(avisos == 1, "los suscriptores se enteran del cambio", "");

    // Preferencias.
    estado::cambiar(estado::FORMA, 2, "compu");
    estado::cambiar(estado::COLOR_FIJO, 3, "compu");
    int f = -1, c = -1;
    estado::prueba_leer_preferencia(estado::FORMA, &f);
    estado::prueba_leer_preferencia(estado::COLOR_FIJO, &c);
    snprintf(detalle, sizeof detalle, "forma %d, color fijo %d", f, c);
    revisar(f == 2 && c == 3, "cambiar() guarda forma y color fijo", detalle);

    estado::cambiar(estado::PAUSA, 1, "compu");
    estado::cambiar(estado::FUENTE, MODO_LINE, "compu");
    int v;
    bool hay = estado::prueba_leer_preferencia(estado::PAUSA, &v) || estado::prueba_leer_preferencia(estado::FUENTE, &v);
    revisar(!hay, "no se guardan pausa ni fuente", "");

    estado::reiniciar();
    estado::prueba_escribir_preferencia(estado::FORMA, 3);
    estado::prueba_escribir_preferencia(estado::VELOCIDAD, 2);
    estado::cargar_preferencias();
    snprintf(detalle, sizeof detalle, "forma %d, velocidad %d", estado::valor(estado::FORMA), estado::valor(estado::VELOCIDAD));
    revisar(estado::valor(estado::FORMA) == 3 && estado::valor(estado::VELOCIDAD) == 2, "cargar_preferencias() aplica los campos", detalle);

    estado::reiniciar();
    estado::prueba_escribir_preferencia(estado::FORMA, 9);
    estado::prueba_escribir_preferencia(estado::VELOCIDAD, 7);
    estado::cargar_preferencias();
    revisar(estado::valor(estado::FORMA) == 0 && estado::valor(estado::VELOCIDAD) == VELOCIDAD_INICIAL,
            "valores inválidos se ignoran", "");
    estado::reiniciar();
    estado::prueba_borrar_preferencias();
}

// --- Tempo ---------------------------------------------------------------
static void pruebas_tempo() {
    printf("\n--- Tempo ---\n");
    struct { const char* nombre; std::vector<double> golpes; double ahora; int esperado; } casos[] = {
        {"120 BPM parejo", {0, 0.5, 1, 1.5, 2, 2.5}, 2.6, 120},
        {"60 BPM se dobla a 120", {0, 1, 2, 3, 4}, 4.1, 120},
        {"240 BPM se divide a 120", {0, .25, .5, .75, 1, 1.25}, 1.3, 120},
        {"golpes de a bloques (0,49 / 0,51)", {0, 0.49, 1.0, 1.49, 2.0, 2.49, 3.0}, 3.1, 120},
        {"un golpe perdido no cambia el tempo", {0, 0.5, 1, 2, 2.5, 3}, 3.1, 120},
        {"menos de 4 golpes → sin tempo", {0, 0.5, 1}, 1.1, -1},
        {"3 s sin golpes → sin tempo", {0, 0.5, 1, 1.5}, 5, -1},
        {"dos grupos 0,25 y 0,75 (mediana baja)", {0, .25, 1, 1.25, 2, 2.25, 3}, 3.1, 120},
    };
    for (auto& c : casos) {
        golpe::Momentos m;
        for (double g : c.golpes) m.agregar(g);
        int bpm = golpe::estimar_bpm(m, c.ahora);
        char detalle[40];
        snprintf(detalle, sizeof detalle, "%d (esperado %d)", bpm, c.esperado);
        revisar(bpm == c.esperado, c.nombre, detalle);
    }
}

// --- Nota ----------------------------------------------------------------
static void pruebas_nota() {
    printf("\n--- Nota ---\n");
    int nota;
    double cents;
    char detalle[80];
    nota::a_nota(440, &nota, &cents);
    snprintf(detalle, sizeof detalle, "nota %d, %.1f cents", nota, cents);
    revisar(nota == 9 && fabs(cents) < 0.01, "a_nota(440) → A, 0 cents", detalle);
    nota::a_nota(261.63 * pow(2, 20 / 1200.0), &nota, &cents);
    snprintf(detalle, sizeof detalle, "nota %d, %.1f cents", nota, cents);
    revisar(nota == 0 && fabs(cents - 20) < 0.1, "a_nota(C4 + 20 cents) → C, +20", detalle);

    const int n = TAMANO_VENTANA;
    std::vector<real_t> x(n);
    for (double f : {65.41, 82.41, 110.0, 196.0, 440.0, 987.77}) {
        // Tono con armónicos, como un instrumento.
        for (int i = 0; i < n; i++) {
            double t = (double)i / FRECUENCIA_MUESTREO;
            x[i] = (real_t)(0.5 * sin(2 * M_PI * f * t) + 0.25 * sin(2 * M_PI * 2 * f * t) + 0.12 * sin(2 * M_PI * 3 * f * t));
        }
        real_t claridad;
        double obtenida = nota::detectar_frecuencia(x.data(), n, FRECUENCIA_MUESTREO, &claridad);
        double error_cents = obtenida > 0 ? 1200 * log2(obtenida / f) : 9999;
        snprintf(detalle, sizeof detalle, "%.2f Hz (%.2f cents), claridad %.3f", obtenida, error_cents, claridad);
        char nombre[60];
        snprintf(nombre, sizeof nombre, "YIN: %.2f Hz con armónicos", f);
        revisar(fabs(error_cents) < 2, nombre, detalle);
    }
    for (int i = 0; i < n; i++) x[i] = 0;
    real_t claridad;
    double silencio = nota::detectar_frecuencia(x.data(), n, FRECUENCIA_MUESTREO, &claridad);
    revisar(silencio < 0, "YIN: silencio → sin nota", "");
    srand(7);
    for (int i = 0; i < n; i++) x[i] = (real_t)(rand() / (double)RAND_MAX - 0.5);
    double ruido = nota::detectar_frecuencia(x.data(), n, FRECUENCIA_MUESTREO, &claridad);
    snprintf(detalle, sizeof detalle, "claridad %.2f", claridad);
    revisar(ruido < 0, "YIN: ruido blanco → sin nota", detalle);
}

int main() {
    if (!analisis::iniciar()) {
        printf("No se pudo reservar memoria\n");
        return 1;
    }
#ifdef ANALISIS_DOUBLE
    printf("Pruebas con double\n");
#else
    printf("Pruebas con float (como en el ESP32)\n");
#endif
    pruebas_fft();
    pruebas_bandas();
    pruebas_estado();
    pruebas_tempo();
    pruebas_nota();
    printf("\n%s\n", errores == 0 ? "Todo bien" : "Hay errores");
    printf("errores: %d\n", errores);
    return errores == 0 ? 0 : 1;
}
