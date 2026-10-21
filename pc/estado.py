import configuracion

velocidad = configuracion.VELOCIDAD_INICIAL
pausa = 0
pico = 0
golpe = 0

def aplicar_accion(codigo):
    global velocidad, pausa, pico, golpe
    if codigo == configuracion.BOTON_CAIDA:
        velocidad = (velocidad + 1) % len(configuracion.VELOCIDADES_CAIDA)
    elif codigo == configuracion.BOTON_PAUSA:
        pausa = 1 - pausa
    elif codigo == configuracion.BOTON_PICO:
        pico = 1 - pico
    elif codigo == configuracion.BOTON_GOLPE:
        golpe = 1 - golpe
    else:
        print(f"código desconocido: {codigo}")

if __name__ == "__main__":
    print(f"Velocidad: {velocidad}")
    for _ in range(4):
        aplicar_accion(configuracion.BOTON_CAIDA)
        print(f"Velocidad: {velocidad}")
    aplicar_accion(configuracion.BOTON_PAUSA)
    print(f"Pausa: {pausa}")
    aplicar_accion(configuracion.BOTON_PAUSA)
    print(f"Pausa: {pausa}")
    aplicar_accion(configuracion.BOTON_PAUSA)
    print(f"Pausa: {pausa}")
    aplicar_accion(99)  