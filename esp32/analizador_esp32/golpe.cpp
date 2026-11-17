// golpe.cpp — Detector de golpes y tempo (ver golpe.h).

#include "golpe.h"
#include <algorithm>
#include <math.h>

namespace golpe {

Momentos momentos;

namespace {
real_t anterior[CANTIDAD_BARRAS];  // dB del bloque anterior
bool hay_anterior = false;          // false hasta el primer bloque (None en Python)
double ultimo_golpe = -1000;        // muy en el pasado para que el primero valga
}  // namespace

void Momentos::agregar(double momento) {
    if (cantidad < BPM_MAXIMO_MOMENTOS) {
        valores[(inicio + cantidad) % BPM_MAXIMO_MOMENTOS] = momento;
        cantidad++;
    } else {
        // Lleno: se pisa el más viejo, como un deque con maxlen.
        valores[inicio] = momento;
        inicio = (inicio + 1) % BPM_MAXIMO_MOMENTOS;
    }
}

bool detectar(const real_t* db, const real_t* techo, double ahora) {
    // Primer bloque: todavía no hay con qué comparar.
    if (!hay_anterior) {
        for (int b = 0; b < CANTIDAD_BARRAS; b++) anterior[b] = db[b];
        hay_anterior = true;
        return false;
    }
    // Algún grave subió lo suficiente y está cerca de su techo.
    bool alguno = false;
    for (int i = 0; i < CANTIDAD_BANDAS_DETECCION_GOLPE; i++) {
        int g = BANDAS_DETECCION_GOLPE[i];
        real_t subida = db[g] - anterior[g];
        bool cerca = db[g] > techo[g] - GOLPE_DISTANCIA_TECHO_DB;
        if (subida > GOLPE_SUBIDA_DB && cerca) alguno = true;
    }
    // Se actualiza SIEMPRE, antes de cualquier return: si no, durante la
    // espera se compararía contra un bloque viejo.
    for (int b = 0; b < CANTIDAD_BARRAS; b++) anterior[b] = db[b];

    // Espera entre golpes: evita contar dos veces el mismo bombo.
    if (ahora - ultimo_golpe < GOLPE_ESPERA) return false;
    if (alguno) {
        ultimo_golpe = ahora;
        momentos.agregar(ahora);
        return true;
    }
    return false;
}

int estimar_bpm(const Momentos& momentos_golpes, double ahora) {
    // Solo los golpes de los últimos BPM_VENTANA segundos.
    double recientes[BPM_MAXIMO_MOMENTOS];
    int cantidad = 0;
    for (int i = 0; i < momentos_golpes.cantidad; i++) {
        if (ahora - momentos_golpes[i] <= BPM_VENTANA) recientes[cantidad++] = momentos_golpes[i];
    }
    if (cantidad < BPM_MINIMO_GOLPES) return -1;
    if (ahora - recientes[cantidad - 1] > BPM_SIN_GOLPES) return -1;

    int cantidad_intervalos = cantidad - 1;
    double intervalos[BPM_MAXIMO_MOMENTOS];
    double ordenados[BPM_MAXIMO_MOMENTOS];
    for (int i = 0; i < cantidad_intervalos; i++) {
        intervalos[i] = recientes[i + 1] - recientes[i];
        ordenados[i] = intervalos[i];
    }
    std::sort(ordenados, ordenados + cantidad_intervalos);
    // Mediana "baja": el intervalo del medio de la lista ordenada (ver golpe.py).
    double mediana = ordenados[(cantidad_intervalos - 1) / 2];
    if (mediana <= 0) return -1;
    // Promedio de los intervalos cercanos a la mediana (nunca queda vacío).
    double suma = 0;
    int cercanos = 0;
    for (int i = 0; i < cantidad_intervalos; i++) {
        if (fabs(intervalos[i] - mediana) <= BPM_TOLERANCIA * mediana) {
            suma += intervalos[i];
            cercanos++;
        }
    }
    double intervalo = suma / cercanos;
    if (!isfinite(intervalo) || intervalo <= 0) return -1;
    double bpm = 60 / intervalo;
    while (bpm < BPM_MINIMO) bpm *= 2;
    while (bpm >= BPM_MAXIMO) bpm /= 2;
    // round() de Python redondea los .5 al par: nearbyint hace lo mismo.
    return (int)nearbyint(bpm);
}

void reiniciar() {
    hay_anterior = false;
    ultimo_golpe = -1000;
    momentos.borrar();
}

}  // namespace golpe
