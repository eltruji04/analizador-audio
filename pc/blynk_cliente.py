"""
blynk_cliente.py — Conexión con la app de Blynk.

- principal.py llama a iniciar(), que arranca un hilo propio (bucle())
  que conecta, escucha a la app y reconecta si se corta;
- estado.py llama a avisar_cambio() después de cada cambio: el valor se
  deja en una cola y el hilo de Blynk lo manda (un solo hilo usa el socket);
- cuando el usuario toca algo en la app, al_recibir() llama a
  estado.cambiar(campo, valor, "Blynk").

Cada campo va en un pin virtual (ver PINES). Forma y color viajan como
índice de su lista (ver LISTAS). El token se lee del .env.
"""

import BlynkLib
import queue
import threading
import time
import estado
import configuracion
import os
from dotenv import load_dotenv


load_dotenv()  # busca el .env y carga sus variables
BLYNK_AUTH_TOKEN = os.getenv("BLYNK_AUTH_TOKEN")
PINES  = {"velocidad": 0, 
          "pausa": 1, 
          "pico": 2, 
          "golpe": 3, 
          "afinador": 4, 
          "forma": 5, 
          "color":6, 
          "color_fijo": 7}
LISTAS = {"forma": configuracion.FORMAS, "color": configuracion.MODOS_COLOR}
pendientes = queue.Queue()
# Segundos que se espera antes de reintentar la conexión con Blynk.
ESPERA_RECONEXION = 5


def iniciar():
    """
    Arranca el hilo de Blynk. Devuelve False si no hay token en el .env.
    Devuelve True apenas arranca el hilo: la conexión se confirma después,
    en al_conectar() (estado.blynk_conectado pasa a True).
    """
    if BLYNK_AUTH_TOKEN is None:
        estado.blynk_conectado = False
        return False
    # daemon=True: el hilo se corta solo al cerrar el programa.
    hilo = threading.Thread(target=bucle, daemon=True)
    hilo.start()
    return True


def bucle():
    """
    Hilo de Blynk: conecta, atiende la conexión y, si se corta, espera
    ESPERA_RECONEXION segundos y vuelve a conectar. Corre todo el programa.

    Es el único que usa el socket: los cambios de la compu llegan por la
    cola `pendientes` y se mandan desde acá, nunca desde el hilo principal.
    """
    while True:
        try:
            blynk = BlynkLib.Blynk(BLYNK_AUTH_TOKEN, server="blynk.cloud")
            blynk.on("connected", al_conectar)
            blynk.on("disconnected", al_desconectar)
            # Un handler por pin. El `c=campo` guarda el campo de esta
            # vuelta del for; sin él, todas las lambdas verían el último.
            for campo, pin in PINES.items():
                blynk.on(f"V{pin}", lambda valores, c=campo: al_recibir(c, valores))

            while blynk.state != BlynkLib.DISCONNECTED:
                # Primero se manda todo lo que dejó avisar_cambio()… (solo
                # con el login hecho: antes, el servidor no lo acepta).
                while blynk.state == BlynkLib.CONNECTED:
                    try:
                        pin, numero = pendientes.get_nowait()
                    except queue.Empty:
                        break
                    blynk.virtual_write(pin, numero)
                # …y después se escucha a Blynk (espera hasta 50 ms).
                blynk.run()
        except (ValueError, OSError) as error:
            # ValueError: no se pudo conectar. OSError: se cortó la red.
            print(f"Blynk: {error}")
        estado.blynk_conectado = False
        time.sleep(ESPERA_RECONEXION)



def al_conectar(ping=None):
    """
    Blynk aceptó el token. Se le manda el estado completo: la compu es la
    dueña y la app tiene que mostrar lo que hay ahora, no lo que tenía.
    """
    estado.blynk_conectado = True
    print("Blynk conectado")
    for campo in PINES:
        encolar(campo, getattr(estado, campo))


def al_desconectar():
    """Se cortó la conexión: bucle() sale de su vuelta y reintenta."""
    estado.blynk_conectado = False
    print("Blynk desconectado")


def al_recibir(campo, valores):
    """
    Llegó un valor desde la app. `valores` es una lista de textos ("1").
    Los campos de LISTAS llegan como índice (el Menu manda 0, 1, 2…).
    """
    try:
        numero = int(valores[0])
        valor = LISTAS[campo][numero] if campo in LISTAS else numero
        estado.cambiar(campo, valor, "Blynk")
    except (ValueError, IndexError):
        print(f"Blynk mandó un valor inválido para {campo}: {valores}")


def encolar(campo, valor):
    """Deja el valor en la cola para que bucle() lo mande. Texto → índice."""
    numero = LISTAS[campo].index(valor) if campo in LISTAS else valor
    pendientes.put((PINES[campo], numero))


def avisar_cambio(campo, valor, origen):
    """
    Se llama después de cada cambio del estado. Manda el valor nuevo a
    Blynk, salvo que el cambio haya venido de Blynk (la app ya lo tiene).
    Si no está conectado igual se encola: al conectar se manda todo.
    """
    if origen == "Blynk" or campo not in PINES:
        return
    encolar(campo, valor)
