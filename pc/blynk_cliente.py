"""
blynk_cliente.py — Conexión con la app de Blynk.

FALTA IMPLEMENTAR
 El resto del programa ya está listo:
- principal.py llama a iniciar() al arrancar;
- estado.py llama a avisar_cambio() después de cada cambio, venga de
  donde venga, para que Blynk muestre el estado actual;
- cuando el usuario toque algo en Blynk, este módulo tiene que llamar a
  estado.aplicar_accion(codigo, "Blynk") (mismos códigos que los botones)
  o a estado.cambiar(campo, valor, "Blynk").
"""

import estado


def iniciar():
    """
    Conecta con Blynk y anota estado.blynk_conectado. Devuelve True si se
    conectó. Por ahora no conecta.
    """
    estado.blynk_conectado = False
    return False


def avisar_cambio(campo, valor, origen):
    """
    Se llama después de cada cambio del estado. Tiene que mandar el valor
    nuevo a Blynk (salvo que el cambio haya venido de Blynk). Por ahora no hace nada.
    """
    pass
