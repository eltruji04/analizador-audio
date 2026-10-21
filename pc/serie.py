import serial
import time
import configuracion

#Conexion al arduino
def conectar(puerto):
    conexion = serial.Serial(puerto, configuracion.VELOCIDAD_SERIE)
    time.sleep(2)
    return conexion

# Armado del paquete de bytes que se envía al Arduino
def armar_paquete(alturas, modo, nota, pausa, pico):
    if len(alturas) != configuracion.CANTIDAD_BARRAS:
        raise ValueError("La cantidad de alturas no es la esperada")

    paquete = [configuracion.BYTE_INICIO]
    for altura in alturas:
        altura = int(altura)
        altura = max(0, min(altura, configuracion.ALTURA_MAXIMA))
        paquete.append(altura)
    if modo not in (configuracion.MODO_MIC, configuracion.MODO_LINE):
        raise ValueError(f"El modo debe ser 0 (micrófono) o 1 (entrada de línea): {modo}")
    paquete.append(modo)
    if nota not in range(0, configuracion.SIN_NOTA + 1):
        raise ValueError(f"El valor de nota debe estar entre 0 y {configuracion.SIN_NOTA}: {nota}")
    paquete.append(nota)
    if pausa not in (0, 1):
        raise ValueError(f"El valor de pausa debe ser 0 o 1: {pausa}")
    paquete.append(pausa)
    if pico not in (0, 1):
        raise ValueError(f"El valor de pico debe ser 0 o 1: {pico}")
    paquete.append(pico)
    return bytes(paquete)

def enviar(conexion, paquete):
    conexion.write(paquete)

def leer_boton(conexion):
    if conexion.in_waiting > 0:
        dato = conexion.read(1)
        return dato[0]
    else:
        return None

if __name__ == "__main__":
    import estado
    alturas_prueba = [-2, 31, 34, 300, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    paquete = armar_paquete(alturas_prueba, configuracion.MODO_MIC, configuracion.SIN_NOTA, estado.pausa, estado.pico)
    print(f"Paquete: {list(paquete)}")
    print(f"Largo del paquete: {len(paquete)}")

    # Pruebas de armar_paquete con pausa y pico activados: el largo tiene
    # que seguir siendo 21 y los últimos dos bytes (pausa, pico) valer 1.
    paquete = armar_paquete(alturas_prueba, configuracion.MODO_LINE, configuracion.SIN_NOTA, 1, 1)
    print(f"Paquete con pausa y pico (esperado largo 21, termina en 1, 1): "
          f"largo {len(paquete)}, termina en {paquete[-2]}, {paquete[-1]}")

    # Valores inválidos: cada uno tiene que dar ValueError con su mensaje.
    # El try/except es para que el error no corte las pruebas que siguen.
    # Cada caso es (modo, pausa, pico).
    casos_invalidos = [(2, 0, 0, 0), (0, 5, 0, 0), (0, 0, 255, 0), (0,0,0,13)]
    for modo, pausa, pico, nota in casos_invalidos:
        try:
            armar_paquete(alturas_prueba, modo, nota, pausa, pico)
            print(f"ERROR: modo={modo}, pausa={pausa}, pico={pico}, nota={nota} no dio error")
        except ValueError as error:
            print(f"Error esperado: {error}")

    # Pruebas de leer_boton sin Arduino: "loop://" es un puerto falso de
    # pyserial donde lo que se escribe vuelve para leerse, como si lo
    # hubiera mandado el Arduino.
    prueba = serial.serial_for_url("loop://")

    # Prueba 1: no hay nada esperando, tiene que devolver None sin quedarse colgado
    print(f"Prueba 1 (esperado None): {leer_boton(prueba)}")

    # Prueba 2: se aprieta un botón. La pausa corta es por si el puerto
    # falso tarda un instante en tener el byte disponible.
    prueba.write(bytes([configuracion.BOTON_CAIDA]))
    time.sleep(0.01)
    print(f"Prueba 2 (esperado 1, None): {leer_boton(prueba)}, {leer_boton(prueba)}")

    # Prueba 3: dos botones antes de leer, tienen que salir en orden
    prueba.write(bytes([configuracion.BOTON_CAIDA, configuracion.BOTON_PAUSA]))
    time.sleep(0.01)
    print(f"Prueba 3 (esperado 1, 2, None): "
          f"{leer_boton(prueba)}, {leer_boton(prueba)}, {leer_boton(prueba)}")

    # Prueba 4: botón leído y aplicado al estado, la velocidad tiene que avanzar
    antes = estado.velocidad
    prueba.write(bytes([configuracion.BOTON_CAIDA]))
    time.sleep(0.01)
    codigo = leer_boton(prueba)
    if codigo is not None:
        estado.aplicar_accion(codigo)
    print(f"Prueba 4 (velocidad tiene que avanzar): {antes} -> {estado.velocidad}")

    prueba.close()
