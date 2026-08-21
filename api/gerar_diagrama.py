"""
Roots of Brazil — gerador do diagrama da API (Ordem 4).

Emite `docs/diagrama_api.png`. O diagrama mostra o que o texto do relatório
explica em parágrafos: por onde a requisição passa e, principalmente, **qual
dos dois bancos responde a quê** — a decisão de arquitetura central da Ordem 4.

As contagens de endpoints vêm de `app/models/catalogo.py`, não de constantes
escritas aqui: se um endpoint de navegação for acrescentado, o diagrama passa a
mostrar o número novo na próxima geração.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.models.catalogo import RECURSOS  # noqa: E402

SAIDA = RAIZ / "docs" / "diagrama_api.png"

VERDE_ESCURO = "#1b4332"
VERDE = "#2d6a4f"
VERDE_CLARO = "#95d5b2"
AREIA = "#e9edc9"
TERRACOTA = "#bc6c25"
CINZA = "#495057"
FUNDO = "#fbfbf9"


#: Altura de uma linha de texto e do bloco do título, em unidades do eixo.
#: A altura da caixa é DERIVADA do conteúdo em vez de fixada à mão — foi o que
#: fazia o texto transbordar na primeira versão do diagrama.
LINHA = 0.34
TITULO = 0.62
MARGEM = 0.24


def altura_de(linhas) -> float:
    return TITULO + len(linhas) * LINHA + MARGEM


def caixa(ax, x, y, largura, titulo, linhas, cor, cor_texto="white", tamanho=9):
    """Desenha uma caixa cuja altura acomoda exatamente o conteúdo.

    `y` é a borda INFERIOR. Devolve a altura usada, para o chamador empilhar a
    próxima caixa sem sobreposição.
    """
    altura = altura_de(linhas)
    ax.add_patch(mpatches.FancyBboxPatch(
        (x, y), largura, altura, boxstyle="round,pad=0.10,rounding_size=0.16",
        linewidth=0, facecolor=cor, zorder=2))
    topo = y + altura - MARGEM / 2
    ax.text(x + largura / 2, topo, titulo, ha="center", va="top",
            fontsize=tamanho + 1.5, fontweight="bold", color=cor_texto, zorder=3)
    for i, linha in enumerate(linhas):
        ax.text(x + largura / 2, topo - TITULO - i * LINHA, linha, ha="center", va="top",
                fontsize=tamanho - 0.5, color=cor_texto, zorder=3)
    return altura


def seta(ax, x1, y1, x2, y2, rotulo="", cor=CINZA, estilo="-|>"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=estilo, color=cor, linewidth=1.7,
                                shrinkA=2, shrinkB=2), zorder=1)
    if rotulo:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.18, rotulo, ha="center", va="bottom",
                fontsize=8, color=cor, style="italic",
                bbox=dict(boxstyle="round,pad=0.2", facecolor=FUNDO, edgecolor="none"))


def main() -> int:
    n_listagem = len(RECURSOS)
    n_detalhe = len(RECURSOS)
    n_navegacao = sum(len(r.navegacoes) for r in RECURSOS)
    total = n_listagem + n_detalhe + n_navegacao + 2  # + /v1/relacoes + /v1/busca

    fig, ax = plt.subplots(figsize=(13.5, 13.0))
    fig.patch.set_facecolor(FUNDO)
    ax.set_facecolor(FUNDO)
    ax.set_xlim(0, 13.5)
    # O ylim é ajustado no fim, depois de a pilha ser montada — fixá-lo aqui
    # recortava as caixas de cima. Patches são clipados pelo eixo; texto não,
    # e era por isso que o título do "Cliente" aparecia solto sobre o fundo.
    ax.axis("off")

    # A pilha é montada de BAIXO para cima, cada caixa devolvendo a altura que
    # ocupou. Assim nenhuma posição é um número mágico que precise ser
    # reajustado à mão quando o texto de uma caixa muda.

    # --- Fonte comum (base) ---
    y_fonte = 0.35
    h_fonte = caixa(
        ax, 3.3, y_fonte, 6.9,
        "Corpus Fundador v1.1  →  Dicionário de Dados v1.2",
        ["mesma fonte para os dois bancos",
         "toda propriedade 1:1 com uma coluna documentada"],
        VERDE_ESCURO, tamanho=8.5,
    )

    # --- Os dois bancos ---
    y_bancos = y_fonte + h_fonte + 0.75
    linhas_rel = ["SQLite em dev · PostgreSQL na Ordem 6", "",
                  f"{n_listagem} listagens    /v1/{{recurso}}",
                  f"{n_detalhe} detalhes     /v1/{{recurso}}/{{id}}", "",
                  "filtro · ordenação · paginação"]
    linhas_grafo = ["Neo4j AuraDB 5.27 enterprise", "",
                    f"{n_navegacao} navegações   /v1/{{recurso}}/{{id}}/{{rel}}",
                    "1 relações     /v1/relacoes",
                    "1 busca        /v1/busca (full-text)", "",
                    "peso e proveniência na aresta"]
    altura_bancos = max(altura_de(linhas_rel), altura_de(linhas_grafo))
    caixa(ax, 0.40, y_bancos, 5.10, "Banco Relacional  (Ordem 2)",
          linhas_rel, AREIA, cor_texto=VERDE_ESCURO)
    caixa(ax, 8.00, y_bancos, 5.10, "Banco de Grafo  (Ordem 3)",
          linhas_grafo, VERDE_CLARO, cor_texto=VERDE_ESCURO)
    topo_bancos = y_bancos + altura_bancos

    # --- Camada de rotas ---
    y_rotas = topo_bancos + 1.05
    h_rotas = caixa(
        ax, 2.2, y_rotas, 9.1,
        "FastAPI — routers derivados de app/models/catalogo.py",
        ["parâmetros validados nas Seções 5.1 e 5.2 · erros no formato da Seção 5.3",
         "o contrato servido é api/openapi.yaml, não um gerado do código"],
        VERDE,
    )

    # --- Middlewares ---
    y_middle = y_rotas + h_rotas + 0.62
    h_middle = caixa(
        ax, 2.2, y_middle, 9.1, "Middlewares  (de fora para dentro)",
        ["CORS aberto  →  100 req/min por IP (429)  →  gzip  →  ETag / 304",
         "decisão do fundador para a Seção 6 · sem chave de API"],
        VERDE,
    )

    # --- Cliente ---
    y_cliente = y_middle + h_middle + 0.62
    h_cliente = caixa(ax, 4.9, y_cliente, 3.7, "Cliente",
                      ["aplicativo · navegador · Postman"], VERDE_ESCURO)

    # --- Títulos, acima de tudo ---
    ax.text(6.75, y_cliente + h_cliente + 0.85,
            "Roots of Brazil — Arquitetura da API v1.1",
            ha="center", fontsize=16, fontweight="bold", color=VERDE_ESCURO)
    ax.text(6.75, y_cliente + h_cliente + 0.42,
            f"Ordem 4 · {total} endpoints somente leitura · 381 entidades · 1.585 relações",
            ha="center", fontsize=9.5, color=CINZA)

    # --- Setas verticais ---
    seta(ax, 6.75, y_cliente, 6.75, y_middle + h_middle)
    seta(ax, 6.75, y_middle, 6.75, y_rotas + h_rotas)

    # --- Bifurcação para os dois bancos ---
    ax.text(6.75, y_rotas - 0.30, "a requisição é resolvida por um dos dois bancos",
            ha="center", va="top", fontsize=8.5, color=CINZA, style="italic")
    seta(ax, 4.6, y_rotas, 2.95, topo_bancos, "listagem · detalhe", TERRACOTA)
    seta(ax, 8.9, y_rotas, 10.55, topo_bancos, "travessia · busca", TERRACOTA)

    # --- Hidratação, no vão entre os bancos ---
    y_hidra = y_bancos + altura_bancos / 2
    seta(ax, 8.00, y_hidra, 5.50, y_hidra, "", CINZA, estilo="<|-")
    ax.text(6.75, y_hidra + 0.26, "hidratação", ha="center", fontsize=8.5,
            color=CINZA, style="italic")
    ax.text(6.75, y_hidra - 0.22,
            "o grafo devolve\nIDs e arestas;\nos campos vêm\ndo relacional",
            ha="center", va="top", fontsize=7, color=CINZA, linespacing=1.45)

    # --- Dos bancos para a fonte comum ---
    seta(ax, 2.95, y_bancos, 4.6, y_fonte + h_fonte, "", CINZA, estilo="<|-")
    seta(ax, 10.55, y_bancos, 8.9, y_fonte + h_fonte, "", CINZA, estilo="<|-")

    ax.set_ylim(0, y_cliente + h_cliente + 1.25)

    fig.savefig(SAIDA, dpi=170, bbox_inches="tight", facecolor=FUNDO)
    plt.close(fig)
    print(f"{SAIDA.relative_to(RAIZ)}: {SAIDA.stat().st_size // 1024} KB "
          f"({total} endpoints representados).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
