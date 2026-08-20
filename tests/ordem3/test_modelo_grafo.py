"""Testes do modelo de grafo da Ordem 3 — rodam offline, sem Neo4j.

O ponto destes testes é impedir que `app/models/grafo.py` e
`schemas/ontologia.ttl` divirjam: o modelo do Neo4j é uma tradução da ontologia,
e uma tradução que sai de sincronia em silêncio é pior do que não ter tradução.
Por isso a ontologia é lida do arquivo e comparada com o modelo, em vez de as
duas listas serem simplesmente escritas duas vezes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.models.grafo import (  # noqa: E402
    CONSTRAINTS,
    ENTIDADES,
    INDICES,
    LABEL_SUPERCLASSE,
    LABELS,
    PROPRIEDADES_ARESTA,
    TIPO_RELACAO_POR_NOME,
    TIPOS_RELACAO,
    TOTAL_OBJETOS_ESPERADO,
    TOTAL_RELACOES_ESPERADO,
    label_do_id,
    valida_aresta,
)

ONTOLOGIA = (RAIZ / "schemas" / "ontologia.ttl").read_text(encoding="utf-8")


# =============================================================
# Paridade com a ontologia (Ordem 1)
# =============================================================


def test_todo_owl_class_do_corpus_virou_label() -> None:
    """As 8 subclasses de roots:ObjetoRoots viram exatamente os 8 labels."""
    classes = set(
        re.findall(r"roots:(\w+) a owl:Class ;\s*rdfs:subClassOf roots:ObjetoRoots", ONTOLOGIA)
    )
    assert classes == set(LABELS)
    assert len(LABELS) == 8


def test_todo_object_property_virou_tipo_de_relacao() -> None:
    """Os 12 owl:ObjectProperty viram exatamente os 12 tipos de relação."""
    propriedades = set(re.findall(r"roots:(\w+) a owl:ObjectProperty", ONTOLOGIA))
    assert propriedades == set(TIPO_RELACAO_POR_NOME)
    assert len(TIPOS_RELACAO) == 12


def test_superclasse_existe_na_ontologia() -> None:
    """O label extra em todo nó corresponde a uma classe real da ontologia."""
    assert f"roots:{LABEL_SUPERCLASSE} a owl:Class" in ONTOLOGIA


def test_dominio_e_alcance_sao_labels_conhecidos() -> None:
    """Nenhum domain/range aponta para um label que não existe."""
    for definicao in TIPOS_RELACAO:
        assert definicao.dominio <= LABELS, definicao.tipo
        assert definicao.alcance <= LABELS, definicao.tipo
        assert definicao.dominio and definicao.alcance, definicao.tipo


def test_unioes_owl_preservadas() -> None:
    """As duas uniões declaradas em OWL sobrevivem à tradução.

    ASSOCIADO_A_POVO tem domain `owl:unionOf (Receita Ingrediente)` e
    ORIGINARIO_DE tem range `owl:unionOf (Povo Bioma)`. Achatar qualquer uma
    delas para um único label rejeitaria arestas legítimas do corpus.
    """
    assert TIPO_RELACAO_POR_NOME["ASSOCIADO_A_POVO"].dominio == {"Receita", "Ingrediente"}
    assert TIPO_RELACAO_POR_NOME["ORIGINARIO_DE"].alcance == {"Povo", "Bioma"}


def test_reservados_sao_os_dois_sem_instancia() -> None:
    """VARIANTE_REGIONAL e SIMILAR_A: 0 instâncias, marcados como reservados."""
    reservados = {d.tipo for d in TIPOS_RELACAO if d.reservado}
    assert reservados == {"VARIANTE_REGIONAL", "SIMILAR_A"}
    for tipo in reservados:
        assert TIPO_RELACAO_POR_NOME[tipo].instancias_esperadas == 0


# =============================================================
# Paridade com o baseline da Auditoria Sprint 2 (Ordem 2)
# =============================================================


def test_baseline_de_nos_bate_com_a_ordem_2() -> None:
    """Contagem por entidade idêntica ao dicionário `esperado` do ETL da Ordem 2."""
    esperado = {"Ingrediente": 130, "Receita": 136, "Tecnica": 38, "Povo": 17,
                "Territorio": 18, "Patrimonio": 35, "Bioma": 7, "LivroFonte": 0}
    assert {e.label: e.instancias_esperadas for e in ENTIDADES} == esperado
    assert sum(esperado.values()) == TOTAL_OBJETOS_ESPERADO == 381


def test_baseline_de_arestas_bate_com_mv_grafo_agregado() -> None:
    """Contagem por tipo idêntica à view `mv_grafo_agregado` conferida na Ordem 2."""
    esperado = {"USA_INGREDIENTE": 895, "ASSOCIADO_A_POVO": 205, "CULTIVADO_EM": 106,
                "UTILIZA_TECNICA": 85, "PREPARADO_COM": 81, "OCORRE_EM": 77,
                "ORIGINARIO_DE": 67, "PATRIMONIO_DE": 38, "LOCALIZADO_EM_BIOMA": 24,
                "DERIVA_DE": 7, "VARIANTE_REGIONAL": 0, "SIMILAR_A": 0}
    assert {d.tipo: d.instancias_esperadas for d in TIPOS_RELACAO} == esperado
    assert sum(esperado.values()) == TOTAL_RELACOES_ESPERADO == 1585


def test_prefixos_sao_os_da_politica_de_identificadores() -> None:
    """Prefixos de ID conforme Dicionário v1.2, Seção 3."""
    assert {e.prefixo for e in ENTIDADES} == {"ING", "REC", "TEC", "POV", "TER", "PAT", "BIO", "LIV"}


# =============================================================
# Resolução da FK polimórfica por prefixo
# =============================================================


@pytest.mark.parametrize(
    ("id_legivel", "label"),
    [("ING-000001", "Ingrediente"), ("REC-000136", "Receita"), ("TEC-000038", "Tecnica"),
     ("POV-000017", "Povo"), ("TER-000018", "Territorio"), ("PAT-000035", "Patrimonio"),
     ("BIO-000007", "Bioma"), ("LIV-000001", "LivroFonte")],
)
def test_label_do_id(id_legivel: str, label: str) -> None:
    assert label_do_id(id_legivel) == label


def test_label_do_id_rejeita_prefixo_desconhecido() -> None:
    """Prefixo fora da política não vira label chutado — levanta erro."""
    with pytest.raises(ValueError, match="não corresponde a nenhuma"):
        label_do_id("XYZ-000001")


# =============================================================
# Validação de aresta contra domain/range
# =============================================================


def test_aresta_valida_passa() -> None:
    valida_aresta("Receita", "USA_INGREDIENTE", "Ingrediente")
    valida_aresta("Ingrediente", "ASSOCIADO_A_POVO", "Povo")  # domain via união
    valida_aresta("Receita", "ASSOCIADO_A_POVO", "Povo")  # domain via união
    valida_aresta("Ingrediente", "ORIGINARIO_DE", "Bioma")  # range via união
    valida_aresta("Ingrediente", "ORIGINARIO_DE", "Povo")  # range via união


def test_aresta_com_origem_errada_e_rejeitada() -> None:
    with pytest.raises(ValueError, match="rdfs:domain"):
        valida_aresta("Povo", "USA_INGREDIENTE", "Ingrediente")


def test_aresta_com_destino_errado_e_rejeitada() -> None:
    with pytest.raises(ValueError, match="rdfs:range"):
        valida_aresta("Receita", "USA_INGREDIENTE", "Receita")


def test_tipo_inexistente_e_rejeitado() -> None:
    with pytest.raises(ValueError, match="não existe na ontologia"):
        valida_aresta("Receita", "CONTEM", "Ingrediente")


# =============================================================
# DDL do grafo
# =============================================================


def test_constraints_sao_idempotentes_e_de_unicidade() -> None:
    """Só constraints de unicidade de nó — o único tipo que roda no Community."""
    assert len(CONSTRAINTS) == 2
    for c in CONSTRAINTS:
        assert "IF NOT EXISTS" in c, c
        assert "IS UNIQUE" in c, c
        assert "IS NOT NULL" not in c, "constraint de existência exige Enterprise"
        assert f":{LABEL_SUPERCLASSE}" in c, "unicidade deve valer sobre todo o corpus"


def test_constraints_cobrem_id_e_uuid() -> None:
    alvos = {"n.id" if "n.id IS UNIQUE" in c else "n.uuid" for c in CONSTRAINTS}
    assert alvos == {"n.id", "n.uuid"}


def test_indices_sao_idempotentes() -> None:
    for i in INDICES:
        assert "IF NOT EXISTS" in i, i


def test_ha_indice_de_confiabilidade_para_cada_tipo_de_relacao() -> None:
    """Espelha idx_relacoes_confiabilidade do DDL da Ordem 2, por tipo."""
    for definicao in TIPOS_RELACAO:
        assert any(f"[r:{definicao.tipo}]" in i for i in INDICES), definicao.tipo


def test_indice_fulltext_cobre_as_oito_entidades() -> None:
    fulltext = [i for i in INDICES if "FULLTEXT" in i]
    assert len(fulltext) == 1
    for entidade in ENTIDADES:
        assert entidade.label in fulltext[0]


def test_propriedades_de_aresta_cobrem_as_colunas_de_relacoes() -> None:
    """As colunas próprias de `relacoes` viram propriedades nativas da aresta.

    É o ganho que a ontologia da Ordem 1 delegou explicitamente a esta Ordem:
    em RDF isso exigiria reificação.
    """
    assert set(PROPRIEDADES_ARESTA) == {
        "rel_id", "fonte", "pagina", "confiabilidade",
        "observacoes", "data_criacao", "peso", "metodo_calculo_peso",
    }
