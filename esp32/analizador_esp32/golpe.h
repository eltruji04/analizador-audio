// golpe.h — Detector de golpes (bombo) y tempo (traducción de pc/golpe.py).
//
// - Trabaja sobre los dB SIN promediar (el promedio le quita ~6 dB al bombo).
// - Golpe = algún grave (BANDAS_DETECCION_GOLPE) sube más de GOLPE_SUBIDA_DB
//   respecto del bloque anterior y queda a menos de GOLPE_DISTANCIA_TECHO_DB
//   de su techo.
// - Después de un golpe, espera GOLPE_ESPERA segundos antes de aceptar otro.
// - estimar_bpm() calcula el tempo con los momentos de los últimos golpes,
//   que detectar() va anotando.

#pragma once
#include "configuracion.h"

namespace golpe {

// Momentos de los últimos golpes (como el deque de Python con maxlen=64):
// del más viejo al más nuevo.
struct Momentos {
    double valores[BPM_MAXIMO_MOMENTOS];
    int inicio = 0;     // posición del más viejo
    int cantidad = 0;
    void agregar(double momento);
    double operator[](int i) const { return valores[(inicio + i) % BPM_MAXIMO_MOMENTOS]; }
    void borrar() { inicio = 0; cantidad = 0; }
};

extern Momentos momentos;

// true si en este bloque hubo un golpe. db y techo: 16 valores. ahora: en segundos.
bool detectar(const real_t* db, const real_t* techo, double ahora);

// Tempo en BPM, o −1 si no se puede decir (en Python era None).
int estimar_bpm(const Momentos& momentos_golpes, double ahora);

// Vuelve al estado de arranque (para las pruebas).
void reiniciar();

}  // namespace golpe
