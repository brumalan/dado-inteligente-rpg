"""
Trabalho Final - Database Of Things - 270400
Alan Brum - 92305

Dado inteligente para RPG de mesa com ESP-32.
Modelagem do banco em MongoEngine.

Banco: MongoDB, base `rpg_de_mesa`.
  - Na nuvem (MongoDB Atlas): o endereco vem da variavel de ambiente MONGO_URI.
  - Sem MONGO_URI: usa o MongoDB local, localhost:27017.
As classes de Personagem espelham os documentos da colecao personagens,
por isso alguns campos usam db_field para casar com o nome gravado
(ex.: pontosVida no banco, pontos_vida no Python).
"""

import os
from datetime import datetime

from mongoengine import (
    connect,
    Document,
    EmbeddedDocument,
    StringField,
    IntField,
    BooleanField,
    DateTimeField,
    ListField,
    ReferenceField,
    EmbeddedDocumentField,
    CASCADE,
    DENY,
    NULLIFY,
)

# --------------------------------------------------------------------------
# Conexao
# --------------------------------------------------------------------------

MONGO_HOST = "localhost"
MONGO_PORT = 27017
MONGO_DB = "rpg_de_mesa"

# endereco do Atlas, configurado no Render (nunca gravado no codigo,
# porque contem a senha do usuario do banco)
MONGO_URI = os.environ.get("MONGO_URI")


def conectar():
    """Abre a conexao com o Atlas, se MONGO_URI existir; senao, com o MongoDB local."""
    if MONGO_URI:
        return connect(db=MONGO_DB, host=MONGO_URI)
    return connect(db=MONGO_DB, host=MONGO_HOST, port=MONGO_PORT)


# --------------------------------------------------------------------------
# Documentos agregados (embutidos dentro de personagem)
# --------------------------------------------------------------------------

class Atributos(EmbeddedDocument):
    forca = IntField(required=True, min_value=1, max_value=20)
    destreza = IntField(required=True, min_value=1, max_value=20)
    constituicao = IntField(required=True, min_value=1, max_value=20)
    inteligencia = IntField(required=True, min_value=1, max_value=20)
    sabedoria = IntField(required=True, min_value=1, max_value=20)
    carisma = IntField(required=True, min_value=1, max_value=20)


class PontosVida(EmbeddedDocument):
    atual = IntField(required=True, min_value=0)
    maximo = IntField(required=True, min_value=1)


class ItemInventario(EmbeddedDocument):
    # no banco a chave e "item", nao "nome"
    item = StringField(required=True, min_length=1, max_length=100)
    quantidade = IntField(required=True, min_value=1, default=1)


# --------------------------------------------------------------------------
# personagens - colecao que ja existe, reaproveitada do CRUD anterior
# --------------------------------------------------------------------------

class Personagem(Document):
    nome = StringField(required=True, min_length=2, max_length=100)
    jogador = StringField(max_length=100)
    sistema = StringField(max_length=50)
    campanha = StringField(max_length=100)
    raca = StringField(max_length=50)
    classe = StringField(max_length=50)
    nivel = IntField(min_value=1, max_value=20, default=1)
    atributos = EmbeddedDocumentField(Atributos)
    pontos_vida = EmbeddedDocumentField(PontosVida, db_field="pontosVida")
    inventario = ListField(EmbeddedDocumentField(ItemInventario), default=list)
    pericias = ListField(StringField(max_length=50), default=list)
    alinhamento = StringField(max_length=50)
    vivo = BooleanField(default=True)

    meta = {"collection": "personagens"}

    def __str__(self):
        return "%s (%s nivel %s)" % (self.nome, self.classe, self.nivel)


# --------------------------------------------------------------------------
# sessoes - uma partida de RPG
# --------------------------------------------------------------------------

class Sessao(Document):
    nome = StringField(required=True, min_length=2, max_length=120)
    campanha = StringField(max_length=100)
    mestre = StringField(max_length=100)
    inicio = DateTimeField(required=True, default=datetime.now)
    fim = DateTimeField()
    ativa = BooleanField(default=True)

    meta = {
        "collection": "sessoes",
        "indexes": ["ativa", "inicio"],
    }

    def __str__(self):
        return "%s (%s)" % (self.nome, "ativa" if self.ativa else "encerrada")


# --------------------------------------------------------------------------
# rolagens - um documento por rolagem de dado enviada pelo ESP-32
# --------------------------------------------------------------------------

TIPOS_DE_DADO = ("d4", "d6", "d8", "d10", "d12", "d20")

FACES_POR_DADO = {"d4": 4, "d6": 6, "d8": 8, "d10": 10, "d12": 12, "d20": 20}


class Rolagem(Document):
    sessao = ReferenceField(Sessao, required=True, reverse_delete_rule=CASCADE)
    personagem = ReferenceField(Personagem, required=True, reverse_delete_rule=DENY)
    dado = StringField(required=True, choices=TIPOS_DE_DADO)
    faces = IntField(required=True, min_value=2)
    resultado = IntField(required=True, min_value=1)
    # "acerto" quando sai 20 no d20, "falha" quando sai 1 no d20, senao None
    critico = StringField(choices=("acerto", "falha"), null=True, default=None)
    dispositivo = StringField(required=True, max_length=50)
    momento = DateTimeField(required=True, default=datetime.now)

    meta = {
        "collection": "rolagens",
        "indexes": [
            "sessao",
            "personagem",
            "momento",
            ("sessao", "personagem"),
        ],
        "ordering": ["-momento"],
    }

    def classificar(self):
        """Preenche faces e critico a partir do tipo de dado e do resultado."""
        self.faces = FACES_POR_DADO.get(self.dado, self.faces)
        if self.dado == "d20":
            if self.resultado == 20:
                self.critico = "acerto"
            elif self.resultado == 1:
                self.critico = "falha"
            else:
                self.critico = None
        else:
            self.critico = None
        return self

    def __str__(self):
        return "%s = %s" % (self.dado, self.resultado)


# --------------------------------------------------------------------------
# dispositivos - vinculo entre o ESP-32, o personagem e a sessao
# --------------------------------------------------------------------------

class Dispositivo(Document):
    codigo = StringField(required=True, unique=True, max_length=50)
    descricao = StringField(max_length=120)
    # NULLIFY: se o personagem ou a sessao forem apagados, o vinculo
    # vira None em vez de ficar apontando para um documento inexistente
    personagem = ReferenceField(Personagem, reverse_delete_rule=NULLIFY)
    sessao = ReferenceField(Sessao, reverse_delete_rule=NULLIFY)
    atualizado_em = DateTimeField(default=datetime.now)

    meta = {"collection": "dispositivos"}

    def __str__(self):
        alvo = self.personagem.nome if self.personagem else "sem vinculo"
        return "%s -> %s" % (self.codigo, alvo)
