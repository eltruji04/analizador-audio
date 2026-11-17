// botones.cpp — Los 4 pulsadores (ver botones.h).

#include "botones.h"
#include "configuracion.h"
#include "estado.h"
#include <Arduino.h>

namespace botones {

namespace {
const int CODIGOS[4] = {BOTON_CAIDA, BOTON_PAUSA, BOTON_PICO, BOTON_GOLPE};
const unsigned long ANTIRREBOTE = 50;
bool ultimaLectura[4] = {HIGH, HIGH, HIGH, HIGH};
bool estadoEstable[4] = {HIGH, HIGH, HIGH, HIGH};
unsigned long ultimoCambio[4] = {0, 0, 0, 0};
}  // namespace

void iniciar() {
    for (int i = 0; i < 4; i++) pinMode(PINES_BOTONES[i], INPUT_PULLUP);   // suelto = HIGH, apretado = LOW
}

void revisar() {
    for (int i = 0; i < 4; i++) {
        bool lectura = digitalRead(PINES_BOTONES[i]);
        if (lectura != ultimaLectura[i]) {
            ultimoCambio[i] = millis();
            ultimaLectura[i] = lectura;
        }
        if (millis() - ultimoCambio[i] > ANTIRREBOTE && lectura != estadoEstable[i]) {
            estadoEstable[i] = lectura;
            // Una sola acción por cada vez que se aprieta.
            if (estadoEstable[i] == LOW) estado::aplicar_accion(CODIGOS[i], "botón");
        }
    }
}

}  // namespace botones
