// ------------ ANALIZADOR DE AUDIO DE 16 BANDAS — ESP32 ------------
//
// Traducción de todo el programa de la compu (pc/) y del Arduino
// (arduino/analizador_oled) a un solo ESP32, sin compu:
//
//   Micrófono I2S / ADC de línea ──► ESP32 ──► OLED 128x32, LEDs
//                                     ▲  │
//                         4 botones ──┘  └──► Blynk (WiFi)
//
// Tareas:
// - Audio (núcleo 1, prioridad 5, captura.cpp): lee cada bloque por I2S y
//   lo analiza (analisis.cpp). Es lo que hacía el callback de sounddevice.
// - loop() (núcleo 1, prioridad 1): botones, Monitor Serie (las mismas
//   teclas que la ventana de la compu) y OLED.
// - Blynk (núcleo 0, junto al WiFi, blynk_cliente.cpp).
//
// Lo que NO se tradujo: el visualizador de pygame (visualizador.py,
// dibujo.py, colores.py), porque el ESP32 no tiene ventana. Su lugar lo
// ocupan la OLED y el Monitor Serie.
//
// Placa: "ESP32 Dev Module", con el core 3.x de Espressif.
// Librerías: Adafruit SSD1306, Adafruit GFX y Blynk.

#include "analisis.h"
#include "blynk_cliente.h"
#include "botones.h"
#include "captura.h"
#include "configuracion.h"
#include "estado.h"
#include "pantalla.h"

// Cada cuánto se informan por el Monitor Serie los tiempos del análisis.
const unsigned long INTERVALO_INFORME = 5000;
unsigned long ultimo_informe = 0;
bool informe_activo = true;

const char* const NOMBRES_NOTAS[13] = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B", "-"};

// Muestra cada cambio con su origen (en la compu iba en el encabezado de la ventana).
void mostrar_cambio(estado::Campo campo, int valor, const char* origen) {
  char texto[40];
  estado::describir(campo, valor, texto, sizeof texto);
  Serial.printf("[%s] %s\n", origen, texto);
}

void mostrar_ayuda() {
  Serial.println();
  Serial.println("Teclas (Monitor Serie, con \"Sin ajuste de línea\"):");
  Serial.println("  espacio  pausa           p  marca de pico     g  golpe");
  Serial.println("  a        afinador        f  forma             c  color");
  Serial.println("  v        velocidad       r  recalibrar        i  fuente MIC/LINE");
  Serial.println("  t        informe de tiempos (prende/apaga)    h  esta ayuda");
}

// Las teclas de visualizador.py, ahora por el Monitor Serie.
void atender_teclado() {
  while (Serial.available() > 0) {
    char tecla = Serial.read();
    switch (tecla) {
      case ' ': estado::alternar(estado::PAUSA, "serie"); break;
      case 'p': estado::alternar(estado::PICO, "serie"); break;
      case 'g': estado::alternar(estado::GOLPE, "serie"); break;
      case 'a': estado::alternar(estado::AFINADOR, "serie"); break;
      case 'f': estado::siguiente(estado::FORMA, "serie"); break;
      case 'c': estado::siguiente(estado::COLOR, "serie"); break;
      case 'v': estado::siguiente(estado::VELOCIDAD, "serie"); break;
      case 'i': estado::alternar(estado::FUENTE, "serie"); break;
      case 'r':
        estado::pedir_recalibracion("serie");
        Serial.println("[serie] Recalibrando");
        break;
      case 't': informe_activo = !informe_activo; break;
      case 'h': mostrar_ayuda(); break;
      default: break;   // saltos de línea y otras teclas: nada
    }
  }
}

// Cada INTERVALO_INFORME: cuánto tarda el análisis de un bloque (tiene que
// quedar por debajo de los ~21,3 ms que dura un bloque) y qué está sonando.
void informar() {
  uint32_t promedio, maximo, bloques, perdidos;
  captura::tiempos(&promedio, &maximo, &bloques, &perdidos);
  if (!informe_activo) return;
  const analisis::Resultados& r = analisis::resultados();
  const float bloque_ms = 1000.0f * TAMANO_BLOQUE / FRECUENCIA_MUESTREO;
  Serial.printf("Análisis: %.1f ms promedio, %.1f ms máximo (bloque: %.1f ms) · %u bloques",
                promedio / 1000.0f, maximo / 1000.0f, bloque_ms, (unsigned)bloques);
  if (perdidos) Serial.printf(" · %u lecturas sin audio", (unsigned)perdidos);
  Serial.printf(" · nivel %.0f dB · nota %s", (double)r.nivel, NOMBRES_NOTAS[r.nota]);
  if (!isnan(r.frecuencia)) Serial.printf(" (%.1f Hz, %+.0f cents)", r.frecuencia, r.cents);
  if (r.bpm > 0) Serial.printf(" · %d BPM", r.bpm);
  Serial.printf(" · Blynk %s · RAM libre %u\n", blynk_cliente::conectado() ? "sí" : "no",
                (unsigned)ESP.getFreeHeap());
}

void setup() {
  Serial.begin(VELOCIDAD_SERIE);
  delay(200);
  Serial.println("\nAnalizador de audio — ESP32");

  // La forma, la caída y los efectos de la última vez.
  estado::cargar_preferencias();
  estado::suscribir(mostrar_cambio);

  pantalla::iniciar();
  botones::iniciar();

  if (!analisis::iniciar()) {
    Serial.println("No hay memoria para el análisis");
    for (;;) delay(1000);
  }

  if (!blynk_cliente::iniciar()) {
    Serial.println("Blynk sin conectar: falta secretos.h (ver secretos.h.ejemplo)");
  }

  if (!captura::iniciar(pantalla::recibir)) {
    Serial.println("No se pudo arrancar la tarea de audio");
    for (;;) delay(1000);
  }
  mostrar_ayuda();
}

void loop() {
  botones::revisar();
  atender_teclado();
  pantalla::atender();
  if (millis() - ultimo_informe >= INTERVALO_INFORME) {
    ultimo_informe = millis();
    informar();
  }
  // Le deja el núcleo a las otras tareas un momento (~1000 vueltas por segundo).
  delay(1);
}
