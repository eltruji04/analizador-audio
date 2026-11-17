// estado.h — Estado compartido del analizador (traducción de pc/estado.py).
//
// El ESP32 es el único dueño del estado. Los botones, el Monitor Serie y
// Blynk solo piden cambios, siempre con estado::cambiar() (o
// estado::aplicar_accion() para los códigos de botón).
//
// Diferencias con la compu:
// - Los campos son números: forma y color se guardan como índice de su
//   lista (en Python eran textos).
// - Las preferencias se guardan en la memoria flash (NVS) en vez de un
//   archivo JSON.
// - cambiar() se puede llamar desde cualquier tarea: tiene un candado.

#pragma once
#include <stdint.h>

namespace estado {

enum Campo {
    VELOCIDAD, PAUSA, PICO, GOLPE, AFINADOR, FORMA, COLOR, COLOR_FIJO, FUENTE,
    CANTIDAD_CAMPOS
};

// Valores actuales. Leer siempre con estado::valor() o directamente (son
// int: leerlos desde otra tarea es seguro).
extern volatile int valores[CANTIDAD_CAMPOS];

// true = se pidió recalibrar y la tarea de audio todavía no lo atendió.
extern volatile bool pedido_recalibrar;

// Funciones que se llaman después de cada cambio, con (campo, valor, origen).
typedef void (*Suscriptor)(Campo campo, int valor, const char* origen);
void suscribir(Suscriptor funcion);

inline int valor(Campo campo) { return valores[campo]; }

// Nombre corto del campo ("velocidad", "pausa"...), para los mensajes.
const char* nombre(Campo campo);

// Texto corto de un cambio: "Peak activado", "Forma: onda"…
// Escribe en `texto` (de `largo` bytes) y lo devuelve.
const char* describir(Campo campo, int valor, char* texto, int largo);

// Única forma de cambiar el estado. Devuelve false (y no cambia nada) si
// el valor no es válido para ese campo (en Python era ValueError).
bool cambiar(Campo campo, int valor, const char* origen);

void alternar(Campo campo, const char* origen);   // 0 ↔ 1
void siguiente(Campo campo, const char* origen);  // siguiente valor, y vuelve al primero
void aplicar_accion(int codigo, const char* origen);  // códigos BOTON_* (1 a 4)
void pedir_recalibracion(const char* origen);

// Último cambio, para mostrarlo por el Monitor Serie: texto y origen.
void ultimo_cambio(char* texto, int largo, const char** origen);

// Preferencias guardadas (velocidad, pico, golpe, afinador, forma, color,
// color fijo). La pausa y la fuente no se guardan, igual que en la compu.
void guardar_preferencias();
void cargar_preferencias();

// Solo para las pruebas en la compu: vuelve todo a los valores de arranque.
void reiniciar();

#ifndef ARDUINO
// En la compu no hay NVS: las preferencias viven en memoria y las pruebas
// las leen y escriben con estas funciones.
bool prueba_leer_preferencia(Campo campo, int* valor);
void prueba_escribir_preferencia(Campo campo, int valor);
void prueba_borrar_preferencias();
#endif

}  // namespace estado
