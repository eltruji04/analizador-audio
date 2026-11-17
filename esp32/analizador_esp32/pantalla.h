// pantalla.h — OLED 128x32 y LEDs (traducción de arduino/analizador_oled).
//
// Dibuja lo mismo que el Arduino: las 16 barras (desde el piso o desde el
// centro), la marca de pico, el símbolo de pausa, la fuente (MIC / LINE)
// y la nota. La diferencia es que el paquete ya no llega por el puerto
// serie: lo arma analisis.cpp y lo entrega la tarea de audio.

#pragma once
#include "analisis.h"

namespace pantalla {

// Prepara la OLED y los LEDs y muestra la pantalla de espera.
void iniciar();

// Recibe un paquete nuevo. La llama la tarea de audio: solo lo copia.
void recibir(const analisis::Paquete& paquete);

// Si llegó un paquete desde la última vez, lo dibuja. Se llama en loop().
void atender();

}  // namespace pantalla
