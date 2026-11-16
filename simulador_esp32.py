"""
Trabalho Final - Database Of Things - 270400
Alan Brum - 92305

Simulador do ESP-32: faz exatamente as mesmas chamadas que o firmware,
para testar a API sem o hardware (ou como plano B na demonstracao).

Uso (no terminal, na pasta deste arquivo):
    python simulador_esp32.py https://ENDERECO.onrender.com
    python simulador_esp32.py https://ENDERECO.onrender.com d20 5

O primeiro argumento e o endereco da API; depois, opcionalmente, o tipo
de dado e quantas rolagens fazer (padrao: d20, 3 rolagens).
So usa a biblioteca padrao do Python.
"""

import json
import random
import sys
import urllib.error
import urllib.request

CODIGO_DISPOSITIVO = "esp32-01"
FACES = {"d4": 4, "d6": 6, "d8": 8, "d10": 10, "d12": 12, "d20": 20}


def chamar(metodo, url, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(url, data=dados, method=metodo,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as erro:
        return erro.code, json.loads(erro.read().decode() or "{}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    base = sys.argv[1].rstrip("/")
    dado = sys.argv[2] if len(sys.argv) > 2 else "d20"
    vezes = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    if dado not in FACES:
        sys.exit("Tipo de dado invalido: " + dado)

    print("GET /dispositivos/%s/vinculo  (a primeira chamada pode levar ~1 min se a API estiver hibernando)" % CODIGO_DISPOSITIVO)
    codigo, vinculo = chamar("GET", "%s/dispositivos/%s/vinculo" % (base, CODIGO_DISPOSITIVO))
    print("  ->", codigo, vinculo)
    if codigo != 200 or not vinculo.get("vinculado"):
        print("O dado nao esta vinculado. Faca o PUT /dispositivos/%s/vinculo pelo /docs antes." % CODIGO_DISPOSITIVO)
        return

    print("LCD: %s | Dado: %s" % (vinculo["personagem_nome"][:16], dado))
    for _ in range(vezes):
        resultado = random.randint(1, FACES[dado])
        codigo, resposta = chamar("POST", base + "/rolagens",
                                  {"dispositivo": CODIGO_DISPOSITIVO, "dado": dado, "resultado": resultado})
        if codigo == 201:
            critico = resposta["rolagem"]["critico"]
            sinal = {"acerto": "LED verde + bip agudo", "falha": "LED vermelho + bip grave"}.get(critico, "bip curto")
            print("  %s = %2d  -> registrado, critico=%s (%s)" % (dado, resultado, critico, sinal))
        else:
            print("  %s = %2d  -> NAO registrado (%s) %s" % (dado, resultado, codigo, resposta))


if __name__ == "__main__":
    main()
