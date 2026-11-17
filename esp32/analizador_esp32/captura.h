// captura.h — Captura de audio por I2S (reemplaza a pc/captura.py y a la
// parte de principal.py que abría el dispositivo).
//
// Una tarea propia, en el núcleo 1, lee bloques de TAMANO_BLOQUE muestras
// del canal I2S y los pasa a analisis::procesar_bloque(). Abre la fuente
// de estado::FUENTE (MIC o LINE, cada una con sus pines en
// configuracion.h) y, si cambia, cierra el canal y abre el de la otra.
//
// Es lo que en la compu hacían el callback de sounddevice y
// capturar_continuo(): acá no hay hilo principal que mantenga el stream,
// la tarea lee y analiza en un solo bucle.

#pragma once
#include "analisis.h"
#include <stdint.h>

namespace captura {

// Función que recibe cada paquete nuevo para la OLED. Se llama desde la
// tarea de audio: tiene que ser rápida y no dibujar ahí.
typedef void (*AlHaberPaquete)(const analisis::Paquete& paquete);

// Arranca la tarea de audio. Devuelve false si no se pudo crear.
bool iniciar(AlHaberPaquete al_haber_paquete);

// Cuánto tarda el análisis de cada bloque, para ver si entra en los
// ~21,3 ms que dura un bloque. Devuelve los valores desde la última
// llamada y los pone en cero.
void tiempos(uint32_t* promedio_us, uint32_t* maximo_us, uint32_t* bloques, uint32_t* bloques_perdidos);

}  // namespace captura
