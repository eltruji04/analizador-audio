#!/bin/sh
# Compila y corre las pruebas del análisis del ESP32 en la compu.
#   sh esp32/pruebas/correr_pruebas.sh
# Primero con double (tiene que dar lo mismo que el Python) y después con
# float (como corre en el ESP32). Los ejecutables quedan en esp32/pruebas/salida/.
set -e
cd "$(dirname "$0")"
mkdir -p salida
FUENTES="../analizador_esp32/fft.cpp ../analizador_esp32/bandas.cpp ../analizador_esp32/golpe.cpp \
../analizador_esp32/nota.cpp ../analizador_esp32/estado.cpp ../analizador_esp32/analisis.cpp"
OPCIONES="-std=c++17 -O2 -Wall -Wextra"
for tipo in double float; do
  extra=""
  [ "$tipo" = double ] && extra="-DANALISIS_DOUBLE"
  c++ $OPCIONES $extra $FUENTES pruebas_unidad.cpp -o salida/pruebas_unidad_$tipo
  c++ $OPCIONES $extra $FUENTES comparar.cpp -o salida/comparar_$tipo
  echo "=== pruebas_unidad ($tipo) ==="
  ./salida/pruebas_unidad_$tipo
done
