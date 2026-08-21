"""
Roots of Brazil — metadados dos recursos da API (Ordem 4).

Fonte única da verdade para os 7 recursos da Especificação Conceitual v1.1:
quais campos cada um expõe, quais filtros aceita, e por qual relação do grafo
cada endpoint de navegação caminha.

Tanto `api/gerar_openapi.py` quanto os routers de `app/api/` leem daqui. Não é
conveniência: se a especificação OpenAPI e o servidor tivessem cada um a sua
lista de campos, elas divergiriam na primeira alteração, e o contrato
publicado deixaria de descrever o que a API realmente devolve.

Os campos vêm do Dicionário de Dados Oficial v1.2, materializados em
`schemas/ddl_sqlite.sql` na Ordem 2 — usar o DDL como origem garante a
restrição da Ordem 4 de que nenhum endpoint expõe campo ausente do Dicionário.

Este módulo não altera nada das Ordens 1-3; `app/models/grafo.py` (Ordem 3) é
importado apenas para leitura, para reaproveitar os tipos de relação já
validados contra a ontologia.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

Sentido = Literal["direta", "inversa"]


# =============================================================
# Blocos transversais do Dicionário v1.2 (Seções 2-9)
# =============================================================

#: Presentes em todo Objeto Roots. Seções 3, 4, 5, 6, 7.
CAMPOS_IDENTIDADE: Final[tuple[str, ...]] = (
    "id", "uuid", "slug", "created_at", "updated_at", "version",
)

#: Internacionalização — Seção 8. Nome em 8 idiomas, descrição em 3.
CAMPOS_I18N: Final[tuple[str, ...]] = (
    "nome_pt", "nome_en", "nome_es", "nome_fr", "nome_it", "nome_de", "nome_ja", "nome_zh",
    "descricao_pt", "descricao_en", "descricao_es",
)

#: Taxonomia expandida — Seção 9. Sete níveis, do mais amplo ao mais específico.
CAMPOS_TAXONOMIA: Final[tuple[str, ...]] = (
    "macrogrupo", "grupo", "ordem_taxonomica", "familia", "classe", "categoria", "subcategoria",
)

#: Geodados — Seção 10. Só Território e Bioma.
CAMPOS_GEO: Final[tuple[str, ...]] = ("latitude", "longitude", "bounding_box", "geometry")

#: Propriedades próprias da aresta — Seção 20. Ficam em `relacoes`, e no grafo
#: são propriedades nativas (ver relatório da Ordem 3).
CAMPOS_ARESTA: Final[tuple[str, ...]] = (
    "rel_id", "origem_id", "destino_id", "tipo_relacao",
    "fonte", "pagina", "confiabilidade", "observacoes", "data_criacao",
    "peso", "metodo_calculo_peso",
)


# =============================================================
# Navegação — Seção 2 da Especificação Conceitual
# =============================================================


@dataclass(frozen=True)
class Navegacao:
    """Um endpoint /v1/{recurso}/{id}/{sub}, resolvido pelo grafo (Ordem 3).

    `sentido` diz se caminhamos na direção declarada da relação na ontologia
    ou contra ela. Ex.: USA_INGREDIENTE vai de Receita para Ingrediente; o
    endpoint /v1/ingredientes/{id}/receitas percorre a mesma aresta ao
    contrário, então é "inversa".

    `tipos` é uma tupla porque dois endpoints da Especificação juntam mais de
    uma relação: /v1/povos/{id}/ingredientes e /v1/ingredientes/{id}/povos
    combinam ASSOCIADO_A_POVO e ORIGINARIO_DE, exatamente como a Seção 2.4
    descreve.
    """

    sub: str
    tipos: tuple[str, ...]
    sentido: Sentido
    recurso_destino: str
    descricao: str
    #: True quando a Especificação nomeia o sub-recurso no singular e espera
    #: um objeto, não uma lista (só /v1/receitas/{id}/territorio).
    singular: bool = False


@dataclass(frozen=True)
class Recurso:
    """Um dos 7 recursos de primeira classe da Especificação Conceitual."""

    nome: str                      # segmento de path: "ingredientes"
    singular: str                  # nome do schema: "Ingrediente"
    tabela: str                    # tabela do banco relacional (Ordem 2)
    label: str                     # label do grafo (Ordem 3)
    prefixo: str                   # prefixo do ID legível: "ING"
    campo_nome: str                # coluna que carrega o nome próprio
    aba_workbook: str              # Seção 7 da Especificação: rastreabilidade
    filtros: tuple[str, ...]       # parâmetros de query da Seção 2
    navegacoes: tuple[Navegacao, ...] = ()
    campos_proprios: tuple[str, ...] = ()
    tem_geo: bool = False
    exemplo_id: str = ""


RECURSOS: Final[tuple[Recurso, ...]] = (
    Recurso(
        nome="ingredientes", singular="Ingrediente", tabela="ingrediente",
        label="Ingrediente", prefixo="ING", campo_nome="nome_principal",
        aba_workbook="1. Catálogo Ingredientes",
        # Seção 2.1: categoria, subcategoria, classe, confiabilidade, bioma, q
        filtros=("categoria", "subcategoria", "classe", "confiabilidade", "bioma", "q"),
        campos_proprios=(
            "nome_principal", "nomes_regionais", "origem_texto", "estado_regiao",
            "bioma_texto", "confiabilidade", "n_livros_fonte", "n_citacoes",
            "origem_registro", "liv_id",
        ),
        navegacoes=(
            Navegacao("receitas", ("USA_INGREDIENTE",), "inversa", "receitas",
                      "Receitas que usam este ingrediente"),
            Navegacao("territorios", ("CULTIVADO_EM",), "direta", "territorios",
                      "Territórios onde o ingrediente é cultivado"),
            Navegacao("povos", ("ASSOCIADO_A_POVO", "ORIGINARIO_DE"), "direta", "povos",
                      "Povos associados ao ingrediente ou dos quais ele é originário"),
        ),
        exemplo_id="ING-000031",
    ),
    Recurso(
        nome="receitas", singular="Receita", tabela="receita",
        label="Receita", prefixo="REC", campo_nome="nome",
        aba_workbook="2. Catálogo Receitas",
        # Seção 2.2: categoria, estado, regiao, confiabilidade, q
        filtros=("categoria", "estado", "regiao", "confiabilidade", "q"),
        campos_proprios=(
            "nome", "estado", "regiao", "influencia_cultural",
            "n_versoes_catalogadas", "livros_fonte", "liv_id", "confiabilidade",
        ),
        navegacoes=(
            Navegacao("ingredientes", ("USA_INGREDIENTE",), "direta", "ingredientes",
                      "Ingredientes da receita"),
            Navegacao("tecnicas", ("UTILIZA_TECNICA",), "direta", "tecnicas",
                      "Técnicas empregadas no preparo"),
            # A Especificação escreve este no SINGULAR — "Território de origem
            # da receita". Preservado como está: o path é /territorio.
            Navegacao("territorio", ("OCORRE_EM",), "direta", "territorios",
                      "Território de origem da receita", singular=True),
            Navegacao("povos", ("ASSOCIADO_A_POVO",), "direta", "povos",
                      "Povos de influência cultural"),
        ),
        exemplo_id="REC-000001",
    ),
    Recurso(
        nome="tecnicas", singular="Tecnica", tabela="tecnica",
        label="Tecnica", prefixo="TEC", campo_nome="nome",
        aba_workbook="3. Catálogo Técnicas",
        filtros=("categoria", "subcategoria", "confiabilidade", "q"),
        campos_proprios=(
            "nome", "descricao", "ingredientes_utilizados", "receitas",
            "origem_cultural", "livros_fonte", "liv_id", "confiabilidade",
        ),
        navegacoes=(
            Navegacao("ingredientes", ("PREPARADO_COM",), "direta", "ingredientes",
                      "Ingredientes preparados com esta técnica"),
            Navegacao("receitas", ("UTILIZA_TECNICA",), "inversa", "receitas",
                      "Receitas que empregam esta técnica"),
        ),
        exemplo_id="TEC-000001",
    ),
    Recurso(
        nome="povos", singular="Povo", tabela="povo",
        label="Povo", prefixo="POV", campo_nome="povo",
        aba_workbook="4. Catálogo Povos",
        filtros=("categoria", "regiao", "confiabilidade", "q"),
        campos_proprios=(
            "povo", "regiao", "ingredientes_associados", "receitas",
            "praticas_culinarias", "livros_fonte", "liv_id", "confiabilidade",
        ),
        navegacoes=(
            Navegacao("ingredientes", ("ASSOCIADO_A_POVO", "ORIGINARIO_DE"), "inversa",
                      "ingredientes", "Ingredientes associados ao povo ou dele originários"),
            Navegacao("receitas", ("ASSOCIADO_A_POVO",), "inversa", "receitas",
                      "Receitas associadas ao povo"),
            Navegacao("patrimonio", ("PATRIMONIO_DE",), "inversa", "patrimonio",
                      "Itens de patrimônio do povo"),
        ),
        exemplo_id="POV-000001",
    ),
    Recurso(
        nome="territorios", singular="Territorio", tabela="territorio",
        label="Territorio", prefixo="TER", campo_nome="estado",
        aba_workbook="5. Catálogo Territórios",
        filtros=("categoria", "confiabilidade", "q"),
        campos_proprios=(
            "estado", "bioma_texto", "ingredientes", "receitas",
            "produtos_tradicionais", "livros_fonte", "liv_id", "confiabilidade",
        ),
        tem_geo=True,
        navegacoes=(
            Navegacao("receitas", ("OCORRE_EM",), "inversa", "receitas",
                      "Receitas que ocorrem no território"),
            Navegacao("ingredientes", ("CULTIVADO_EM",), "inversa", "ingredientes",
                      "Ingredientes cultivados no território"),
            Navegacao("biomas", ("LOCALIZADO_EM_BIOMA",), "direta", "biomas",
                      "Biomas em que o território se localiza"),
        ),
        exemplo_id="TER-000001",
    ),
    Recurso(
        nome="biomas", singular="Bioma", tabela="bioma",
        label="Bioma", prefixo="BIO", campo_nome="nome",
        aba_workbook="12. Catálogo Biomas",
        filtros=("oficial_ibge", "q"),
        campos_proprios=(
            "nome", "descricao", "territorios_associados_n",
            "ingredientes_associados_n", "fonte", "oficial_ibge",
        ),
        tem_geo=True,
        navegacoes=(
            Navegacao("territorios", ("LOCALIZADO_EM_BIOMA",), "inversa", "territorios",
                      "Territórios localizados neste bioma"),
            Navegacao("ingredientes", ("ORIGINARIO_DE",), "inversa", "ingredientes",
                      "Ingredientes originários deste bioma"),
        ),
        exemplo_id="BIO-000001",
    ),
    Recurso(
        nome="patrimonio", singular="Patrimonio", tabela="patrimonio",
        label="Patrimonio", prefixo="PAT", campo_nome="elemento",
        aba_workbook="6. Catálogo Patrimônio",
        # Seção 2.7 cita explicitamente apenas ?categoria=
        filtros=("categoria", "confiabilidade", "q"),
        campos_proprios=(
            "categoria", "elemento", "descricao", "povo_regiao_relacionada",
            "livros_fonte", "liv_id", "confiabilidade",
        ),
        navegacoes=(
            # A Especificação nomeia o sub-recurso "povos_territorios", mas a
            # única relação que ela associa a ele é PATRIMONIO_DE, cujo range
            # na ontologia é Povo (38 instâncias, nenhuma para Território).
            # Mantido o nome do path como na Especificação e devolvido o que a
            # relação de fato alcança — divergência registrada no relatório,
            # sem inventar arestas para Território que o corpus não tem.
            Navegacao("povos_territorios", ("PATRIMONIO_DE",), "direta", "povos",
                      "Povos aos quais o item de patrimônio pertence"),
        ),
        exemplo_id="PAT-000001",
    ),
)

RECURSO_POR_NOME: Final[dict[str, Recurso]] = {r.nome: r for r in RECURSOS}
RECURSO_POR_PREFIXO: Final[dict[str, Recurso]] = {r.prefixo: r for r in RECURSOS}
RECURSO_POR_LABEL: Final[dict[str, Recurso]] = {r.label: r for r in RECURSOS}


def campos_de(recurso: Recurso) -> tuple[str, ...]:
    """Todos os campos que o recurso expõe, na ordem em que aparecem no schema.

    A união dos blocos transversais com os campos próprios. Nenhum campo fora
    desta lista chega à resposta — é assim que a restrição "nenhum endpoint
    expõe campo ausente do Dicionário v1.2" fica garantida por construção, e
    não por revisão manual.
    """
    campos: list[str] = list(CAMPOS_IDENTIDADE)
    for c in recurso.campos_proprios:
        if c not in campos:
            campos.append(c)
    for c in CAMPOS_TAXONOMIA:
        if c not in campos:
            campos.append(c)
    if recurso.tem_geo:
        campos.extend(CAMPOS_GEO)
    campos.extend(CAMPOS_I18N)
    return tuple(campos)


# =============================================================
# Domínios — Seções 5.3 e 11 do Dicionário / Especificação
# =============================================================

#: Os 4 valores canônicos de confiabilidade. O Dicionário v1.2 (Seção 11)
#: permite texto livre após o emoji — a Ordem 2 encontrou "🔵 Inferido com
#: cautela" no corpus real — então o FILTRO casa por prefixo de emoji, não por
#: igualdade. Estes são os rótulos aceitos no parâmetro de query.
CONFIABILIDADES: Final[tuple[str, ...]] = (
    "🟢 Confirmado em várias fontes",
    "🟡 Confirmado em uma única fonte",
    "🔵 Inferido",
    "🔴 Pendente de validação",
)

#: Mapa rótulo -> emoji, para o filtro por prefixo.
EMOJI_CONFIABILIDADE: Final[dict[str, str]] = {r: r[0] for r in CONFIABILIDADES}

#: Códigos de erro da Seção 5.3 da Especificação Conceitual, com o HTTP status
#: que cada um carrega.
ERROS: Final[dict[str, int]] = {
    "INVALID_PARAMETER": 400,
    "NOT_FOUND": 404,
    "REFERENTIAL_INTEGRITY_ERROR": 422,
    "RATE_LIMIT_EXCEEDED": 429,
    "INTERNAL_ERROR": 500,
}

#: Seção 5.1: "page_size máximo sugerido: 100".
PAGE_SIZE_PADRAO: Final = 20
PAGE_SIZE_MAXIMO: Final = 100

#: Seção 4: tipos aceitos pela busca global, na ordem em que a Especificação
#: os lista.
TIPOS_BUSCA: Final[tuple[str, ...]] = (
    "ingrediente", "receita", "tecnica", "povo", "territorio", "bioma", "patrimonio",
)
