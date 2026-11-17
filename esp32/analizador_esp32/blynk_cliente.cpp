// blynk_cliente.cpp — Conexión con la app de Blynk (ver blynk_cliente.h).
//
// Necesita la librería "Blynk" (de Volodymyr Shymanskyy) instalada en el
// Arduino IDE. BlynkSimpleEsp32.h crea el objeto global Blynk: por eso se
// incluye solo en este archivo.

#include "blynk_cliente.h"
#include "configuracion.h"
#include "estado.h"
#include <Arduino.h>
#include <string.h>

#if __has_include("secretos.h")
#include "secretos.h"
#define HAY_SECRETOS 1
#endif

#ifdef HAY_SECRETOS

#include <WiFi.h>
#include <WiFiClient.h>
#include <BlynkSimpleEsp32.h>

namespace blynk_cliente {

namespace {

// Pin virtual de cada campo (mismo orden que estado::Campo).
const int PINES[estado::CANTIDAD_CAMPOS] = {0, 1, 2, 3, 4, 5, 6, 7, 8};
// Segundos que se espera antes de reintentar la conexión con Blynk.
const uint32_t ESPERA_RECONEXION_MS = 5000;

struct Pendiente {
    int pin;
    int valor;
};
QueueHandle_t pendientes = nullptr;
volatile bool esta_conectado = false;

void encolar(estado::Campo campo, int valor) {
    Pendiente p = {PINES[campo], valor};
    xQueueSend(pendientes, &p, 0);   // si la cola está llena, se pierde (al reconectar se manda todo)
}

// Se llama después de cada cambio del estado, desde la tarea que lo hizo.
void avisar_cambio(estado::Campo campo, int valor, const char* origen) {
    if (strcmp(origen, "Blynk") == 0) return;   // la app ya lo tiene
    encolar(campo, valor);
}

void al_recibir(estado::Campo campo, int valor) {
    if (!estado::cambiar(campo, valor, "Blynk")) {
        Serial.printf("Blynk mandó un valor inválido para %s: %d\n", estado::nombre(campo), valor);
    }
}

void tarea_blynk(void*) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_NOMBRE, WIFI_CLAVE);
    Blynk.config(BLYNK_AUTH_TOKEN);
    for (;;) {
        // El WiFi se reconecta solo; mientras tanto, se espera.
        if (WiFi.status() != WL_CONNECTED) {
            esta_conectado = false;
            vTaskDelay(pdMS_TO_TICKS(500));
            continue;
        }
        if (!Blynk.connected()) {
            if (!Blynk.connect(3000)) {
                esta_conectado = false;
                Serial.println("Blynk: no se pudo conectar, reintento en 5 s");
                vTaskDelay(pdMS_TO_TICKS(ESPERA_RECONEXION_MS));
                continue;
            }
        }
        // Primero se manda todo lo que dejó avisar_cambio()…
        Pendiente p;
        while (Blynk.connected() && xQueueReceive(pendientes, &p, 0) == pdTRUE) {
            Blynk.virtualWrite(p.pin, p.valor);
        }
        // …y después se escucha a Blynk.
        Blynk.run();
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

}  // namespace

bool iniciar() {
    pendientes = xQueueCreate(32, sizeof(Pendiente));
    if (pendientes == nullptr) return false;
    estado::suscribir(avisar_cambio);
    // Núcleo 0, junto al WiFi; el audio está en el 1.
    return xTaskCreatePinnedToCore(tarea_blynk, "blynk", 8192, nullptr, 1, nullptr, 0) == pdPASS;
}

bool conectado() { return esta_conectado; }

}  // namespace blynk_cliente

// --- Lo que llega desde la app (corre dentro de Blynk.run()) ---

// Blynk aceptó el token: se le manda el estado completo, porque el ESP32
// es el dueño y la app tiene que mostrar lo que hay ahora.
BLYNK_CONNECTED() {
    blynk_cliente::esta_conectado = true;
    Serial.println("Blynk conectado");
    for (int c = 0; c < estado::CANTIDAD_CAMPOS; c++) {
        blynk_cliente::encolar((estado::Campo)c, estado::valor((estado::Campo)c));
    }
}

BLYNK_DISCONNECTED() {
    blynk_cliente::esta_conectado = false;
    Serial.println("Blynk desconectado");
}

// La forma y el color llegan como índice de su lista (el Menu manda 0, 1, 2…).
BLYNK_WRITE(V0) { blynk_cliente::al_recibir(estado::VELOCIDAD, param.asInt()); }
BLYNK_WRITE(V1) { blynk_cliente::al_recibir(estado::PAUSA, param.asInt()); }
BLYNK_WRITE(V2) { blynk_cliente::al_recibir(estado::PICO, param.asInt()); }
BLYNK_WRITE(V3) { blynk_cliente::al_recibir(estado::GOLPE, param.asInt()); }
BLYNK_WRITE(V4) { blynk_cliente::al_recibir(estado::AFINADOR, param.asInt()); }
BLYNK_WRITE(V5) { blynk_cliente::al_recibir(estado::FORMA, param.asInt()); }
BLYNK_WRITE(V6) { blynk_cliente::al_recibir(estado::COLOR, param.asInt()); }
BLYNK_WRITE(V7) { blynk_cliente::al_recibir(estado::COLOR_FIJO, param.asInt()); }
BLYNK_WRITE(V8) { blynk_cliente::al_recibir(estado::FUENTE, param.asInt()); }

#else  // sin secretos.h: sin WiFi ni Blynk

namespace blynk_cliente {
bool iniciar() { return false; }
bool conectado() { return false; }
}  // namespace blynk_cliente

#endif
