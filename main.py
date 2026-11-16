"""
Trabalho Final - Database Of Things - 270400
Alan Brum - 92305

Dado inteligente para RPG de mesa com ESP-32.
API REST em FastAPI sobre o MongoDB (MongoEngine).

Na nuvem: hospedada no Render, com o banco no MongoDB Atlas
(variavel de ambiente MONGO_URI). Documentacao interativa em /docs.

Para subir localmente, na pasta deste arquivo (sem MONGO_URI usa o
MongoDB local):
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Fluxo de uso:
  1. cria-se a sessao de jogo           POST /sessoes
  2. vincula-se o dado ao personagem    PUT  /dispositivos/esp32-01/vinculo
  3. o ESP-32 descobre quem ele e       GET  /dispositivos/esp32-01/vinculo
  4. cada rolagem do dado vira          POST /rolagens
  5. o historico e as estatisticas      GET  /rolagens, GET /sessoes/{id}/estatisticas
"""

from datetime import datetime
from typing import Literal, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from modelos import (
    FACES_POR_DADO,
    TIPOS_DE_DADO,
    Dispositivo,
    Personagem,
    Rolagem,
    Sessao,
    conectar,
)
from personagens_iniciais import garantir_personagens

app = FastAPI(
    title="API do Dado Inteligente de RPG",
    description=(
        "Trabalho final - ESP-32 que rola dados de RPG, registra cada rolagem "
        "no MongoDB e devolve historico e estatisticas por personagem e sessao. "
        "Alan Brum - 92305"
    ),
    version="1.0.0",
)

conectar()
# no banco novo (Atlas) as fichas ainda nao existem: grava na primeira subida
garantir_personagens()


@app.get("/", tags=["Status"], summary="Confere se a API esta no ar")
def status():
    return {
        "api": "Dado Inteligente de RPG",
        "status": "no ar",
        "personagens": Personagem.objects.count(),
        "documentacao": "/docs",
    }


# ==========================================================================
# Modelos Pydantic - formato JSON das requisicoes
# ==========================================================================

class SessaoEntrada(BaseModel):
    nome: str = Field(min_length=2, max_length=120, examples=["Sessao 3 - As Ruinas de Karendhal"])
    campanha: Optional[str] = Field(default=None, max_length=100, examples=["As Ruinas de Karendhal"])
    mestre: Optional[str] = Field(default=None, max_length=100, examples=["Alan"])


class VinculoEntrada(BaseModel):
    """Diz a qual personagem e sessao o dado fisico esta servindo."""

    personagem_id: str = Field(examples=["6ab30fb5e1101742fcba8a75"])
    sessao_id: str = Field(examples=["6b12c9f0a1b2c3d4e5f60718"])
    descricao: Optional[str] = Field(default=None, max_length=120, examples=["Dado da ponta da mesa"])


class RolagemEntrada(BaseModel):
    """Corpo que o ESP-32 envia a cada rolagem."""

    dispositivo: str = Field(min_length=1, max_length=50, examples=["esp32-01"])
    dado: Literal["d4", "d6", "d8", "d10", "d12", "d20"] = Field(examples=["d20"])
    resultado: int = Field(ge=1, le=20, examples=[17])


# ==========================================================================
# Funcoes auxiliares
# ==========================================================================

def para_object_id(valor: str, nome_campo: str) -> ObjectId:
    """Converte string em ObjectId, devolvendo 400 quando o formato e invalido."""
    try:
        return ObjectId(valor)
    except (InvalidId, TypeError):
        raise HTTPException(
            status_code=400,
            detail="O campo " + nome_campo + " nao e um id valido do MongoDB: " + str(valor),
        )


def personagem_resumo(personagem: Personagem) -> dict:
    return {
        "id": str(personagem.id),
        "nome": personagem.nome,
        "classe": personagem.classe,
        "nivel": personagem.nivel,
        "campanha": personagem.campanha,
    }


def sessao_resumo(sessao: Sessao) -> dict:
    return {
        "id": str(sessao.id),
        "nome": sessao.nome,
        "campanha": sessao.campanha,
        "mestre": sessao.mestre,
        "inicio": sessao.inicio,
        "fim": sessao.fim,
        "ativa": sessao.ativa,
    }


def rolagem_resumo(rolagem: Rolagem) -> dict:
    return {
        "id": str(rolagem.id),
        "sessao_id": str(rolagem.sessao.id),
        "personagem_id": str(rolagem.personagem.id),
        "personagem_nome": rolagem.personagem.nome,
        "dado": rolagem.dado,
        "faces": rolagem.faces,
        "resultado": rolagem.resultado,
        "critico": rolagem.critico,
        "dispositivo": rolagem.dispositivo,
        "momento": rolagem.momento,
    }


def estatisticas_de(consulta) -> dict:
    """Calcula total, media, maior, menor e criticos de um conjunto de rolagens."""
    total = consulta.count()
    if total == 0:
        return {
            "total_rolagens": 0,
            "media": None,
            "maior": None,
            "menor": None,
            "criticos_de_acerto": 0,
            "criticos_de_falha": 0,
            "por_dado": {},
        }

    resultados = [r.resultado for r in consulta]
    por_dado = {}
    for rolagem in consulta:
        dado = rolagem.dado
        if dado not in por_dado:
            por_dado[dado] = {"quantidade": 0, "soma": 0}
        por_dado[dado]["quantidade"] += 1
        por_dado[dado]["soma"] += rolagem.resultado
    for dado, valores in por_dado.items():
        valores["media"] = round(valores["soma"] / valores["quantidade"], 2)
        del valores["soma"]

    return {
        "total_rolagens": total,
        "media": round(sum(resultados) / total, 2),
        "maior": max(resultados),
        "menor": min(resultados),
        "criticos_de_acerto": consulta.filter(critico="acerto").count(),
        "criticos_de_falha": consulta.filter(critico="falha").count(),
        "por_dado": por_dado,
    }


# ==========================================================================
# PERSONAGENS - leitura (o cadastro ja foi feito na atividade anterior)
# ==========================================================================

@app.get("/personagens", tags=["Personagens"], summary="Lista os personagens")
def listar_personagens():
    personagens = Personagem.objects.order_by("nome")
    return {
        "total": personagens.count(),
        "personagens": [personagem_resumo(p) for p in personagens],
    }


@app.get("/personagens/{personagem_id}", tags=["Personagens"], summary="Busca um personagem pelo ID")
def obter_personagem(personagem_id: str):
    personagem = Personagem.objects(id=para_object_id(personagem_id, "personagem_id")).first()
    if personagem is None:
        raise HTTPException(status_code=404, detail="Personagem nao encontrado: " + personagem_id)

    dados = personagem_resumo(personagem)
    dados["raca"] = personagem.raca
    dados["jogador"] = personagem.jogador
    dados["sistema"] = personagem.sistema
    dados["alinhamento"] = personagem.alinhamento
    dados["vivo"] = personagem.vivo
    dados["pericias"] = list(personagem.pericias)
    if personagem.atributos:
        dados["atributos"] = {
            "forca": personagem.atributos.forca,
            "destreza": personagem.atributos.destreza,
            "constituicao": personagem.atributos.constituicao,
            "inteligencia": personagem.atributos.inteligencia,
            "sabedoria": personagem.atributos.sabedoria,
            "carisma": personagem.atributos.carisma,
        }
    if personagem.pontos_vida:
        dados["pontos_vida"] = {
            "atual": personagem.pontos_vida.atual,
            "maximo": personagem.pontos_vida.maximo,
        }
    dados["inventario"] = [
        {"item": i.item, "quantidade": i.quantidade} for i in personagem.inventario
    ]
    return dados


@app.get(
    "/personagens/{personagem_id}/estatisticas",
    tags=["Personagens"],
    summary="Estatisticas de rolagem de um personagem",
)
def estatisticas_do_personagem(personagem_id: str, sessao_id: Optional[str] = None):
    personagem = Personagem.objects(id=para_object_id(personagem_id, "personagem_id")).first()
    if personagem is None:
        raise HTTPException(status_code=404, detail="Personagem nao encontrado: " + personagem_id)

    consulta = Rolagem.objects(personagem=personagem)
    if sessao_id:
        consulta = consulta.filter(sessao=para_object_id(sessao_id, "sessao_id"))

    return {
        "personagem": personagem_resumo(personagem),
        "sessao_id": sessao_id,
        "estatisticas": estatisticas_de(consulta),
    }


# ==========================================================================
# SESSOES - CRUD da partida
# ==========================================================================

@app.post("/sessoes", status_code=201, tags=["Sessoes"], summary="Abre uma sessao de jogo")
def criar_sessao(dados: SessaoEntrada):
    sessao = Sessao(
        nome=dados.nome,
        campanha=dados.campanha,
        mestre=dados.mestre,
        inicio=datetime.now(),
        ativa=True,
    ).save()
    return {"mensagem": "Sessao aberta com sucesso", "sessao": sessao_resumo(sessao)}


@app.get("/sessoes", tags=["Sessoes"], summary="Lista as sessoes")
def listar_sessoes(ativa: Optional[bool] = None):
    consulta = Sessao.objects
    if ativa is not None:
        consulta = consulta.filter(ativa=ativa)
    consulta = consulta.order_by("-inicio")
    return {"total": consulta.count(), "sessoes": [sessao_resumo(s) for s in consulta]}


@app.get("/sessoes/{sessao_id}", tags=["Sessoes"], summary="Busca uma sessao pelo ID")
def obter_sessao(sessao_id: str):
    sessao = Sessao.objects(id=para_object_id(sessao_id, "sessao_id")).first()
    if sessao is None:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada: " + sessao_id)
    return sessao_resumo(sessao)


@app.put("/sessoes/{sessao_id}", tags=["Sessoes"], summary="Atualiza os dados de uma sessao")
def atualizar_sessao(sessao_id: str, dados: SessaoEntrada):
    sessao = Sessao.objects(id=para_object_id(sessao_id, "sessao_id")).first()
    if sessao is None:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada: " + sessao_id)

    sessao.nome = dados.nome
    sessao.campanha = dados.campanha
    sessao.mestre = dados.mestre
    sessao.save()
    return {"mensagem": "Sessao atualizada com sucesso", "sessao": sessao_resumo(sessao)}


@app.put("/sessoes/{sessao_id}/encerrar", tags=["Sessoes"], summary="Encerra a sessao")
def encerrar_sessao(sessao_id: str):
    sessao = Sessao.objects(id=para_object_id(sessao_id, "sessao_id")).first()
    if sessao is None:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada: " + sessao_id)
    if not sessao.ativa:
        raise HTTPException(status_code=409, detail="Esta sessao ja foi encerrada")

    sessao.ativa = False
    sessao.fim = datetime.now()
    sessao.save()
    return {"mensagem": "Sessao encerrada", "sessao": sessao_resumo(sessao)}


@app.delete("/sessoes/{sessao_id}", tags=["Sessoes"], summary="Remove a sessao e suas rolagens")
def excluir_sessao(sessao_id: str):
    sessao = Sessao.objects(id=para_object_id(sessao_id, "sessao_id")).first()
    if sessao is None:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada: " + sessao_id)

    # reverse_delete_rule=CASCADE no modelo apaga junto as rolagens da sessao
    quantidade = Rolagem.objects(sessao=sessao).count()
    sessao.delete()
    return {
        "mensagem": "Sessao removida com sucesso",
        "rolagens_removidas_em_cascata": quantidade,
    }


@app.get(
    "/sessoes/{sessao_id}/estatisticas",
    tags=["Sessoes"],
    summary="Estatisticas da sessao, no total e por personagem",
)
def estatisticas_da_sessao(sessao_id: str):
    sessao = Sessao.objects(id=para_object_id(sessao_id, "sessao_id")).first()
    if sessao is None:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada: " + sessao_id)

    rolagens = Rolagem.objects(sessao=sessao)
    por_personagem = []
    # distinct("personagem") ja devolve os documentos Personagem desreferenciados
    for personagem in rolagens.distinct("personagem"):
        if personagem is None:
            continue
        por_personagem.append(
            {
                "personagem": personagem_resumo(personagem),
                "estatisticas": estatisticas_de(rolagens.filter(personagem=personagem)),
            }
        )

    return {
        "sessao": sessao_resumo(sessao),
        "estatisticas_gerais": estatisticas_de(rolagens),
        "por_personagem": por_personagem,
    }


# ==========================================================================
# DISPOSITIVOS - vinculo entre o ESP-32, o personagem e a sessao
# ==========================================================================

@app.get(
    "/dispositivos",
    tags=["Dispositivos"],
    summary="Lista os dados fisicos cadastrados",
)
def listar_dispositivos():
    dispositivos = Dispositivo.objects.order_by("codigo")
    return {
        "total": dispositivos.count(),
        "dispositivos": [
            {
                "codigo": d.codigo,
                "descricao": d.descricao,
                "personagem": personagem_resumo(d.personagem) if d.personagem else None,
                "sessao": sessao_resumo(d.sessao) if d.sessao else None,
                "atualizado_em": d.atualizado_em,
            }
            for d in dispositivos
        ],
    }


@app.get(
    "/dispositivos/{codigo}/vinculo",
    tags=["Dispositivos"],
    summary="O ESP-32 pergunta a quem ele esta servindo",
)
def obter_vinculo(codigo: str):
    """Endpoint consumido pelo ESP-32 ao ligar, para mostrar o nome no LCD."""
    dispositivo = Dispositivo.objects(codigo=codigo).first()
    if dispositivo is None:
        raise HTTPException(status_code=404, detail="Dispositivo nao cadastrado: " + codigo)

    vinculado = dispositivo.personagem is not None and dispositivo.sessao is not None
    return {
        "codigo": dispositivo.codigo,
        "vinculado": vinculado,
        "personagem_nome": dispositivo.personagem.nome if dispositivo.personagem else None,
        "personagem_id": str(dispositivo.personagem.id) if dispositivo.personagem else None,
        "sessao_nome": dispositivo.sessao.nome if dispositivo.sessao else None,
        "sessao_id": str(dispositivo.sessao.id) if dispositivo.sessao else None,
        "sessao_ativa": dispositivo.sessao.ativa if dispositivo.sessao else None,
    }


@app.put(
    "/dispositivos/{codigo}/vinculo",
    tags=["Dispositivos"],
    summary="Vincula o dado a um personagem e a uma sessao",
)
def definir_vinculo(codigo: str, dados: VinculoEntrada):
    personagem = Personagem.objects(id=para_object_id(dados.personagem_id, "personagem_id")).first()
    if personagem is None:
        raise HTTPException(status_code=404, detail="Personagem nao encontrado: " + dados.personagem_id)

    sessao = Sessao.objects(id=para_object_id(dados.sessao_id, "sessao_id")).first()
    if sessao is None:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada: " + dados.sessao_id)
    if not sessao.ativa:
        raise HTTPException(status_code=409, detail="Nao da para vincular o dado a uma sessao encerrada")

    # cria o dispositivo na primeira vez que ele aparece
    dispositivo = Dispositivo.objects(codigo=codigo).first()
    if dispositivo is None:
        dispositivo = Dispositivo(codigo=codigo)

    dispositivo.descricao = dados.descricao or dispositivo.descricao
    dispositivo.personagem = personagem
    dispositivo.sessao = sessao
    dispositivo.atualizado_em = datetime.now()
    dispositivo.save()

    return {
        "mensagem": "Dado vinculado com sucesso",
        "codigo": dispositivo.codigo,
        "personagem": personagem_resumo(personagem),
        "sessao": sessao_resumo(sessao),
    }


@app.delete(
    "/dispositivos/{codigo}/vinculo",
    tags=["Dispositivos"],
    summary="Desvincula o dado do personagem",
)
def remover_vinculo(codigo: str):
    dispositivo = Dispositivo.objects(codigo=codigo).first()
    if dispositivo is None:
        raise HTTPException(status_code=404, detail="Dispositivo nao cadastrado: " + codigo)

    dispositivo.personagem = None
    dispositivo.sessao = None
    dispositivo.atualizado_em = datetime.now()
    dispositivo.save()
    return {"mensagem": "Vinculo removido", "codigo": dispositivo.codigo}


# ==========================================================================
# ROLAGENS - o coracao do trabalho: o que o ESP-32 grava
# ==========================================================================

@app.post("/rolagens", status_code=201, tags=["Rolagens"], summary="Registra uma rolagem do dado")
def registrar_rolagem(dados: RolagemEntrada):
    """
    Chamado pelo ESP-32 a cada rolagem.

    Regras de negocio:
      - o dispositivo precisa estar cadastrado e vinculado a personagem e sessao;
      - a sessao precisa estar ativa;
      - o resultado precisa caber no numero de faces do dado (1 ate faces);
      - o critico e calculado aqui, nao enviado pelo ESP-32:
        no d20, 20 e acerto critico e 1 e falha critica.
    """
    dispositivo = Dispositivo.objects(codigo=dados.dispositivo).first()
    if dispositivo is None:
        raise HTTPException(status_code=404, detail="Dispositivo nao cadastrado: " + dados.dispositivo)

    if dispositivo.personagem is None or dispositivo.sessao is None:
        raise HTTPException(
            status_code=409,
            detail="O dispositivo " + dados.dispositivo + " nao esta vinculado a um personagem e a uma sessao",
        )

    if not dispositivo.sessao.ativa:
        raise HTTPException(status_code=409, detail="A sessao vinculada a este dispositivo ja foi encerrada")

    faces = FACES_POR_DADO[dados.dado]
    if dados.resultado > faces:
        raise HTTPException(
            status_code=422,
            detail="Resultado " + str(dados.resultado) + " impossivel em um " + dados.dado + " (maximo " + str(faces) + ")",
        )

    rolagem = Rolagem(
        sessao=dispositivo.sessao,
        personagem=dispositivo.personagem,
        dado=dados.dado,
        resultado=dados.resultado,
        dispositivo=dados.dispositivo,
        momento=datetime.now(),
    ).classificar()
    rolagem.save()

    return {"mensagem": "Rolagem registrada", "rolagem": rolagem_resumo(rolagem)}


@app.get("/rolagens", tags=["Rolagens"], summary="Historico de rolagens")
def listar_rolagens(
    sessao_id: Optional[str] = None,
    personagem_id: Optional[str] = None,
    dado: Optional[str] = None,
    somente_criticos: bool = False,
    limite: int = Query(default=50, ge=1, le=500),
):
    consulta = Rolagem.objects
    if sessao_id:
        consulta = consulta.filter(sessao=para_object_id(sessao_id, "sessao_id"))
    if personagem_id:
        consulta = consulta.filter(personagem=para_object_id(personagem_id, "personagem_id"))
    if dado:
        if dado not in TIPOS_DE_DADO:
            raise HTTPException(status_code=422, detail="Tipo de dado invalido: " + dado)
        consulta = consulta.filter(dado=dado)
    if somente_criticos:
        consulta = consulta.filter(critico__ne=None)

    total = consulta.count()
    consulta = consulta.order_by("-momento").limit(limite)
    return {
        "total": total,
        "exibindo": min(total, limite),
        "rolagens": [rolagem_resumo(r) for r in consulta],
    }


@app.get("/rolagens/{rolagem_id}", tags=["Rolagens"], summary="Busca uma rolagem pelo ID")
def obter_rolagem(rolagem_id: str):
    rolagem = Rolagem.objects(id=para_object_id(rolagem_id, "rolagem_id")).first()
    if rolagem is None:
        raise HTTPException(status_code=404, detail="Rolagem nao encontrada: " + rolagem_id)
    return rolagem_resumo(rolagem)


@app.delete("/rolagens/{rolagem_id}", tags=["Rolagens"], summary="Anula uma rolagem")
def excluir_rolagem(rolagem_id: str):
    """Serve para o mestre anular uma rolagem registrada por engano."""
    rolagem = Rolagem.objects(id=para_object_id(rolagem_id, "rolagem_id")).first()
    if rolagem is None:
        raise HTTPException(status_code=404, detail="Rolagem nao encontrada: " + rolagem_id)

    resumo = rolagem_resumo(rolagem)
    rolagem.delete()
    return {"mensagem": "Rolagem anulada", "rolagem": resumo}
