"""
Testes da Ordem 3 — camada de conexão (`app/database/neo4j.py`), sem servidor.

O driver real é substituído por um duplo de teste. O que se verifica é o
contrato da camada: de onde vem a configuração, o que acontece quando falta
senha, se o driver é sempre fechado e se indisponibilidade vira `False` em vez
de exceção. A conversa com um Neo4j de verdade está em `test_carga_neo4j.py`.
"""

from __future__ import annotations

import pytest

from app.database import neo4j as conexao
from app.models import grafo

pytest.importorskip("neo4j", reason="driver neo4j não instalado")

AMBIENTE_COMPLETO = {
    "NEO4J_URI": "bolt://servidor-de-teste:7687",
    "NEO4J_USER": "usuario",
    "NEO4J_PASSWORD": "senha",
    "NEO4J_DATABASE": "roots_teste",
}


# --- Duplos de teste ----------------------------------------------------------

class _ResultadoFalso:
    def __init__(self, registro):
        self._registro = registro

    def single(self):
        return self._registro


class _RegistroFalso:
    def __init__(self, valor):
        self._valor = valor

    def value(self):
        return self._valor


class _SessaoFalsa:
    def __init__(self, valor=None):
        self.valor = valor
        self.chamadas: list[tuple[str, dict]] = []
        self.fechada = False

    def run(self, cypher, **params):
        self.chamadas.append((cypher, params))
        return _ResultadoFalso(None if self.valor is None else _RegistroFalso(self.valor))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.fechada = True
        return False


class _DriverFalso:
    def __init__(self, uri, auth=None, falha_conectividade=False, valor=None):
        self.uri = uri
        self.auth = auth
        self.falha_conectividade = falha_conectividade
        self.fechado = False
        self.database = None
        self.sessao_criada = _SessaoFalsa(valor)

    def session(self, database=None):
        self.database = database
        return self.sessao_criada

    def verify_connectivity(self):
        if self.falha_conectividade:
            raise RuntimeError("servidor indisponível")

    def close(self):
        self.fechado = True


@pytest.fixture
def driver_falso(monkeypatch):
    """Substitui `GraphDatabase.driver` e devolve o último driver criado."""
    criados: list[_DriverFalso] = []
    opcoes: dict = {"falha_conectividade": False, "valor": None}

    def fabrica(uri, auth=None, **_kwargs):
        driver = _DriverFalso(uri, auth, **opcoes)
        criados.append(driver)
        return driver

    import neo4j

    monkeypatch.setattr(neo4j.GraphDatabase, "driver", staticmethod(fabrica))
    return criados, opcoes


# --- Configuração -------------------------------------------------------------

def test_config_vem_do_ambiente():
    config = conexao.carrega_config(ambiente=AMBIENTE_COMPLETO)
    assert config.uri == "bolt://servidor-de-teste:7687"
    assert config.usuario == "usuario"
    assert config.senha == "senha"
    assert config.database == "roots_teste"


def test_config_aplica_defaults_menos_para_a_senha():
    config = conexao.carrega_config(ambiente={"NEO4J_PASSWORD": "senha"})
    assert config.uri == conexao.URI_PADRAO
    assert config.usuario == conexao.USUARIO_PADRAO
    assert config.database == conexao.DATABASE_PADRAO


@pytest.mark.parametrize("ambiente", [{}, {"NEO4J_PASSWORD": ""}, {"NEO4J_URI": "bolt://x"}])
def test_senha_ausente_levanta_em_vez_de_assumir_um_default(ambiente):
    # Nunca assumir neo4j/neo4j: uma senha padrão silenciosa é como se conecta
    # sem querer no servidor errado.
    with pytest.raises(conexao.ConfiguracaoNeo4jAusente, match="NEO4J_PASSWORD"):
        conexao.carrega_config(ambiente=ambiente)


# --- Driver e sessão ----------------------------------------------------------

def test_driver_recebe_uri_e_credenciais(driver_falso):
    criados, _ = driver_falso
    config = conexao.carrega_config(ambiente=AMBIENTE_COMPLETO)
    driver = conexao.cria_driver(config)
    assert criados == [driver]
    assert driver.uri == config.uri
    assert driver.auth == ("usuario", "senha")


def test_sessao_usa_o_database_configurado_e_fecha_tudo(driver_falso):
    criados, _ = driver_falso
    config = conexao.carrega_config(ambiente=AMBIENTE_COMPLETO)
    with conexao.sessao(config) as ses:
        assert ses is criados[0].sessao_criada
    assert criados[0].database == "roots_teste"
    assert criados[0].fechado, "o driver precisa ser fechado ao sair do context manager"
    assert criados[0].sessao_criada.fechada


def test_sessao_fecha_o_driver_mesmo_com_excecao_dentro_do_bloco(driver_falso):
    criados, _ = driver_falso
    config = conexao.carrega_config(ambiente=AMBIENTE_COMPLETO)
    with pytest.raises(ZeroDivisionError), conexao.sessao(config):
        raise ZeroDivisionError
    assert criados[0].fechado


def test_conectividade_ok(driver_falso):
    criados, _ = driver_falso
    config = conexao.carrega_config(ambiente=AMBIENTE_COMPLETO)
    assert conexao.verifica_conectividade(config) is True
    assert criados[0].fechado


def test_conectividade_falha_vira_false_e_nao_excecao(driver_falso):
    criados, opcoes = driver_falso
    opcoes["falha_conectividade"] = True
    config = conexao.carrega_config(ambiente=AMBIENTE_COMPLETO)
    assert conexao.verifica_conectividade(config) is False
    assert criados[0].fechado, "driver precisa fechar mesmo quando a verificação falha"


def test_conectividade_false_quando_nem_da_para_criar_o_driver(monkeypatch):
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    assert conexao.verifica_conectividade() is False


def test_escalar_devolve_o_valor_unico(driver_falso):
    _, opcoes = driver_falso
    opcoes["valor"] = 381
    config = conexao.carrega_config(ambiente=AMBIENTE_COMPLETO)
    with conexao.sessao(config) as ses:
        assert conexao.escalar(ses, "MATCH (n) RETURN count(n)") == 381


def test_escalar_devolve_none_quando_a_query_nao_retorna_linha(driver_falso):
    config = conexao.carrega_config(ambiente=AMBIENTE_COMPLETO)
    with conexao.sessao(config) as ses:
        assert conexao.escalar(ses, "MATCH (n:Inexistente) RETURN n") is None


def test_escalar_repassa_parametros(driver_falso):
    config = conexao.carrega_config(ambiente=AMBIENTE_COMPLETO)
    with conexao.sessao(config) as ses:
        conexao.escalar(ses, grafo.cypher_conta_orfaos(), labels=["Ingrediente"])
        cypher, params = ses.chamadas[-1]
    assert params == {"labels": ["Ingrediente"]}
    assert grafo.LABEL_OBJETO_ROOTS in cypher


# --- Queries de validação (construção do texto, sem servidor) -----------------

def test_query_de_contagem_por_label_filtra_pelos_labels_conhecidos():
    cypher = grafo.cypher_conta_nos_por_label()
    assert f"MATCH (n:{grafo.LABEL_OBJETO_ROOTS})" in cypher
    assert "WITH label WHERE label IN $labels" in cypher


def test_query_de_contagem_por_tipo_filtra_pelo_enum():
    assert "WHERE type(r) IN $tipos" in grafo.cypher_conta_relacoes_por_tipo()


def test_query_de_orfaos_procura_nos_sem_aresta():
    assert "WHERE NOT (n)--()" in grafo.cypher_conta_orfaos()


def test_query_de_rel_id_duplicado_agrupa_e_conta():
    cypher = grafo.cypher_rel_ids_duplicados()
    assert "WITH r.rel_id AS rel_id, count(*) AS n" in cypher
    assert "WHERE n > 1" in cypher


def test_query_de_peso_cobre_nulo_e_fora_da_faixa():
    # Equivalente ao CHECK (peso >= 0.0 AND peso <= 1.0) do DDL da Ordem 2,
    # mais o caso "propriedade ausente", que no grafo é possível e no SQL não.
    cypher = grafo.cypher_peso_fora_da_faixa()
    assert "r.peso IS NULL" in cypher
    assert "r.peso < 0.0 OR r.peso > 1.0" in cypher


def test_query_de_dominio_imagem_usa_os_labels_da_ontologia():
    cypher = grafo.cypher_viola_dominio_imagem("ASSOCIADO_A_POVO")
    assert "MATCH (origem)-[r:ASSOCIADO_A_POVO]->(destino)" in cypher
    # domain é owl:unionOf(Receita, Ingrediente) — as duas pontas precisam aparecer
    assert "'Receita'" in cypher and "'Ingrediente'" in cypher
    assert "'Povo'" in cypher


def test_resumo_do_modelo_expoe_o_baseline():
    resumo = grafo.ResumoModelo()
    assert resumo.total_nos_esperado == 381
    assert resumo.total_relacoes_esperado == 1585
    assert resumo.total_orfaos_esperado == 18
    assert len(resumo.constraints) == 10
    assert len(resumo.indices) == len(grafo.INDICES_DE_NO) + 2 * len(grafo.RELACOES)
