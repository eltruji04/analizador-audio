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
#define PRUEBA_TEXTO 0

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
const byte PICO_CAIDA = 3;          // los picos bajan 1 nivel cada 3 paquetes

// ------------ BOTONES -----------------
const byte PINES[4] = {11, 10, 9, 6};
const byte CODIGOS[4] = {1, 2, 3, 4}; // 1velocidad 2pausa 3pico 4golpe
const unsigned long ANTIRREBOTE = 50;    
bool ultimaLectura[4]  = {HIGH, HIGH, HIGH, HIGH};
bool estadoEstable[4]  = {HIGH, HIGH, HIGH, HIGH};
unsigned long ultimoCambio[4] = {0, 0, 0, 0};

// NOTAS GUARDADAS
const char* const NOTAS[13] = {
  "C", "C#", "D", "D#", "E", "F", "F#",
  "G", "G#", "A", "A#", "B", "-"
};

// ------------ APARIENCIA ------------
const byte NUM_BARRAS  = 16;   
const byte BARRA_ANCHO = 5;    
const byte BARRA_PASO  = 6;    
const byte SEG_ALTO    = 2;    
const byte SEG_HUECO   = 0;    

const byte DIV_X = 99, DIV_Y = 2, DIV_W = 1, DIV_H = 28;  
const byte TEXTO_X = 103;      
const byte TEXTO_Y  = 3;        
const byte MODO_VACIO_X = 111; 
const byte SEP_Y   = 11;       
const byte SEP_W   = 22;       
const byte NOTA_X1  = 109;      
const byte NOTA_X2  = 103;      
const byte NOTA_Y  = 14;       

// ...................................................................
// FUNCIONES

// PAUSA
void CIRCULO() { 
  display.fillCircle(48, 16, 17, SSD1306_BLACK);    
  display.drawCircle(48, 16, 15, SSD1306_WHITE);
  display.drawCircle(48, 16, 14, SSD1306_WHITE);

  display.fillRect(44, 10, 3, 13, SSD1306_WHITE);   
  display.fillRect(50, 10, 3, 13, SSD1306_WHITE);   
}

// PANTALLA DE ESPERA ---------------------------
void pantallaInicial() {
  display.clearDisplay();
  display.fillRect(DIV_X, DIV_Y, DIV_W, DIV_H, SSD1306_WHITE);    

  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(MODO_VACIO_X, TEXTO_Y);                       
  display.print(F("-"));

  display.drawFastHLine(TEXTO_X, SEP_Y, SEP_W, SSD1306_WHITE);    

  display.setTextSize(2);
  display.setCursor(NOTA_X1, NOTA_Y);                             
  display.print(F("-"));

  display.display();
}

// PANTALLA CUANDO LLEGA UN PAQUETE ------------------------
void dibujarPantalla() {
  display.clearDisplay();
  
  // Dibujar las 16 barras (Corregido el error de paréntesis)
  for (byte i = 0; i < NUM_BARRAS; i++) {
    byte nivel = constrain(niveles[i], 0, 16);
    int x = 1 + i * BARRA_PASO;
    for (byte s = 0; s < nivel; s++) {
      int y = ALTO - (s + 1) * SEG_ALTO + SEG_HUECO;
      display.fillRect(x, y, BARRA_ANCHO, SEG_ALTO - SEG_HUECO, SSD1306_WHITE);
    }
  }
    
  // Marca de pico
  if (pico == 1) {
    for (byte i = 0; i < NUM_BARRAS; i++) { 
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
  display.fillRect(DIV_X, DIV_Y, DIV_W, DIV_H, SSD1306_WHITE);    
  display.drawFastHLine(TEXTO_X, SEP_Y, SEP_W, SSD1306_WHITE);    

  // LINE o MIC según el modo
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(TEXTO_X, TEXTO_Y);
  if (modo == 1) {
    display.print(F("LINE"));
  } else if (modo == 0) {
    display.print(F("MIC"));
  }

  // Nota
  byte n = (nota > 12) ? 12 : nota;
  byte notaX = (strlen(NOTAS[n]) == 1) ? NOTA_X1 : NOTA_X2;
  display.setTextSize(2);
  display.setCursor(notaX, NOTA_Y);
  display.print(NOTAS[n]);

  display.display();   
}

// PROCESAR BYTE RECIBIDO
bool procesarByte(byte b) {
  if (b == 255) { 
    leyendo = true;
    datonum = 0;
    return false; 
  }
  if (!leyendo) return false; 

  datos[datonum] = b;
  datonum++;
  if (datonum < 20) return false; 

  for (byte i = 0; i < 16; i++) { 
    niveles[i] = datos[i] / 2; 
  }
  modo = datos[16]; 
  nota = datos[17]; 
  pausa = datos[18]; 
  pico = datos[19]; // (Corregido: era dato[19] sin 's')

  // (Corregido: era PICO_CAIDA_CADA)
  bool bajar = (++caidaPico >= PICO_CAIDA); 
  if (bajar) caidaPico = 0;

  for (byte i = 0; i < 16; i++) {
    if (niveles[i] >= alturaPico[i]) {
      alturaPico[i] = niveles[i];
    } else if (bajar && alturaPico[i] > 0) {
      alturaPico[i]--;
    }
  }

  leyendo = false;
  return true; 
}

// REVISAR LOS CUATRO BOTONES (Estructura de llaves corregida)
void revisarBotones() {
  for (byte i = 0; i < 4; i++) {
    bool lectura = digitalRead(PINES[i]);

    if (lectura != ultimaLectura[i]) {       
      ultimoCambio[i] = millis();
      ultimaLectura[i] = lectura;
    }

    if (millis() - ultimoCambio[i] > ANTIRREBOTE && lectura != estadoEstable[i]) {
      estadoEstable[i] = lectura;
      if (estadoEstable[i] == LOW) {         
        Serial.write(CODIGOS[i]);
      }
    }
  }
}

void setup() {
  Serial.begin(115200);        
  Serial.setTimeout(20);       

  for (byte i = 0; i < 4; i++) {
    pinMode(PINES[i], INPUT_PULLUP);   
  }

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    for (;;);          
  }
  Wire.setClock(400000);       

  pantallaInicial();           
}

void loop() {
  revisarBotones();            

  bool hayNuevo = false;

  while (Serial.available() > 0) {
#if PRUEBA_TEXTO
    char c = Serial.peek();
    if (c < '0' || c > '9') {          
      Serial.read();
      continue;
    }
    if (procesarByte(Serial.parseInt())) hayNuevo = true;
#else
    if (procesarByte(Serial.read())) hayNuevo = true;
#endif
  }

  if (hayNuevo) dibujarPantalla();     
}
