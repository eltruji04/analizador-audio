// comparar.cpp — Corre el análisis del ESP32 sobre una señal grabada en un
// archivo y escribe los resultados de cada bloque, para compararlos con los
// de pc/principal.al_recibir_bloque (ver comparar_con_python.py).
//
// Uso: comparar <senal.f32> <eventos.txt> <salida.txt>
// - senal.f32: muestras float32 intercaladas (izquierdo, derecho, …).
// - eventos.txt: una línea "bloque acción valor" por evento, en orden.
// - salida.txt: una línea por bloque (mismo formato que escribe el Python).

#include "../analizador_esp32/analisis.h"
#include "../analizador_esp32/estado.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <vector>

struct Evento {
    int bloque;
    char accion[32];
    int valor;
};

int main(int argc, char** argv) {
    if (argc != 4) {
        fprintf(stderr, "Uso: %s senal.f32 eventos.txt salida.txt\n", argv[0]);
        return 2;
    }
    FILE* archivo = fopen(argv[1], "rb");
    if (!archivo) { perror(argv[1]); return 2; }
    std::vector<float> senal;
    float muestra;
    while (fread(&muestra, sizeof muestra, 1, archivo) == 1) senal.push_back(muestra);
    fclose(archivo);

    std::vector<Evento> eventos;
    archivo = fopen(argv[2], "r");
    if (!archivo) { perror(argv[2]); return 2; }
    Evento e;
    while (fscanf(archivo, "%d %31s %d", &e.bloque, e.accion, &e.valor) == 3) eventos.push_back(e);
    fclose(archivo);

    FILE* salida = fopen(argv[3], "w");
    if (!salida) { perror(argv[3]); return 2; }

    if (!analisis::iniciar()) { fprintf(stderr, "Sin memoria\n"); return 1; }
    // La prueba arranca en LINE (señal estéreo), igual que comparar_con_python.py.
    estado::cambiar(estado::FUENTE, MODO_LINE, "prueba");

    const int m = TAMANO_BLOQUE;
    int cantidad_bloques = (int)(senal.size() / (2 * m));
    std::vector<real_t> izquierdo(m), derecho(m);
    bool mono = false;
    size_t proximo = 0;
    for (int b = 0; b < cantidad_bloques; b++) {
        while (proximo < eventos.size() && eventos[proximo].bloque == b) {
            const Evento& ev = eventos[proximo++];
            if (!strcmp(ev.accion, "velocidad")) estado::cambiar(estado::VELOCIDAD, ev.valor, "prueba");
            else if (!strcmp(ev.accion, "pausa")) estado::cambiar(estado::PAUSA, ev.valor, "prueba");
            else if (!strcmp(ev.accion, "pico")) estado::cambiar(estado::PICO, ev.valor, "prueba");
            else if (!strcmp(ev.accion, "golpe")) estado::cambiar(estado::GOLPE, ev.valor, "prueba");
            else if (!strcmp(ev.accion, "afinador")) estado::cambiar(estado::AFINADOR, ev.valor, "prueba");
            else if (!strcmp(ev.accion, "forma")) estado::cambiar(estado::FORMA, ev.valor, "prueba");
            else if (!strcmp(ev.accion, "recalibrar")) estado::pedir_recalibracion("prueba");
            else if (!strcmp(ev.accion, "fuente")) {
                analisis::cambio_de_fuente();
                estado::cambiar(estado::FUENTE, ev.valor, "prueba");
                mono = ev.valor == MODO_MIC;   // el micrófono es mono
            } else fprintf(stderr, "Evento desconocido: %s\n", ev.accion);
        }
        for (int i = 0; i < m; i++) {
            izquierdo[i] = senal[(size_t)(b * m + i) * 2];
            derecho[i] = senal[(size_t)(b * m + i) * 2 + 1];
        }
        double ahora = 1000.0 + (double)b * m / FRECUENCIA_MUESTREO;
        analisis::Paquete paquete;
        bool nuevo = analisis::procesar_bloque(izquierdo.data(), mono ? nullptr : derecho.data(), m, ahora, &paquete);

        const analisis::Resultados& r = analisis::resultados();
        for (int k = 0; k < CANTIDAD_BARRAS; k++) fprintf(salida, "%.6f ", (double)r.alturas[k]);
        for (int k = 0; k < CANTIDAD_BARRAS; k++) fprintf(salida, "%.6f ", (double)r.destello[k]);
        for (int k = 0; k < CANTIDAD_BARRAS; k++) fprintf(salida, "%.6f ", (double)r.picos[k]);
        fprintf(salida, "%d %.6f %.6f %d %.6f %d", r.nota, r.frecuencia, r.cents, r.bpm, (double)r.nivel, nuevo ? 1 : 0);
        if (nuevo) {
            for (int k = 0; k < CANTIDAD_BARRAS; k++) fprintf(salida, " %d", paquete.alturas[k]);
            fprintf(salida, " %d %d %d %d %d", paquete.fuente, paquete.nota, paquete.pausa, paquete.pico, paquete.forma_oled);
        }
        fprintf(salida, "\n");
    }
    fclose(salida);
    return 0;
}
