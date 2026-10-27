// ------------ 16 BAND FRECUENCY ANALYZER ------------

// ------------ LIBRERÍAS ------------
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

//dimensiones de la pantalla
#define ANCHO 128
#define ALTO  32

// 1 = pruebas escribir paquete por Monitor Serie
// 0 = el paquete llega como bytes desde la compu
#define PRUEBA_TEXTO 1

Adafruit_SSD1306 display(ANCHO, ALTO, &Wire, -1);

// ------------ VARIABLES RECIBIDAS POR PUERTO SERIE ------------
byte niveles[16];      // altura de cada barra (1 - 16)
byte modo = 0;         // 0 = MIC y 1 = LINE
byte nota = 12;        // 0 a 11 = nota o 12 = sin nota
byte pausa = 0;        // 0 = reproduce y 1 = pausa
byte pico = 0;         // 0 = no marca de pico y 1 = dibuja la marca de pico

// ------------ CONFIGURACIÓN DE RECEPCIÓN ------------
byte datos[20];        // los 20 bytes que llegan después del 255
byte datonum = 0;      // cuenta de bytes ya recibidos
bool leyendo = false;  // inicializamos en false y se vuelve true cuando lee un 255


// ------------ CONFIGURACIÓN DE MODO PICO ------------
byte alturaPico[16];                // máximo reciente de cada barra
byte caidaPico = 0;                 // cuenta de paquetes para bajar los picos
const byte PICO_CAIDA = 3;     // los picos bajan 1 nivel cada 3 paquetes (más alto = bajan más lento)

// ------------ BOTONESS -----------------
const byte PINES[4] = {11, 10, 9, 6};
const byte CODIGOS[4] = {1, 2, 3, 4}; // 1velocidad 2pausa 3pico 4golpe
const unsigned long ANTIRREBOTE = 50;    
bool ultimaLectura[4]  = {HIGH, HIGH, HIGH, HIGH};
bool estadoEstable[4]  = {HIGH, HIGH, HIGH, HIGH};
unsigned long ultimoCambio[4] = {0, 0, 0, 0};

// NOTAS GUARDADAS, NO SE IMPRIMEN AUN
  const char* const NOTAS[13] = {
    "C", "C#", "D", "D#", "E", "F", "F#",
    "G", "G#", "A", "A#", "B", "-"
  };

// ------------ APARIENCIA ------------
  // panel de 16 barras
    const byte NUM_BARRAS  = 16;   // cantidad de barras
    const byte BARRA_ANCHO = 5;    // píxeles encendidos a lo ancho de cada barra
    const byte BARRA_PASO  = 6;    // 96 px
    const byte SEG_ALTO    = 2;    // alto de cada fila
    const byte SEG_HUECO   = 0;    // px apagados arriba de cada fila: 0 = barra sólida, 1 = se ven las filas

  // panel derecho
    const byte DIV_X = 99, DIV_Y = 2, DIV_W = 1, DIV_H = 28;  // barra vertical
    const byte TEXTO_X = 103;      // x de LINE y MIC
    const byte TEXTO_Y  = 3;        // y de LINE y MIC
    const byte MODO_VACIO_X = 111; // x del "-" de la zona de modo en la pantalla de espera
    const byte SEP_Y   = 11;       // y de la línea horizontal
    const byte SEP_W   = 22;       // largo de la línea horizontal
    const byte NOTA_X1  = 109;      // x de la nota DE 1 DIGITO
    const byte NOTA_X2  = 103;      // x de la nota DE 2 DIGITOS
    const byte NOTA_Y  = 14;       // y de la nota

// ...................................................................
//FUNCIONES
// PAUSA
  void CIRCULO() { //simbolo de pausa
    display.fillCircle(48, 16, 17, SSD1306_BLACK);    // borra las barras que quedan detrás
    display.drawCircle(48, 16, 15, SSD1306_WHITE);
    display.drawCircle(48, 16, 14, SSD1306_WHITE);

    display.fillRect(44, 10, 3, 13, SSD1306_WHITE);   // Barra izquierda
    display.fillRect(50, 10, 3, 13, SSD1306_WHITE);   // Barra derecha
  }

// PANTALLA DE ESPERA ---------------------------
  void pantallaInicial() {
    display.clearDisplay();
    display.fillRect(DIV_X, DIV_Y, DIV_W, DIV_H, SSD1306_WHITE);    // barra vertical

    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(MODO_VACIO_X, TEXTO_Y);                       // "-" de la zona de modo
    display.print(F("-"));

    display.drawFastHLine(TEXTO_X, SEP_Y, SEP_W, SSD1306_WHITE);    // línea separadora

    display.setTextSize(2);
    display.setCursor(NOTA_X1, NOTA_Y);                             // "-" de la nota
    display.print(F("-"));

    display.display();
  }

// PANTALLA CUANDO LLEGA UN PAQUETE ------------------------
  //16barras
  void dibujarPantalla() {
    display.clearDisplay();
    //PRUEBA
      (for (byte i = 0; i < NUM_BARRAS; i++) {
      byte nivel = constrain(niveles[i], 0, 16);
      int x = 1 + i * BARRA_PASO;
      for (byte s = 0; s < nivel; s++) {
        int y = ALTO - (s + 1) * SEG_ALTO + SEG_HUECO;
        display.fillRect(x, y, BARRA_ANCHO, SEG_ALTO - SEG_HUECO, SSD1306_WHITE);
      } )
    }
    
  //Marca de pico
    if (pico == 1) {
      for (byte i = 0; i < NUM_BARRAS; i++) { //recorre las 16
        if (alturaPico[i] > 0) {
          int x = 1 + i * BARRA_PASO;
          int y = ALTO - alturaPico[i] * SEG_ALTO;
          display.drawFastHLine(x, y, BARRA_ANCHO, SSD1306_WHITE);
        }
      }
    }

  // Pausa
    if (pausa == 1) CIRCULO();

  // ACCESORIOS FIJOS DEL PANEL
    display.fillRect(DIV_X, DIV_Y, DIV_W, DIV_H, SSD1306_WHITE);    // linea vertical
    display.drawFastHLine(TEXTO_X, SEP_Y, SEP_W, SSD1306_WHITE);    // linea separadora

  // LINE o MIC según el modo
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(TEXTO_X, TEXTO_Y);
    display.print(F("----"));
    if (modo == 1) {
      display.print(F("LINE"));
    } else if (modo == 0) {
      display.print(F("MIC"));
    }

    // Nota: centrada según tenga 1 o 2 caracteres
    byte n = (nota > 12) ? 12 : nota;
    byte notaX = (strlen(NOTAS[n]) == 1) ? NOTA_X1 : NOTA_X2;
    display.setTextSize(2);
    display.setCursor(notaX, NOTA_Y);
    display.print(NOTAS[n]);

    display.display();   // sin esto no se ve nada
  }

//ahora viene todo lo que pasa cuando recibe un byte
bool procesarByte(byte b){ //verdadero si se completo el paquete o falso si aun no se completa
  if (b == 255) { //marcamos el inicio del paquete
    leyendo = true;
    datonum = 0;
    return false; //recien comienza
  }
  if (!leyendo) return false; //todavia no lee un 255 entonces todavia no empieza ni termina

  datos[datonum] = b;
  datonum++;
  if (datonum < 20) return false; //todavia faltan bytes por leer

  for (byte i = 0; i < 16; i++) { //esto es para las alturas como el byte va de 0-32, lo dividimos para 2 para saber el nivel
    niveles[i] = datos[i] / 2; //es decir pasamos la altura de pixeles a niveles de 2 pixeles de altura
  }
  modo = datos[16]; //el dato numero 16 es mic o line
  nota = datos[17]; //el dato numero 17 es del 1 al 12
  pausa = datos[18]; // 0 andando 1 en pausa
  pico = dato[19]; //0 sin marca 1 con pico

  bool bajar = (++caidaPico >= PICO_CAIDA_CADA) ;
  if (bajar) caidaPico = 0;

//ahora recorremos las 16 barras
for (byte i = 0; i < 16; i++) {
  if (niveles[i] >= alturaPico[i]) {
    alturaPico[i] = niveles[i];
  } else if (bajar && alturaPico[i] > 0) {
    alturaPico[i]--;
  }
}

leyendo = false;
return true; //si no esta leyendo es porque el paquete termino o no inicio aun, ahora espera al proximo 255
}

//ahora REVISAMOS LOS CUATRO BOTONES PARTE IMPORTANTE REVISAR
//al cambiar su estado, manda un byte con su codigo con serial write
void revisarBotones() {
  for (byte i = 0; i <4; i++) 
        bool lectura = digitalRead(PINES[i]);

      if (lectura != ultimaLectura[i]) {       // cambió: reiniciar el conteo del antirrebote
        ultimoCambio[i] = millis();
        ultimaLectura[i] = lectura;
      }

      if (millis() - ultimoCambio[i] > ANTIRREBOTE && lectura != estadoEstable[i]) {
        estadoEstable[i] = lectura;
        if (estadoEstable[i] == LOW) {         // recién apretado
          Serial.write(CODIGOS[i]);
        }
      }
    }
  }

void setup() {
  Serial.begin(115200);        // tiene que ser igual al de la compu
  Serial.setTimeout(20);       // para el modo de prueba con texto

  for (byte i = 0; i < 4; i++) {
    pinMode(PINES[i], INPUT_PULLUP);   // suelto = HIGH, apretado = LOW
  }

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    for (;;);          // si falla: revisar cables o dirección (0x3C / 0x3D)
  }
  Wire.setClock(400000);       // I2C más rápido

  pantallaInicial();           // pantalla de espera hasta que llegue el primer paquete
}

void loop() {
  revisarBotones();            // primero los botones, en cada vuelta (también durante la pausa)

  bool hayNuevo = false;

  while (Serial.available() > 0) {
#if PRUEBA_TEXTO
    char c = Serial.peek();
    if (c < '0' || c > '9') {          // saltar espacios y saltos de línea
      Serial.read();
      continue;
    }
    if (procesarByte(Serial.parseInt())) hayNuevo = true;
#else
    if (procesarByte(Serial.read())) hayNuevo = true;
#endif
  }

  if (hayNuevo) dibujarPantalla();     // se dibuja una sola vez, con el último paquete
}
