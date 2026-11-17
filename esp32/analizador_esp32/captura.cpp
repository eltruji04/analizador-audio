// captura.cpp — Captura de audio por I2S (ver captura.h).
//
// Usa el driver I2S nuevo de ESP-IDF 5 (driver/i2s_std.h), que viene con
// el core 3.x de ESP32 para Arduino.

#include "captura.h"
#include "configuracion.h"
#include "estado.h"
#include <Arduino.h>
#include "driver/i2s_std.h"

namespace captura {

namespace {

constexpr int M = TAMANO_BLOQUE;

AlHaberPaquete avisar_paquete = nullptr;
i2s_chan_handle_t canal = nullptr;
PinesI2S pines_abiertos;

// Muestras crudas: dos canales de 32 bits por muestra (izquierdo, derecho).
int32_t crudo[M * 2];
real_t izquierdo[M];
real_t derecho[M];

// Mediciones (las lee tiempos() desde otra tarea).
portMUX_TYPE candado_tiempos = portMUX_INITIALIZER_UNLOCKED;
uint64_t suma_us = 0;
uint32_t maximo = 0, cantidad = 0, perdidos = 0;

gpio_num_t pin(int numero) { return numero < 0 ? I2S_GPIO_UNUSED : (gpio_num_t)numero; }

void cerrar() {
    if (canal == nullptr) return;
    i2s_channel_disable(canal);
    i2s_del_channel(canal);
    canal = nullptr;
}

// Abre el canal I2S con los pines de la fuente. Devuelve false si falla.
bool abrir(int fuente) {
    cerrar();
    const PinesI2S& p = fuente == MODO_MIC ? PINES_MIC : PINES_LINE;

    i2s_chan_config_t config_canal = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    // 8 × 256 muestras ≈ 43 ms de margen: si un análisis tarda más que un
    // bloque, el DMA sigue guardando audio mientras tanto.
    config_canal.dma_desc_num = 8;
    config_canal.dma_frame_num = 256;
    if (i2s_new_channel(&config_canal, nullptr, &canal) != ESP_OK) {
        canal = nullptr;
        return false;
    }

    // Siempre estéreo de 32 bits: el INMP441 y el PCM1808 mandan 24 bits
    // dentro de cada casillero de 32. Si la fuente es mono, se usa un canal.
    i2s_std_config_t config = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(FRECUENCIA_MUESTREO),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {
            .mclk = pin(p.mclk),
            .bclk = pin(p.bclk),
            .ws = pin(p.ws),
            .dout = I2S_GPIO_UNUSED,
            .din = pin(p.din),
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv = false,
            },
        },
    };
    // MCLK = 256 × 48 kHz = 12,288 MHz (lo que pide el PCM1808).
    config.clk_cfg.mclk_multiple = I2S_MCLK_MULTIPLE_256;

    if (i2s_channel_init_std_mode(canal, &config) != ESP_OK || i2s_channel_enable(canal) != ESP_OK) {
        cerrar();
        return false;
    }
    pines_abiertos = p;
    return true;
}

void tarea_audio(void*) {
    int abierta = -1;   // fuente del canal abierto ahora (−1 = ninguno)
    analisis::Paquete paquete;
    for (;;) {
        // ¿Cambió la fuente? Lo que en la compu hacía elegir_dispositivo().
        int fuente = estado::valor(estado::FUENTE);
        if (fuente != abierta) {
            if (!abrir(fuente)) {
                if (abierta >= 0 && abrir(abierta)) {
                    Serial.println("No pude abrir la fuente nueva: sigo con la anterior");
                    estado::cambiar(estado::FUENTE, abierta, "ESP32");
                } else {
                    Serial.println("No pude abrir la entrada de audio: reviso los pines y reintento");
                    abierta = -1;
                    vTaskDelay(pdMS_TO_TICKS(1000));
                }
                continue;
            }
            // Cambio de fuente (no al empezar): se descarta lo de la anterior.
            if (abierta >= 0) analisis::cambio_de_fuente();
            abierta = fuente;
            Serial.printf("Usando entrada: %s\n", fuente == MODO_MIC ? "MIC" : "LINE");
        }

        size_t leidos = 0;
        esp_err_t error = i2s_channel_read(canal, crudo, sizeof crudo, &leidos, pdMS_TO_TICKS(1000));
        if (error != ESP_OK || leidos < sizeof crudo) {
            // Sin datos en 1 s: el ADC no está conectado o no tiene reloj.
            portENTER_CRITICAL(&candado_tiempos);
            perdidos++;
            portEXIT_CRITICAL(&candado_tiempos);
            continue;
        }

        // De enteros de 32 bits a −1…1, como las muestras de sounddevice.
        const real_t escala = (real_t)(1.0 / 2147483648.0);
        bool estereo = pines_abiertos.estereo;
        int canal_mono = pines_abiertos.canal;
        for (int i = 0; i < M; i++) {
            if (estereo) {
                izquierdo[i] = crudo[2 * i] * escala;
                derecho[i] = crudo[2 * i + 1] * escala;
            } else {
                izquierdo[i] = crudo[2 * i + canal_mono] * escala;
            }
        }

        uint64_t inicio = esp_timer_get_time();
        double ahora = inicio / 1e6;
        bool nuevo = analisis::procesar_bloque(izquierdo, estereo ? derecho : nullptr, M, ahora, &paquete);
        uint32_t duracion = (uint32_t)(esp_timer_get_time() - inicio);

        portENTER_CRITICAL(&candado_tiempos);
        suma_us += duracion;
        cantidad++;
        if (duracion > maximo) maximo = duracion;
        portEXIT_CRITICAL(&candado_tiempos);

        if (nuevo && avisar_paquete) avisar_paquete(paquete);
    }
}

}  // namespace

bool iniciar(AlHaberPaquete al_haber_paquete) {
    avisar_paquete = al_haber_paquete;
    // Núcleo 1 (el 0 es del WiFi), prioridad 5: por encima de loop(), que
    // dibuja la OLED y lee los botones con prioridad 1.
    return xTaskCreatePinnedToCore(tarea_audio, "audio", 8192, nullptr, 5, nullptr, 1) == pdPASS;
}

void tiempos(uint32_t* promedio_us, uint32_t* maximo_us, uint32_t* bloques, uint32_t* bloques_perdidos) {
    portENTER_CRITICAL(&candado_tiempos);
    *promedio_us = cantidad ? (uint32_t)(suma_us / cantidad) : 0;
    *maximo_us = maximo;
    *bloques = cantidad;
    *bloques_perdidos = perdidos;
    suma_us = 0;
    maximo = 0;
    cantidad = 0;
    perdidos = 0;
    portEXIT_CRITICAL(&candado_tiempos);
}

}  // namespace captura
