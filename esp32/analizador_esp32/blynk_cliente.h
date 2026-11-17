// blynk_cliente.h — Conexión con la app de Blynk (traducción de pc/blynk_cliente.py).
//
// - iniciar() arranca una tarea propia que conecta el WiFi y Blynk,
//   escucha a la app y reconecta si se corta.
// - estado.cpp llama a avisar_cambio() después de cada cambio: el valor
//   se deja en una cola y la tarea de Blynk lo manda (una sola tarea usa
//   la conexión).
// - Cuando el usuario toca algo en la app, se llama a
//   estado::cambiar(campo, valor, "Blynk").
//
// Mismos pines virtuales que en la compu (V0 velocidad … V7 color fijo),
// más V8 para la fuente: en el ESP32 no hay teclado para cambiarla.
//
// El WiFi y el token van en secretos.h (copiar secretos.h.ejemplo). Sin
// ese archivo, el programa compila y anda sin Blynk.

#pragma once

namespace blynk_cliente {

// Arranca la tarea de Blynk. Devuelve false si no hay secretos.h.
bool iniciar();
bool conectado();

}  // namespace blynk_cliente
