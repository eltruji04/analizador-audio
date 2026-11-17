// pantalla.cpp — OLED 128x32 y LEDs (ver pantalla.h).
//
// El dibujo es el mismo de arduino/analizador_oled/analizador_oled.ino.

#include "pantalla.h"
#include "configuracion.h"
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Arduino.h>
#include <Wire.h>

namespace pantalla {

namespace {

constexpr int ANCHO = 128;
constexpr int ALTO = 32;
Adafruit_SSD1306 display(ANCHO, ALTO, &Wire, -1);
bool hay_display = false;

// --- Paquete compartido con la tarea de audio ---
portMUX_TYPE candado = portMUX_INITIALIZER_UNLOCKED;
analisis::Paquete compartido;
bool hay_nuevo = false;

// --- Lo que antes llegaba por el puerto serie ---
byte niveles[16];   // altura de cada barra (0 - 16)
byte modo = 0;      // 0 = MIC y 1 = LINE
byte nota = 12;     // 0 a 11 = nota o 12 = sin nota
byte pausa = 0;
byte pico = 0;
byte centro = 0;    // 0 = barras y 1 = modo centro

// --- Marca de pico (la calcula la pantalla, como el Arduino) ---
byte alturaPico[16];
byte caidaPico = 0;
const byte PICO_CAIDA = 3;   // los picos bajan 1 nivel cada 3 paquetes

const char* const NOTAS[13] = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B", "-"};

// --- Apariencia ---
const byte NUM_BARRAS = 16;
const byte BARRA_ANCHO = 5;
const byte BARRA_PASO = 6;
const byte SEG_ALTO = 2;
const byte SEG_HUECO = 0;
const byte CENTRO_Y = 16;

const byte DIV_X = 99, DIV_Y = 2, DIV_W = 1, DIV_H = 28;
const byte TEXTO_X = 103;
const byte TEXTO_Y = 3;
const byte SEP_Y = 11;
const byte SEP_W = 22;
const byte NOTA_X1 = 109;
const byte NOTA_X2 = 103;
const byte NOTA_Y = 14;

void simbolo_pausa() {
    display.fillCircle(48, 16, 17, SSD1306_BLACK);
    display.drawCircle(48, 16, 15, SSD1306_WHITE);
    display.drawCircle(48, 16, 14, SSD1306_WHITE);
    display.fillRect(44, 10, 3, 13, SSD1306_WHITE);
    display.fillRect(50, 10, 3, 13, SSD1306_WHITE);
}

void pantalla_inicial() {
    display.clearDisplay();
    display.fillRect(DIV_X, DIV_Y, DIV_W, DIV_H, SSD1306_WHITE);
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(TEXTO_X, TEXTO_Y);
    display.print(F("----"));
    display.drawFastHLine(TEXTO_X, SEP_Y, SEP_W, SSD1306_WHITE);
    display.setTextSize(2);
    display.setCursor(NOTA_X1, NOTA_Y);
    display.print(F("-"));
    display.display();
}

// Lo que hacía procesarByte() con un paquete completo.
void tomar_paquete(const analisis::Paquete& p) {
    for (byte i = 0; i < 16; i++) niveles[i] = p.alturas[i] / 2;   // píxeles (0-32) → niveles (0-16)
    modo = p.fuente;
    nota = p.nota;
    pausa = p.pausa;
    pico = p.pico;
    centro = p.forma_oled;

    // Picos: suben de inmediato y bajan despacio.
    bool bajar = (++caidaPico >= PICO_CAIDA);
    if (bajar) caidaPico = 0;
    for (byte i = 0; i < 16; i++) {
        if (niveles[i] >= alturaPico[i]) alturaPico[i] = niveles[i];
        else if (bajar && alturaPico[i] > 0) alturaPico[i]--;
    }
}

void dibujar_pantalla() {
    // LEDs: siempre hay uno solo encendido.
    digitalWrite(PIN_LED_LINE, modo == MODO_LINE ? HIGH : LOW);
    digitalWrite(PIN_LED_MIC, modo == MODO_MIC ? HIGH : LOW);
    if (!hay_display) return;

    display.clearDisplay();
    for (byte i = 0; i < NUM_BARRAS; i++) {
        byte nivel = constrain(niveles[i], 0, 16);
        int x = 1 + i * BARRA_PASO;
        if (centro == 0) {
            for (byte s = 0; s < nivel; s++) {
                int y = ALTO - (s + 1) * SEG_ALTO + SEG_HUECO;
                display.fillRect(x, y, BARRA_ANCHO, SEG_ALTO - SEG_HUECO, SSD1306_WHITE);
            }
        } else if (nivel > 0) {
            display.fillRect(x, CENTRO_Y - nivel, BARRA_ANCHO, nivel * 2, SSD1306_WHITE);
        }
    }

    if (pico == 1) {
        for (byte i = 0; i < NUM_BARRAS; i++) {
            if (alturaPico[i] == 0) continue;
            int x = 1 + i * BARRA_PASO;
            if (centro == 0) {
                display.drawFastHLine(x, ALTO - alturaPico[i] * SEG_ALTO, BARRA_ANCHO, SSD1306_WHITE);
            } else {
                display.drawFastHLine(x, CENTRO_Y - alturaPico[i], BARRA_ANCHO, SSD1306_WHITE);
                display.drawFastHLine(x, CENTRO_Y + alturaPico[i] - 1, BARRA_ANCHO, SSD1306_WHITE);
            }
        }
    }

    if (pausa == 1) simbolo_pausa();

    display.fillRect(DIV_X, DIV_Y, DIV_W, DIV_H, SSD1306_WHITE);
    display.drawFastHLine(TEXTO_X, SEP_Y, SEP_W, SSD1306_WHITE);

    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(TEXTO_X, TEXTO_Y);
    display.print(modo == MODO_LINE ? F("LINE") : F("MIC"));

    byte n = (nota > 12) ? 12 : nota;
    byte notaX = (strlen(NOTAS[n]) == 1) ? NOTA_X1 : NOTA_X2;
    display.setTextSize(2);
    display.setCursor(notaX, NOTA_Y);
    display.print(NOTAS[n]);

    display.display();
}

}  // namespace

void iniciar() {
    pinMode(PIN_LED_MIC, OUTPUT);
    pinMode(PIN_LED_LINE, OUTPUT);
    Wire.begin(PIN_SDA, PIN_SCL);
    hay_display = display.begin(SSD1306_SWITCHCAPVCC, DIRECCION_OLED);
    if (!hay_display) {
        // El Arduino se quedaba colgado acá; el ESP32 sigue sin pantalla
        // (los LEDs, Blynk y el Monitor Serie siguen andando).
        Serial.println("No encontré la OLED: revisar cables o dirección (0x3C / 0x3D)");
        return;
    }
    Wire.setClock(400000);
    pantalla_inicial();
}

void recibir(const analisis::Paquete& paquete) {
    portENTER_CRITICAL(&candado);
    compartido = paquete;
    hay_nuevo = true;
    portEXIT_CRITICAL(&candado);
}

void atender() {
    analisis::Paquete paquete;
    bool nuevo;
    portENTER_CRITICAL(&candado);
    nuevo = hay_nuevo;
    if (nuevo) paquete = compartido;
    hay_nuevo = false;
    portEXIT_CRITICAL(&candado);
    if (!nuevo) return;
    tomar_paquete(paquete);
    dibujar_pantalla();
}

}  // namespace pantalla
