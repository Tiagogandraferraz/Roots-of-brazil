```sql
-- Roots of Brazil — DDL PostgreSQL (Ordem 2)
-- Implementa literalmente o Dicionário de Dados Oficial v1.2, Seções 12-25.
-- Baseline esperado após ETL: 381 objetos (130/136/38/17/18/35/7 + 0 LivroFonte), 1.585 relações, 18 órfãos, 0 duplicidades.

-- ==========================================================
-- 25.4 — Tipos ENUM
-- ==========================================================

CREATE TYPE confiabilidade_enum AS ENUM (
  'confirmado_varias_fontes', 'confirmado_uma_fonte', 'inferido', 'pendente_validacao'
);

CREATE TYPE tipo_relacao_enum AS ENUM (
  'USA_INGREDIENTE','ASSOCIADO_A_POVO','CULTIVADO_EM','UTILIZA_TECNICA',
  'PREPARADO_COM','OCORRE_EM','ORIGINARIO_DE','PATRIMONIO_DE',
  'LOCALIZADO_EM_BIOMA','DERIVA_DE','VARIANTE_REGIONAL','SIMILAR_A'
);

CREATE TYPE tipo_documento_livro_enum AS ENUM (
  'Livro', 'Apostila', 'Material de curso', 'Ficha tecnica compilada', 'Outro'
);

-- ==========================================================
-- Blocos transversais (repetidos em cada tabela — Dicionário v1.2, Seções 2-9)
-- uuid, slug, created_at, updated_at, version, confiabilidade,
-- nome_pt..nome_zh, descricao_pt/en/es, macrogrupo/grupo/ordem/familia/classe/categoria/subcategoria
-- ==========================================================

-- 25.1 — Primary Keys / 8 tabelas de entidade

CREATE TABLE ingrediente (
  id                VARCHAR(10)  PRIMARY KEY CHECK (id ~ '^ING-\d{6}$'),
  uuid              UUID         UNIQUE NOT NULL,
  slug              VARCHAR(80)  UNIQUE NOT NULL CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  nome_principal    VARCHAR(200) NOT NULL,
  nomes_regionais   TEXT,                          -- lista separada por ';'
  categoria         VARCHAR(100) NOT NULL,
  subcategoria      VARCHAR(100) NOT NULL,
  classe            VARCHAR(50)  NOT NULL,          -- Vegetal | Animal | Processado/Outro
  familia           VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  ordem_taxonomica  VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  grupo             VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  macrogrupo        VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  origem            TEXT,
  estado_regiao     VARCHAR(200),
  bioma_texto       TEXT,                           -- campo texto livre legado (v1.1); LOCALIZADO_EM_BIOMA é a relação estruturada
  n_livros_fonte    INTEGER NOT NULL DEFAULT 0,
  n_citacoes        INTEGER NOT NULL DEFAULT 0,
  origem_registro   TEXT NOT NULL,
  confiabilidade    confiabilidade_enum NOT NULL,
  nome_pt VARCHAR(200) NOT NULL, nome_en VARCHAR(200), nome_es VARCHAR(200), nome_fr VARCHAR(200),
  nome_it VARCHAR(200), nome_de VARCHAR(200), nome_ja VARCHAR(200), nome_zh VARCHAR(200),
  descricao_pt TEXT DEFAULT 'não informado', descricao_en TEXT, descricao_es TEXT,
  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
  version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1)
);

CREATE TABLE receita (
  id                VARCHAR(10)  PRIMARY KEY CHECK (id ~ '^REC-\d{6}$'),
  uuid              UUID         UNIQUE NOT NULL,
  slug              VARCHAR(80)  UNIQUE NOT NULL CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  nome              VARCHAR(200) NOT NULL,
  categoria         VARCHAR(100) NOT NULL,
  subcategoria      VARCHAR(100) NOT NULL,          -- herdado de Categoria na v1.1
  classe            VARCHAR(50)  NOT NULL DEFAULT 'Preparação Culinária',
  familia VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  ordem_taxonomica VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  grupo VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  macrogrupo VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  estado            VARCHAR(100) NOT NULL,
  regiao            VARCHAR(100) NOT NULL,
  influencia_cultural TEXT,                          -- lista separada por ';'
  n_versoes_catalogadas INTEGER NOT NULL DEFAULT 1,
  livros_fonte      TEXT NOT NULL,                   -- lista separada por ';', texto livre legado
  confiabilidade    confiabilidade_enum NOT NULL,
  nome_pt VARCHAR(200) NOT NULL, nome_en VARCHAR(200), nome_es VARCHAR(200), nome_fr VARCHAR(200),
  nome_it VARCHAR(200), nome_de VARCHAR(200), nome_ja VARCHAR(200), nome_zh VARCHAR(200),
  descricao_pt TEXT DEFAULT 'não informado', descricao_en TEXT, descricao_es TEXT,
  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
  version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1)
);

CREATE TABLE tecnica (
  id                VARCHAR(10)  PRIMARY KEY CHECK (id ~ '^TEC-\d{6}$'),
  uuid              UUID         UNIQUE NOT NULL,
  slug              VARCHAR(80)  UNIQUE NOT NULL CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  nome              VARCHAR(200) NOT NULL,
  descricao         TEXT NOT NULL,                   -- espelhada em descricao_pt
  origem_cultural   TEXT,
  livros_fonte      TEXT NOT NULL,
  categoria         VARCHAR(100) NOT NULL DEFAULT 'Processo/Método de preparo',
  subcategoria      VARCHAR(100) NOT NULL DEFAULT 'Processo/Método de preparo',
  classe            VARCHAR(50)  NOT NULL DEFAULT 'Processo Culinário',
  familia VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  ordem_taxonomica VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  grupo VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  macrogrupo VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  confiabilidade    confiabilidade_enum NOT NULL,
  nome_pt VARCHAR(200) NOT NULL, nome_en VARCHAR(200), nome_es VARCHAR(200), nome_fr VARCHAR(200),
  nome_it VARCHAR(200), nome_de VARCHAR(200), nome_ja VARCHAR(200), nome_zh VARCHAR(200),
  descricao_pt TEXT NOT NULL, descricao_en TEXT, descricao_es TEXT,
  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
  version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1)
);

CREATE TABLE povo (
  id                VARCHAR(10)  PRIMARY KEY CHECK (id ~ '^POV-\d{6}$'),
  uuid              UUID         UNIQUE NOT NULL,
  slug              VARCHAR(80)  UNIQUE NOT NULL CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  nome_povo         VARCHAR(200) NOT NULL,           -- espelhado em nome_pt
  regiao            TEXT,                            -- lista separada por ';'
  livros_fonte      TEXT NOT NULL,
  categoria         VARCHAR(100) NOT NULL DEFAULT 'Grupo Sociocultural',
  subcategoria      VARCHAR(100) NOT NULL DEFAULT 'Grupo Sociocultural',
  classe            VARCHAR(50)  NOT NULL DEFAULT 'Povo/Etnia Formadora',
  familia VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  ordem_taxonomica VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  grupo VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  macrogrupo VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  confiabilidade    confiabilidade_enum NOT NULL,
  nome_pt VARCHAR(200) NOT NULL, nome_en VARCHAR(200), nome_es VARCHAR(200), nome_fr VARCHAR(200),
  nome_it VARCHAR(200), nome_de VARCHAR(200), nome_ja VARCHAR(200), nome_zh VARCHAR(200),
  descricao_pt TEXT DEFAULT 'não informado', descricao_en TEXT, descricao_es TEXT,
  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
  version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1)
);

CREATE TABLE territorio (
  id                VARCHAR(10)  PRIMARY KEY CHECK (id ~ '^TER-\d{6}$'),
  uuid              UUID         UNIQUE NOT NULL,
  slug              VARCHAR(80)  UNIQUE NOT NULL CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  estado            VARCHAR(100) NOT NULL,           -- espelhado em nome_pt
  bioma_texto       TEXT,
  livros_fonte      TEXT NOT NULL,
  categoria         VARCHAR(100) NOT NULL DEFAULT 'Unidade Federativa',
  subcategoria      VARCHAR(100) NOT NULL DEFAULT 'Estado',
  classe            VARCHAR(50)  NOT NULL DEFAULT 'Unidade Geopolítica',
  familia VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  ordem_taxonomica VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  grupo VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  macrogrupo VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  latitude          NUMERIC(9,6),
  longitude         NUMERIC(9,6),
  bounding_box      JSONB,
  geometry          JSONB,
  confiabilidade    confiabilidade_enum NOT NULL,
  nome_pt VARCHAR(200) NOT NULL, nome_en VARCHAR(200), nome_es VARCHAR(200), nome_fr VARCHAR(200),
  nome_it VARCHAR(200), nome_de VARCHAR(200), nome_ja VARCHAR(200), nome_zh VARCHAR(200),
  descricao_pt TEXT DEFAULT 'não informado', descricao_en TEXT, descricao_es TEXT,
  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
  version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1)
);

CREATE TABLE patrimonio (
  id                VARCHAR(10)  PRIMARY KEY CHECK (id ~ '^PAT-\d{6}$'),
  uuid              UUID         UNIQUE NOT NULL,
  slug              VARCHAR(80)  UNIQUE NOT NULL CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  categoria         VARCHAR(100) NOT NULL,
  elemento          VARCHAR(200) NOT NULL,           -- espelhado em nome_pt
  descricao         TEXT NOT NULL,                   -- espelhada em descricao_pt
  povo_regiao_relacionada TEXT,
  livros_fonte      TEXT NOT NULL,
  subcategoria      VARCHAR(100) NOT NULL,           -- herdado de Categoria
  classe            VARCHAR(50)  NOT NULL DEFAULT 'Patrimônio Cultural Imaterial',
  familia VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  ordem_taxonomica VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  grupo VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  macrogrupo VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  confiabilidade    confiabilidade_enum NOT NULL,
  nome_pt VARCHAR(200) NOT NULL, nome_en VARCHAR(200), nome_es VARCHAR(200), nome_fr VARCHAR(200),
  nome_it VARCHAR(200), nome_de VARCHAR(200), nome_ja VARCHAR(200), nome_zh VARCHAR(200),
  descricao_pt TEXT NOT NULL, descricao_en TEXT, descricao_es TEXT,
  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
  version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1)
);

CREATE TABLE bioma (
  id                VARCHAR(10)  PRIMARY KEY CHECK (id ~ '^BIO-\d{6}$'),
  uuid              UUID         UNIQUE NOT NULL,
  slug              VARCHAR(80)  UNIQUE NOT NULL CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  nome              VARCHAR(200) NOT NULL,           -- espelhado em nome_pt; enum fechado de 7 valores na origem
  descricao         TEXT NOT NULL,                   -- espelhada em descricao_pt
  oficial_ibge      BOOLEAN NOT NULL DEFAULT TRUE,    -- FALSE apenas para BIO-000007 (Zona Costeira/Litoral)
  territorios_associados_n INTEGER NOT NULL DEFAULT 0,
  ingredientes_associados_n INTEGER NOT NULL DEFAULT 0,
  fonte             TEXT NOT NULL,
  latitude          NUMERIC(9,6),
  longitude         NUMERIC(9,6),
  bounding_box      JSONB,
  geometry          JSONB,
  categoria         VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  subcategoria      VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  classe            VARCHAR(50)  NOT NULL DEFAULT 'não classificado',
  familia VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  ordem_taxonomica VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  grupo VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  macrogrupo VARCHAR(100) NOT NULL DEFAULT 'não classificado',
  confiabilidade    confiabilidade_enum,
  nome_pt VARCHAR(200) NOT NULL, nome_en VARCHAR(200), nome_es VARCHAR(200), nome_fr VARCHAR(200),
  nome_it VARCHAR(200), nome_de VARCHAR(200), nome_ja VARCHAR(200), nome_zh VARCHAR(200),
  descricao_pt TEXT NOT NULL, descricao_en TEXT, descricao_es TEXT,
  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
  version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1)
);

CREATE TABLE livro_fonte (
  id                VARCHAR(10)  PRIMARY KEY CHECK (id ~ '^LIV-\d{6}$'),
  uuid              UUID         UNIQUE NOT NULL,
  slug              VARCHAR(80)  UNIQUE NOT NULL CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  titulo            VARCHAR(300) NOT NULL,
  autor             VARCHAR(200) NOT NULL DEFAULT 'não informado',
  ano               INTEGER,
  isbn              VARCHAR(20),
  editora           VARCHAR(200),
  tipo_documento    tipo_documento_livro_enum NOT NULL,
  idioma            VARCHAR(5)   NOT NULL DEFAULT 'pt',   -- ISO 639-1
  url               TEXT,
  licenca           VARCHAR(200),
  observacoes       TEXT,
  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
  version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1)
);
-- 0 registros nesta carga (Ordem 2) — esquema definido, população pendente (Dicionário v1.2, Seção 19, Tabela "Registros nesta versão: 0").

-- ==========================================================
-- 25.2 — Tabela de arestas RELACOES
-- ==========================================================

CREATE TABLE relacoes (
  rel_id              VARCHAR(12) PRIMARY KEY CHECK (rel_id ~ '^REL-(\d{6}|B\d{5})$'),
  origem_id           VARCHAR(10) NOT NULL,
  destino_id          VARCHAR(10) NOT NULL,
  tipo_relacao        tipo_relacao_enum NOT NULL,
  fonte               TEXT,
  pagina              TEXT,
  confiabilidade      confiabilidade_enum,
  observacoes         TEXT NOT NULL,
  data_criacao        DATE NOT NULL,
  peso                NUMERIC(3,2) NOT NULL CHECK (peso BETWEEN 0.0 AND 1.0),
  metodo_calculo_peso TEXT NOT NULL
  -- origem_id/destino_id não podem ser FK única (apontam para 8 tabelas conforme prefixo) — ver objeto_universal abaixo (25.3)
);

-- ==========================================================
-- 25.3 — FK polimórfica: abordagem escolhida = VIEW DE UNIÃO
-- (recomendada pelo Dicionário v1.2 para PostgreSQL — ver relatório da Ordem 2 para justificativa)
-- ==========================================================

CREATE VIEW objeto_universal AS
  SELECT id, 'Ingrediente' AS tipo, uuid FROM ingrediente
  UNION ALL SELECT id, 'Receita', uuid FROM receita
  UNION ALL SELECT id, 'Tecnica', uuid FROM tecnica
  UNION ALL SELECT id, 'Povo', uuid FROM povo
  UNION ALL SELECT id, 'Territorio', uuid FROM territorio
  UNION ALL SELECT id, 'Patrimonio', uuid FROM patrimonio
  UNION ALL SELECT id, 'Bioma', uuid FROM bioma
  UNION ALL SELECT id, 'LivroFonte', uuid FROM livro_fonte;

-- Trigger de validação de existência (compensa a ausência de FK física — Seção 25.3, segunda abordagem,
-- combinada aqui com a view para validação ativa na escrita, não só consulta):
CREATE OR REPLACE FUNCTION validar_fk_polimorfica() RETURNS TRIGGER AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM objeto_universal WHERE id = NEW.origem_id) THEN
    RAISE EXCEPTION 'origem_id % não existe em nenhuma tabela de entidade', NEW.origem_id;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM objeto_universal WHERE id = NEW.destino_id) THEN
    RAISE EXCEPTION 'destino_id % não existe em nenhuma tabela de entidade', NEW.destino_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_fk_relacoes
  BEFORE INSERT OR UPDATE ON relacoes
  FOR EACH ROW EXECUTE FUNCTION validar_fk_polimorfica();

-- 23.1 — ON DELETE RESTRICT: como não há FK física (chave polimórfica), a proteção contra
-- exclusão física é aplicada via ausência de comando DELETE na Política de Identificadores
-- (objetos são "aposentados", nunca excluídos — Seção 3) — documentado, não uma constraint de banco.

-- ==========================================================
-- Seção 24 — Índices Recomendados
-- ==========================================================

CREATE UNIQUE INDEX idx_ingrediente_id ON ingrediente(id);
CREATE UNIQUE INDEX idx_ingrediente_uuid ON ingrediente(uuid);
CREATE UNIQUE INDEX idx_ingrediente_slug ON ingrediente(slug);
CREATE INDEX idx_ingrediente_categoria_classe ON ingrediente(categoria, classe);
CREATE INDEX idx_ingrediente_nome_pt_trgm ON ingrediente USING GIN (nome_pt gin_trgm_ops);

-- (índices análogos replicados por tabela de entidade — id/uuid/slug únicos, categoria/classe, nome_pt trigram)
CREATE UNIQUE INDEX idx_receita_id ON receita(id);
CREATE UNIQUE INDEX idx_receita_uuid ON receita(uuid);
CREATE UNIQUE INDEX idx_receita_slug ON receita(slug);
CREATE INDEX idx_receita_categoria_classe ON receita(categoria, classe);
CREATE INDEX idx_receita_nome_pt_trgm ON receita USING GIN (nome_pt gin_trgm_ops);

CREATE UNIQUE INDEX idx_tecnica_id ON tecnica(id);
CREATE UNIQUE INDEX idx_tecnica_uuid ON tecnica(uuid);
CREATE UNIQUE INDEX idx_tecnica_slug ON tecnica(slug);

CREATE UNIQUE INDEX idx_povo_id ON povo(id);
CREATE UNIQUE INDEX idx_povo_uuid ON povo(uuid);
CREATE UNIQUE INDEX idx_povo_slug ON povo(slug);

CREATE UNIQUE INDEX idx_territorio_id ON territorio(id);
CREATE UNIQUE INDEX idx_territorio_uuid ON territorio(uuid);
CREATE UNIQUE INDEX idx_territorio_slug ON territorio(slug);

CREATE UNIQUE INDEX idx_patrimonio_id ON patrimonio(id);
CREATE UNIQUE INDEX idx_patrimonio_uuid ON patrimonio(uuid);
CREATE UNIQUE INDEX idx_patrimonio_slug ON patrimonio(slug);

CREATE UNIQUE INDEX idx_bioma_id ON bioma(id);
CREATE UNIQUE INDEX idx_bioma_uuid ON bioma(uuid);
CREATE UNIQUE INDEX idx_bioma_slug ON bioma(slug);

CREATE UNIQUE INDEX idx_livro_fonte_id ON livro_fonte(id);
CREATE UNIQUE INDEX idx_livro_fonte_uuid ON livro_fonte(uuid);
CREATE UNIQUE INDEX idx_livro_fonte_slug ON livro_fonte(slug);

CREATE INDEX idx_relacoes_tipo_relacao ON relacoes(tipo_relacao);
CREATE INDEX idx_relacoes_origem_id ON relacoes(origem_id);
CREATE INDEX idx_relacoes_destino_id ON relacoes(destino_id);
CREATE INDEX idx_relacoes_confiabilidade ON relacoes(confiabilidade);
CREATE INDEX idx_relacoes_origem_tipo ON relacoes(origem_id, tipo_relacao);  -- índice composto — padrão de consulta mais comum

-- Extensão necessária para índices trigram (busca textual, endpoint /v1/busca)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ==========================================================
-- 25.5 — Materialized Views
-- ==========================================================

CREATE MATERIALIZED VIEW mv_estatisticas_corpus AS
SELECT
  (SELECT COUNT(*) FROM ingrediente) AS total_ingredientes,
  (SELECT COUNT(*) FROM receita) AS total_receitas,
  (SELECT COUNT(*) FROM tecnica) AS total_tecnicas,
  (SELECT COUNT(*) FROM povo) AS total_povos,
  (SELECT COUNT(*) FROM territorio) AS total_territorios,
  (SELECT COUNT(*) FROM patrimonio) AS total_patrimonio,
  (SELECT COUNT(*) FROM bioma) AS total_biomas,
  (SELECT COUNT(*) FROM livro_fonte) AS total_livros_fonte,
  (SELECT COUNT(*) FROM relacoes) AS total_relacoes,
  (SELECT COUNT(*) FROM ingrediente WHERE confiabilidade = 'confirmado_varias_fontes') AS ingredientes_confirmado_varias_fontes,
  (SELECT COUNT(*) FROM ingrediente WHERE confiabilidade = 'confirmado_uma_fonte') AS ingredientes_confirmado_uma_fonte,
  (SELECT COUNT(*) FROM ingrediente WHERE confiabilidade = 'inferido') AS ingredientes_inferido,
  (SELECT COUNT(*) FROM ingrediente WHERE confiabilidade = 'pendente_validacao') AS ingredientes_pendente_validacao;

CREATE MATERIALIZED VIEW mv_grafo_agregado AS
SELECT
  tipo_relacao,
  LEFT(origem_id, 3) AS prefixo_origem,
  LEFT(destino_id, 3) AS prefixo_destino,
  COUNT(*) AS n_relacoes
FROM relacoes
GROUP BY tipo_relacao, LEFT(origem_id, 3), LEFT(destino_id, 3)
ORDER BY n_relacoes DESC;

-- REFRESH MATERIALIZED VIEW mv_estatisticas_corpus; -- executar após cada lote de escrita (Seção 25.5)
-- REFRESH MATERIALIZED VIEW mv_grafo_agregado;
```
