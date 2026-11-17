// estado.cpp — Estado compartido del analizador (traducción de pc/estado.py).

#include "estado.h"
#include "configuracion.h"
#include <mutex>
#include <stdio.h>
#include <string.h>

#ifdef ARDUINO
#include <Arduino.h>
#include <Preferences.h>
#endif

namespace estado {

volatile int valores[CANTIDAD_CAMPOS];
volatile bool pedido_recalibrar = false;

namespace {

// Cantidad de valores posibles de cada campo (van de 0 a cantidad − 1).
// La fuente también: MODO_MIC = 0 y MODO_LINE = 1.
const int CANTIDAD_VALORES[CANTIDAD_CAMPOS] = {
    CANTIDAD_VELOCIDADES, 2, 2, 2, 2, CANTIDAD_FORMAS, CANTIDAD_MODOS_COLOR,
    CANTIDAD_COLORES_FIJOS, 2};

const char* const NOMBRES[CANTIDAD_CAMPOS] = {
    "velocidad", "pausa", "pico", "golpe", "afinador", "forma", "color", "color_fijo", "fuente"};


// Campos que se recuerdan entre una vez y la otra (no pausa ni fuente).
const bool GUARDADO[CANTIDAD_CAMPOS] = {
    true, false, true, true, true, true, true, true, false};

const char* const NOMBRES_VELOCIDADES[] = {"lenta", "normal", "rápida"};
const char* const NOMBRES_FORMAS[] = {"barras", "centro", "onda", "espectrograma"};
const char* const NOMBRES_COLORES[] = {"fijo", "arcoiris", "nota"};
const char* const NOMBRES_COLORES_FIJOS[] = {"celeste", "verde", "naranja", "rosa", "violeta"};

const int MAXIMO_SUSCRIPTORES = 4;
Suscriptor suscriptores[MAXIMO_SUSCRIPTORES];
int cantidad_suscriptores = 0;

// Los cambios llegan de varias tareas (botones, Blynk, audio): de a uno.
std::mutex candado;

char texto_ultimo[40] = "Inicio";
const char* origen_ultimo = nullptr;

bool es_valido(Campo campo, int valor) {
    return campo >= 0 && campo < CANTIDAD_CAMPOS && valor >= 0 && valor < CANTIDAD_VALORES[campo];
}

#ifdef ARDUINO
// Claves en la NVS (máximo 15 letras).
const char* const CLAVES[CANTIDAD_CAMPOS] = {
    "velocidad", "pausa", "pico", "golpe", "afinador", "forma", "color", "color_fijo", "fuente"};
Preferences nvs;
const char* const ESPACIO_NVS = "analizador";
#else
int guardadas[CANTIDAD_CAMPOS];
bool hay_guardada[CANTIDAD_CAMPOS];
#endif

// Escribe los campos guardados. Se llama con el candado tomado.
void guardar_sin_candado() {
#ifdef ARDUINO
    if (!nvs.begin(ESPACIO_NVS, false)) {
        Serial.println("No se pudieron guardar las preferencias");
        return;
    }
    for (int c = 0; c < CANTIDAD_CAMPOS; c++) {
        // putInt solo escribe la flash si el valor cambió.
        if (GUARDADO[c]) nvs.putInt(CLAVES[c], valores[c]);
    }
    nvs.end();
#else
    for (int c = 0; c < CANTIDAD_CAMPOS; c++) {
        if (GUARDADO[c]) {
            guardadas[c] = valores[c];
            hay_guardada[c] = true;
        }
    }
#endif
}

void avisar(const char* texto) {
#ifdef ARDUINO
    Serial.println(texto);
#else
    printf("%s\n", texto);
#endif
}

}  // namespace

void suscribir(Suscriptor funcion) {
    if (cantidad_suscriptores < MAXIMO_SUSCRIPTORES) suscriptores[cantidad_suscriptores++] = funcion;
}

const char* nombre(Campo campo) { return NOMBRES[campo]; }

const char* describir(Campo campo, int valor, char* texto, int largo) {
    switch (campo) {
        case PAUSA:
            snprintf(texto, largo, "Pausa %s", valor ? "activada" : "desactivada");
            break;
        case PICO:
            snprintf(texto, largo, "Peak %s", valor ? "activado" : "desactivado");
            break;
        case GOLPE:
            snprintf(texto, largo, "Golpe %s", valor ? "activado" : "desactivado");
            break;
        case AFINADOR:
            snprintf(texto, largo, "Afinador %s", valor ? "activado" : "desactivado");
            break;
        case VELOCIDAD:
            snprintf(texto, largo, "Caída %s", NOMBRES_VELOCIDADES[valor]);
            break;
        case FORMA:
            snprintf(texto, largo, "Forma: %s", NOMBRES_FORMAS[valor]);
            break;
        case COLOR:
            snprintf(texto, largo, "Color: %s", NOMBRES_COLORES[valor]);
            break;
        case COLOR_FIJO:
            snprintf(texto, largo, "Color fijo: %s", NOMBRES_COLORES_FIJOS[valor]);
            break;
        case FUENTE:
            snprintf(texto, largo, "Fuente: %s", valor == MODO_MIC ? "MIC" : "LINE");
            break;
        default:   // no pasa: todos los campos tienen su caso
            snprintf(texto, largo, "Campo %d: %d", (int)campo, valor);
    }
    return texto;
}

bool cambiar(Campo campo, int valor, const char* origen) {
    if (!es_valido(campo, valor)) {
        char aviso[60];
        snprintf(aviso, sizeof aviso, "Valor inválido para %s: %d",
                 (campo >= 0 && campo < CANTIDAD_CAMPOS) ? NOMBRES[campo] : "?", valor);
        avisar(aviso);
        return false;
    }
    {
        std::lock_guard<std::mutex> llave(candado);
        valores[campo] = valor;
        describir(campo, valor, texto_ultimo, sizeof texto_ultimo);
        origen_ultimo = origen;
        if (GUARDADO[campo]) guardar_sin_candado();
    }
    // Los suscriptores se avisan fuera del candado: así uno lento (Blynk)
    // no frena a los demás.
    for (int i = 0; i < cantidad_suscriptores; i++) suscriptores[i](campo, valor, origen);
    return true;
}

void alternar(Campo campo, const char* origen) { cambiar(campo, 1 - valores[campo], origen); }

void siguiente(Campo campo, const char* origen) {
    cambiar(campo, (valores[campo] + 1) % CANTIDAD_VALORES[campo], origen);
}

void aplicar_accion(int codigo, const char* origen) {
    if (codigo == BOTON_CAIDA) siguiente(VELOCIDAD, origen);
    else if (codigo == BOTON_PAUSA) alternar(PAUSA, origen);
    else if (codigo == BOTON_PICO) alternar(PICO, origen);
    else if (codigo == BOTON_GOLPE) alternar(GOLPE, origen);
    else {
        char aviso[40];
        snprintf(aviso, sizeof aviso, "código desconocido: %d", codigo);
        avisar(aviso);
    }
}

void pedir_recalibracion(const char* origen) {
    std::lock_guard<std::mutex> llave(candado);
    pedido_recalibrar = true;
    snprintf(texto_ultimo, sizeof texto_ultimo, "Recalibrando");
    origen_ultimo = origen;
}

void ultimo_cambio(char* texto, int largo, const char** origen) {
    std::lock_guard<std::mutex> llave(candado);
    snprintf(texto, largo, "%s", texto_ultimo);
    *origen = origen_ultimo;
}

void guardar_preferencias() {
    std::lock_guard<std::mutex> llave(candado);
    guardar_sin_candado();
}

void cargar_preferencias() {
    std::lock_guard<std::mutex> llave(candado);
#ifdef ARDUINO
    // Solo lectura: si nunca se guardó nada, el espacio no existe y begin falla.
    if (!nvs.begin(ESPACIO_NVS, true)) return;
#endif
    for (int c = 0; c < CANTIDAD_CAMPOS; c++) {
        if (!GUARDADO[c]) continue;
        int guardado;
#ifdef ARDUINO
        if (!nvs.isKey(CLAVES[c])) continue;
        guardado = nvs.getInt(CLAVES[c], valores[c]);
#else
        if (!hay_guardada[c]) continue;
        guardado = guardadas[c];
#endif
        // Un valor que ya no es válido (por ejemplo, se sacó una forma) se ignora.
        if (es_valido((Campo)c, guardado)) {
            valores[c] = guardado;
        } else {
            char aviso[60];
            snprintf(aviso, sizeof aviso, "Preferencia ignorada: %s = %d ya no es válido", NOMBRES[c], guardado);
            avisar(aviso);
        }
    }
#ifdef ARDUINO
    nvs.end();
#endif
}

namespace {
// Valores de arranque (los mismos que en pc/estado.py).
void poner_arranque() {
    valores[VELOCIDAD] = VELOCIDAD_INICIAL;
    valores[PAUSA] = 0;
    valores[PICO] = 1;
    valores[GOLPE] = 0;
    valores[AFINADOR] = 0;
    valores[FORMA] = 0;       // barras
    valores[COLOR] = 2;       // nota
    valores[COLOR_FIJO] = 0;
    valores[FUENTE] = FUENTE_AUDIO;
}
// Se ejecuta antes que setup(), al cargar el programa.
struct Arranque {
    Arranque() { poner_arranque(); }
} arranque;
}  // namespace

void reiniciar() {
    std::lock_guard<std::mutex> llave(candado);
    poner_arranque();
    pedido_recalibrar = false;
    snprintf(texto_ultimo, sizeof texto_ultimo, "Inicio");
    origen_ultimo = nullptr;
    cantidad_suscriptores = 0;
}

#ifndef ARDUINO
bool prueba_leer_preferencia(Campo campo, int* valor) {
    if (!hay_guardada[campo]) return false;
    *valor = guardadas[campo];
    return true;
}
void prueba_escribir_preferencia(Campo campo, int valor) {
    guardadas[campo] = valor;
    hay_guardada[campo] = true;
}
void prueba_borrar_preferencias() {
    for (int c = 0; c < CANTIDAD_CAMPOS; c++) hay_guardada[c] = false;
}
#endif

}  // namespace estado
