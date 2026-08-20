-- Roots of Brazil — DDL SQLite (variante dev/local da Ordem 2)
-- Derivado literalmente do Dicionário de Dados Oficial v1.2, Seções 12-25.
-- SQLite não tem CREATE TYPE ENUM nativo -> enums implementados via CHECK.

PRAGMA foreign_keys = ON;

-- Blocos transversais (Seções 2-9) repetidos em cada tabela, pois SQLite não tem herança de tabela.

CREATE TABLE ingrediente (
    id                  TEXT PRIMARY KEY CHECK (id GLOB 'ING-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    uuid                TEXT NOT NULL UNIQUE,
    slug                TEXT NOT NULL UNIQUE,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    version             INTEGER NOT NULL CHECK (version >= 1),
    nome_principal       TEXT NOT NULL,
    nomes_regionais      TEXT,
    categoria            TEXT NOT NULL,
    subcategoria         TEXT NOT NULL,
    classe               TEXT NOT NULL CHECK (classe IN ('Vegetal','Animal','Processado/Outro')),
    familia               TEXT NOT NULL DEFAULT 'não classificado',
    ordem_taxonomica      TEXT NOT NULL DEFAULT 'não classificado',
    grupo                 TEXT NOT NULL DEFAULT 'não classificado',
    macrogrupo             TEXT NOT NULL DEFAULT 'não classificado',
    origem_texto          TEXT,
    estado_regiao          TEXT,
    bioma_texto            TEXT,
    confiabilidade          TEXT NOT NULL CHECK (confiabilidade GLOB '🟢*' OR confiabilidade GLOB '🟡*' OR confiabilidade GLOB '🔵*' OR confiabilidade GLOB '🔴*'),
    n_livros_fonte          INTEGER,
    n_citacoes              INTEGER,
    origem_registro         TEXT,
    liv_id                  TEXT,
    nome_pt TEXT NOT NULL, nome_en TEXT, nome_es TEXT, nome_fr TEXT, nome_it TEXT, nome_de TEXT, nome_ja TEXT, nome_zh TEXT,
    descricao_pt TEXT, descricao_en TEXT, descricao_es TEXT
);

CREATE TABLE receita (
    id TEXT PRIMARY KEY CHECK (id GLOB 'REC-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    uuid TEXT NOT NULL UNIQUE, slug TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, version INTEGER NOT NULL CHECK (version >= 1),
    nome TEXT NOT NULL,
    categoria TEXT NOT NULL, subcategoria TEXT NOT NULL, classe TEXT NOT NULL DEFAULT 'Preparação Culinária',
    familia TEXT NOT NULL DEFAULT 'não classificado', ordem_taxonomica TEXT NOT NULL DEFAULT 'não classificado',
    grupo TEXT NOT NULL DEFAULT 'não classificado', macrogrupo TEXT NOT NULL DEFAULT 'não classificado',
    estado TEXT NOT NULL, regiao TEXT NOT NULL, influencia_cultural TEXT,
    n_versoes_catalogadas INTEGER,
    livros_fonte TEXT NOT NULL, liv_id TEXT,
    confiabilidade TEXT NOT NULL CHECK (confiabilidade GLOB '🟢*' OR confiabilidade GLOB '🟡*' OR confiabilidade GLOB '🔵*' OR confiabilidade GLOB '🔴*'),
    nome_pt TEXT NOT NULL, nome_en TEXT, nome_es TEXT, nome_fr TEXT, nome_it TEXT, nome_de TEXT, nome_ja TEXT, nome_zh TEXT,
    descricao_pt TEXT, descricao_en TEXT, descricao_es TEXT
);

CREATE TABLE tecnica (
    id TEXT PRIMARY KEY CHECK (id GLOB 'TEC-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    uuid TEXT NOT NULL UNIQUE, slug TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, version INTEGER NOT NULL CHECK (version >= 1),
    nome TEXT NOT NULL, descricao TEXT NOT NULL,
    ingredientes_utilizados TEXT, receitas TEXT, origem_cultural TEXT,
    livros_fonte TEXT NOT NULL, liv_id TEXT,
    confiabilidade TEXT NOT NULL CHECK (confiabilidade GLOB '🟢*' OR confiabilidade GLOB '🟡*' OR confiabilidade GLOB '🔵*' OR confiabilidade GLOB '🔴*'),
    categoria TEXT NOT NULL, subcategoria TEXT NOT NULL, classe TEXT NOT NULL DEFAULT 'Processo Culinário',
    familia TEXT NOT NULL DEFAULT 'não classificado', ordem_taxonomica TEXT NOT NULL DEFAULT 'não classificado',
    grupo TEXT NOT NULL DEFAULT 'não classificado', macrogrupo TEXT NOT NULL DEFAULT 'não classificado',
    nome_pt TEXT NOT NULL, nome_en TEXT, nome_es TEXT, nome_fr TEXT, nome_it TEXT, nome_de TEXT, nome_ja TEXT, nome_zh TEXT,
    descricao_pt TEXT NOT NULL, descricao_en TEXT, descricao_es TEXT
);

CREATE TABLE povo (
    id TEXT PRIMARY KEY CHECK (id GLOB 'POV-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    uuid TEXT NOT NULL UNIQUE, slug TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, version INTEGER NOT NULL CHECK (version >= 1),
    povo TEXT NOT NULL, regiao TEXT,
    ingredientes_associados TEXT, receitas TEXT, praticas_culinarias TEXT,
    livros_fonte TEXT NOT NULL, liv_id TEXT,
    confiabilidade TEXT NOT NULL CHECK (confiabilidade GLOB '🟢*' OR confiabilidade GLOB '🟡*' OR confiabilidade GLOB '🔵*' OR confiabilidade GLOB '🔴*'),
    categoria TEXT NOT NULL, subcategoria TEXT NOT NULL, classe TEXT NOT NULL DEFAULT 'Povo/Etnia Formadora',
    familia TEXT NOT NULL DEFAULT 'não classificado', ordem_taxonomica TEXT NOT NULL DEFAULT 'não classificado',
    grupo TEXT NOT NULL DEFAULT 'não classificado', macrogrupo TEXT NOT NULL DEFAULT 'não classificado',
    nome_pt TEXT NOT NULL, nome_en TEXT, nome_es TEXT, nome_fr TEXT, nome_it TEXT, nome_de TEXT, nome_ja TEXT, nome_zh TEXT,
    descricao_pt TEXT, descricao_en TEXT, descricao_es TEXT
);

CREATE TABLE territorio (
    id TEXT PRIMARY KEY CHECK (id GLOB 'TER-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    uuid TEXT NOT NULL UNIQUE, slug TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, version INTEGER NOT NULL CHECK (version >= 1),
    estado TEXT NOT NULL, bioma_texto TEXT,
    ingredientes TEXT, receitas TEXT, produtos_tradicionais TEXT,
    livros_fonte TEXT NOT NULL, liv_id TEXT,
    confiabilidade TEXT NOT NULL CHECK (confiabilidade GLOB '🟢*' OR confiabilidade GLOB '🟡*' OR confiabilidade GLOB '🔵*' OR confiabilidade GLOB '🔴*'),
    categoria TEXT NOT NULL, subcategoria TEXT NOT NULL, classe TEXT NOT NULL DEFAULT 'Unidade Geopolítica',
    familia TEXT NOT NULL DEFAULT 'não classificado', ordem_taxonomica TEXT NOT NULL DEFAULT 'não classificado',
    grupo TEXT NOT NULL DEFAULT 'não classificado', macrogrupo TEXT NOT NULL DEFAULT 'não classificado',
    latitude REAL, longitude REAL, bounding_box TEXT, geometry TEXT,
    nome_pt TEXT NOT NULL, nome_en TEXT, nome_es TEXT, nome_fr TEXT, nome_it TEXT, nome_de TEXT, nome_ja TEXT, nome_zh TEXT,
    descricao_pt TEXT, descricao_en TEXT, descricao_es TEXT
);

CREATE TABLE patrimonio (
    id TEXT PRIMARY KEY CHECK (id GLOB 'PAT-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    uuid TEXT NOT NULL UNIQUE, slug TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, version INTEGER NOT NULL CHECK (version >= 1),
    categoria TEXT NOT NULL, elemento TEXT NOT NULL, descricao TEXT NOT NULL,
    povo_regiao_relacionada TEXT,
    livros_fonte TEXT NOT NULL, liv_id TEXT,
    confiabilidade TEXT NOT NULL CHECK (confiabilidade GLOB '🟢*' OR confiabilidade GLOB '🟡*' OR confiabilidade GLOB '🔵*' OR confiabilidade GLOB '🔴*'),
    subcategoria TEXT NOT NULL, classe TEXT NOT NULL DEFAULT 'Patrimônio Cultural Imaterial',
    familia TEXT NOT NULL DEFAULT 'não classificado', ordem_taxonomica TEXT NOT NULL DEFAULT 'não classificado',
    grupo TEXT NOT NULL DEFAULT 'não classificado', macrogrupo TEXT NOT NULL DEFAULT 'não classificado',
    nome_pt TEXT NOT NULL, nome_en TEXT, nome_es TEXT, nome_fr TEXT, nome_it TEXT, nome_de TEXT, nome_ja TEXT, nome_zh TEXT,
    descricao_pt TEXT NOT NULL, descricao_en TEXT, descricao_es TEXT
);

CREATE TABLE bioma (
    id TEXT PRIMARY KEY CHECK (id GLOB 'BIO-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    uuid TEXT NOT NULL UNIQUE, slug TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, version INTEGER NOT NULL CHECK (version >= 1),
    nome TEXT NOT NULL, descricao TEXT NOT NULL,
    territorios_associados_n INTEGER, ingredientes_associados_n INTEGER,
    fonte TEXT NOT NULL, oficial_ibge INTEGER NOT NULL DEFAULT 1 CHECK (oficial_ibge IN (0,1)),
    latitude REAL, longitude REAL, bounding_box TEXT, geometry TEXT,
    nome_pt TEXT NOT NULL, nome_en TEXT, nome_es TEXT, nome_fr TEXT, nome_it TEXT, nome_de TEXT, nome_ja TEXT, nome_zh TEXT,
    descricao_pt TEXT NOT NULL, descricao_en TEXT, descricao_es TEXT
);

CREATE TABLE livro_fonte (
    id TEXT PRIMARY KEY CHECK (id GLOB 'LIV-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    uuid TEXT NOT NULL UNIQUE, slug TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, version INTEGER NOT NULL CHECK (version >= 1),
    titulo TEXT NOT NULL, autor TEXT NOT NULL, ano INTEGER, isbn TEXT, editora TEXT,
    tipo_documento TEXT NOT NULL CHECK (tipo_documento IN
        ('Livro','Apostila','Material de curso','Ficha técnica compilada','Outro')),
    idioma TEXT NOT NULL, url TEXT, licenca TEXT, observacoes TEXT
);

-- Tabela de arestas (Seção 25.3/25.4/29)
CREATE TABLE relacoes (
    rel_id          TEXT PRIMARY KEY,
    origem_id       TEXT NOT NULL,
    destino_id      TEXT NOT NULL,
    tipo_relacao    TEXT NOT NULL CHECK (tipo_relacao IN
        ('USA_INGREDIENTE','ASSOCIADO_A_POVO','CULTIVADO_EM','UTILIZA_TECNICA','PREPARADO_COM',
         'OCORRE_EM','ORIGINARIO_DE','PATRIMONIO_DE','LOCALIZADO_EM_BIOMA','DERIVA_DE',
         'VARIANTE_REGIONAL','SIMILAR_A')),
    fonte           TEXT,
    pagina          TEXT,
    confiabilidade  TEXT CHECK (confiabilidade IS NULL OR confiabilidade GLOB '🟢*' OR confiabilidade GLOB '🟡*' OR confiabilidade GLOB '🔵*' OR confiabilidade GLOB '🔴*'),
    observacoes     TEXT NOT NULL,
    data_criacao    TEXT NOT NULL,
    peso            REAL NOT NULL CHECK (peso >= 0.0 AND peso <= 1.0),
    metodo_calculo_peso TEXT NOT NULL
);

-- FK polimórfica de origem_id/destino_id (Seção 25.3): SQLite não suporta FK condicional
-- nativa contra múltiplas tabelas. Abordagem escolhida: VIEW de união "objeto_universal"
-- (não trigger) — mais simples de manter e de consultar; validação de integridade é feita
-- em Python no ETL (fail-fast) e pode ser reforçada por trigger em PostgreSQL na Ordem 6.
CREATE VIEW objeto_universal AS
    SELECT id, uuid, 'Ingrediente' AS tipo FROM ingrediente
    UNION ALL SELECT id, uuid, 'Receita' FROM receita
    UNION ALL SELECT id, uuid, 'Tecnica' FROM tecnica
    UNION ALL SELECT id, uuid, 'Povo' FROM povo
    UNION ALL SELECT id, uuid, 'Territorio' FROM territorio
    UNION ALL SELECT id, uuid, 'Patrimonio' FROM patrimonio
    UNION ALL SELECT id, uuid, 'Bioma' FROM bioma
    UNION ALL SELECT id, uuid, 'LivroFonte' FROM livro_fonte;

-- Índices (Seção 24)
CREATE INDEX idx_ingrediente_categoria ON ingrediente(categoria);
CREATE INDEX idx_ingrediente_classe ON ingrediente(classe);
CREATE INDEX idx_receita_categoria ON receita(categoria);
CREATE INDEX idx_relacoes_tipo ON relacoes(tipo_relacao);
CREATE INDEX idx_relacoes_origem ON relacoes(origem_id);
CREATE INDEX idx_relacoes_destino ON relacoes(destino_id);
CREATE INDEX idx_relacoes_origem_tipo ON relacoes(origem_id, tipo_relacao);
CREATE INDEX idx_relacoes_confiabilidade ON relacoes(confiabilidade);

-- Materialized views (Seção 25.5) — SQLite não tem MATERIALIZED VIEW nativa; implementadas
-- como VIEW normal (recalculada a cada consulta). Em PostgreSQL (produção), usar
-- CREATE MATERIALIZED VIEW de verdade com REFRESH programado.
CREATE VIEW mv_estatisticas_corpus AS
SELECT
    (SELECT COUNT(*) FROM ingrediente) AS total_ingredientes,
    (SELECT COUNT(*) FROM receita) AS total_receitas,
    (SELECT COUNT(*) FROM tecnica) AS total_tecnicas,
    (SELECT COUNT(*) FROM povo) AS total_povos,
    (SELECT COUNT(*) FROM territorio) AS total_territorios,
    (SELECT COUNT(*) FROM patrimonio) AS total_biomas,
    (SELECT COUNT(*) FROM livro_fonte) AS total_livros_fonte,
    (SELECT COUNT(*) FROM relacoes) AS total_relacoes;

CREATE VIEW mv_grafo_agregado AS
SELECT tipo_relacao, COUNT(*) AS n_instancias
FROM relacoes
GROUP BY tipo_relacao;
