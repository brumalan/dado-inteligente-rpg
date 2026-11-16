"""
Trabalho Final - Database Of Things - 270400
Alan Brum - 92305

Fichas iniciais dos personagens.

A colecao personagens original ficou no MongoDB local do computador da
faculdade. Para o banco na nuvem (Atlas), as quatro fichas foram recriadas
aqui com os mesmos nomes e a mesma estrutura de documento. Os valores de
atributos, inventario e demais campos foram preenchidos de novo.

A API chama garantir_personagens() ao subir: se a colecao estiver vazia,
grava estas fichas; se ja tiver personagens, nao mexe em nada.
"""

from modelos import Atributos, ItemInventario, Personagem, PontosVida

CAMPANHA = "As Ruinas de Karendhal"
SISTEMA = "D&D 5e"

FICHAS = [
    {
        "nome": "Thalira Vento-Norte",
        "raca": "Elfa",
        "classe": "Patrulheira",
        "nivel": 5,
        "atributos": dict(forca=12, destreza=18, constituicao=14, inteligencia=11, sabedoria=15, carisma=10),
        "pontos_vida": dict(atual=42, maximo=42),
        "inventario": [("Arco longo", 1), ("Flechas", 40), ("Capa elfica", 1)],
        "pericias": ["Furtividade", "Sobrevivencia", "Percepcao"],
        "alinhamento": "Neutra e Boa",
    },
    {
        "nome": "Bartolomeu Ferraz",
        "raca": "Anao",
        "classe": "Guerreiro",
        "nivel": 5,
        "atributos": dict(forca=17, destreza=10, constituicao=16, inteligencia=10, sabedoria=12, carisma=9),
        "pontos_vida": dict(atual=49, maximo=49),
        "inventario": [("Machado de batalha", 1), ("Escudo", 1), ("Pocao de cura", 2)],
        "pericias": ["Atletismo", "Intimidacao"],
        "alinhamento": "Leal e Neutro",
    },
    {
        "nome": "Dra. Helena Kovacs",
        "raca": "Humana",
        "classe": "Cleriga",
        "nivel": 4,
        "atributos": dict(forca=10, destreza=11, constituicao=13, inteligencia=14, sabedoria=17, carisma=13),
        "pontos_vida": dict(atual=31, maximo=31),
        "inventario": [("Kit de herbalismo", 1), ("Simbolo sagrado", 1), ("Maca", 1)],
        "pericias": ["Medicina", "Religiao", "Intuicao"],
        "alinhamento": "Leal e Boa",
    },
    {
        "nome": "Nykorion o Silencioso",
        "raca": "Tiefling",
        "classe": "Ladino",
        "nivel": 5,
        "atributos": dict(forca=9, destreza=17, constituicao=12, inteligencia=14, sabedoria=11, carisma=15),
        "pontos_vida": dict(atual=33, maximo=33),
        "inventario": [("Adagas", 2), ("Ferramentas de ladrao", 1), ("Corda de seda", 1)],
        "pericias": ["Furtividade", "Prestidigitacao", "Enganacao"],
        "alinhamento": "Caotico e Neutro",
    },
]


def garantir_personagens() -> int:
    """Grava as fichas se a colecao estiver vazia. Devolve quantas foram gravadas."""
    if Personagem.objects.count() > 0:
        return 0

    for ficha in FICHAS:
        Personagem(
            nome=ficha["nome"],
            sistema=SISTEMA,
            campanha=CAMPANHA,
            raca=ficha["raca"],
            classe=ficha["classe"],
            nivel=ficha["nivel"],
            atributos=Atributos(**ficha["atributos"]),
            pontos_vida=PontosVida(**ficha["pontos_vida"]),
            inventario=[ItemInventario(item=item, quantidade=qtd) for item, qtd in ficha["inventario"]],
            pericias=ficha["pericias"],
            alinhamento=ficha["alinhamento"],
            vivo=True,
        ).save()
    return len(FICHAS)
