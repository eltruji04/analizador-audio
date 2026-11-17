// botones.h — Los 4 pulsadores (traducción de revisarBotones() del Arduino).
//
// Antes, cada botón le mandaba un byte a la compu y la compu llamaba a
// estado.aplicar_accion(). Ahora el ESP32 lo aplica directamente.

#pragma once

namespace botones {

void iniciar();
// Revisa los 4 botones (antirrebote de 50 ms). Se llama en cada vuelta de loop().
void revisar();

}  // namespace botones
