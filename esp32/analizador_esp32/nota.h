// nota.h — Nota que suena y afinador (traducción de pc/nota.py).
//
// analisis.cpp llama a estimar() en cada bloque. Dos formas, según el afinador:
// - Afinador activo: detectar_frecuencia() busca el período de la onda con
//   el método YIN y a_nota() lo pasa a nota y cents. La frecuencia se
//   promedia para que no tiemble.
// - Afinador apagado (modo nota): croma() suma la energía del espectro en
//   las 12 notas y puntajes_raiz() la compara con plantillas de acordes; la
//   nota es la raíz del acorde. Si hay estéreo, usa los lados (L − R) para
//   ignorar la voz, que va al centro.
// En los dos, debajo de NOTA_VOLUMEN_MINIMO_DB no hay nota.

#pragma once
#include "configuracion.h"

namespace nota {

// Reserva memoria y arma las plantillas. Se llama una vez, después de
// bandas::preparar_analisis(). Devuelve false si no hay memoria.
bool iniciar();

// Croma de las muestras (TAMANO_VENTANA, mono): 12 valores (C…B).
void croma(const real_t* muestras, real_t* resultado);
// Lo mismo pero a partir de la potencia del espectro ya calculada
// (la de bandas::potencia(), que usa la misma ventana).
void croma_desde_potencia(const real_t* potencia, real_t* resultado);

// 12 puntajes de 0 a 1: cuánto se parece la croma a un acorde con cada raíz.
void puntajes_raiz(const real_t* croma_promediada, real_t* puntajes);

// Frecuencia en Hz → nota (0 a 11) y cents (−50 a +50).
void a_nota(double frecuencia, int* nota, double* cents);

// YIN. Devuelve la frecuencia en Hz, o −1 si no hay una nota clara (None
// en Python). En `claridad` deja 0 = repetición perfecta … ~1 = nada.
double detectar_frecuencia(const real_t* muestras, int n, double fs, real_t* claridad);

// Resultado de estimar(): la nota (0 a 11 o SIN_NOTA) y, solo con el
// afinador, la frecuencia promediada y los cents (NAN si no hay).
struct Resultado {
    int nota;
    double frecuencia;
    double cents;
};

// muestras: últimas TAMANO_VENTANA muestras (mono). lados: lo mismo de
// (L − R) / 2 (ceros si es mono). misma_ventana: true si bandas acaba de
// analizar estas mismas `muestras` (así la croma reutiliza su espectro).
Resultado estimar(const real_t* muestras, double fs, int afinador, const real_t* lados,
                  bool misma_ventana);

// Vuelve al estado de arranque (para las pruebas).
void reiniciar();

}  // namespace nota
