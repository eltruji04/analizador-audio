import serial
import time
import configuracion

#Conexion al arduino
def conectar(puerto):
    conexion = serial.Serial(puerto, configuracion.VELOCIDAD_SERIE)
    time.sleep(2)
    return conexion

# Armado del paquete de bytes que se envía al Arduino
def armar_paquete(alturas, modo, nota):
    if len(alturas) != configuracion.CANTIDAD_BARRAS:
        raise ValueError("La cantidad de alturas no es la esperada")

    paquete = [configuracion.BYTE_INICIO]
    for altura in alturas:
        altura = int(altura)
        altura = max(0, min(altura, configuracion.ALTURA_MAXIMA))
        paquete.append(altura)
    paquete.append(modo)
    paquete.append(nota)
    return bytes(paquete)

def enviar(conexion, paquete):
    conexion.write(paquete)

if __name__ == "__main__":
    alturas_prueba = [-2, 31, 34, 300, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    paquete = armar_paquete(alturas_prueba, configuracion.MODO_MIC, configuracion.SIN_NOTA)
    print(f"Paquete: {list(paquete)}")
    print(f"Largo del paquete: {len(paquete)}")