// Roots of Brazil — DDL Neo4j (Ordem 3)
//
// ARQUIVO GERADO. Fonte da verdade: app/models/grafo.py (cypher_schema()).
// Para regenerar:  python -m scripts.ordem3.etl_neo4j --emitir-schema schemas/ddl_neo4j.cypher
// O teste tests/ordem3/test_modelo_grafo.py::test_ddl_neo4j_esta_sincronizado
// falha se este arquivo divergir do gerador.
//
// Derivado de schemas/ontologia.ttl (Ordem 1) e schemas/ddl_sqlite.sql (Ordem 2).
// Compatível com Neo4j 5 Community: apenas node uniqueness constraints e índices.

// --- Constraints de unicidade (PK/UNIQUE do relacional) ---

CREATE CONSTRAINT roots_objetoroots_id_unico IF NOT EXISTS
FOR (n:ObjetoRoots) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT roots_objetoroots_uuid_unico IF NOT EXISTS
FOR (n:ObjetoRoots) REQUIRE n.uuid IS UNIQUE;

CREATE CONSTRAINT roots_ingrediente_id_unico IF NOT EXISTS
FOR (n:Ingrediente) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT roots_receita_id_unico IF NOT EXISTS
FOR (n:Receita) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT roots_tecnica_id_unico IF NOT EXISTS
FOR (n:Tecnica) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT roots_povo_id_unico IF NOT EXISTS
FOR (n:Povo) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT roots_territorio_id_unico IF NOT EXISTS
FOR (n:Territorio) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT roots_patrimonio_id_unico IF NOT EXISTS
FOR (n:Patrimonio) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT roots_bioma_id_unico IF NOT EXISTS
FOR (n:Bioma) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT roots_livrofonte_id_unico IF NOT EXISTS
FOR (n:LivroFonte) REQUIRE n.id IS UNIQUE;


// --- Índices (Dicionário v1.2, Seção 24 + busca por aresta) ---

CREATE INDEX roots_objetoroots_slug_idx IF NOT EXISTS
FOR (n:ObjetoRoots) ON (n.slug);

CREATE INDEX roots_ingrediente_categoria_idx IF NOT EXISTS
FOR (n:Ingrediente) ON (n.categoria);

CREATE INDEX roots_ingrediente_classe_idx IF NOT EXISTS
FOR (n:Ingrediente) ON (n.classe);

CREATE INDEX roots_receita_categoria_idx IF NOT EXISTS
FOR (n:Receita) ON (n.categoria);

CREATE INDEX roots_rel_usa_ingrediente_rel_id_idx IF NOT EXISTS
FOR ()-[r:USA_INGREDIENTE]-() ON (r.rel_id);

CREATE INDEX roots_rel_usa_ingrediente_peso_idx IF NOT EXISTS
FOR ()-[r:USA_INGREDIENTE]-() ON (r.peso);

CREATE INDEX roots_rel_associado_a_povo_rel_id_idx IF NOT EXISTS
FOR ()-[r:ASSOCIADO_A_POVO]-() ON (r.rel_id);

CREATE INDEX roots_rel_associado_a_povo_peso_idx IF NOT EXISTS
FOR ()-[r:ASSOCIADO_A_POVO]-() ON (r.peso);

CREATE INDEX roots_rel_cultivado_em_rel_id_idx IF NOT EXISTS
FOR ()-[r:CULTIVADO_EM]-() ON (r.rel_id);

CREATE INDEX roots_rel_cultivado_em_peso_idx IF NOT EXISTS
FOR ()-[r:CULTIVADO_EM]-() ON (r.peso);

CREATE INDEX roots_rel_utiliza_tecnica_rel_id_idx IF NOT EXISTS
FOR ()-[r:UTILIZA_TECNICA]-() ON (r.rel_id);

CREATE INDEX roots_rel_utiliza_tecnica_peso_idx IF NOT EXISTS
FOR ()-[r:UTILIZA_TECNICA]-() ON (r.peso);

CREATE INDEX roots_rel_preparado_com_rel_id_idx IF NOT EXISTS
FOR ()-[r:PREPARADO_COM]-() ON (r.rel_id);

CREATE INDEX roots_rel_preparado_com_peso_idx IF NOT EXISTS
FOR ()-[r:PREPARADO_COM]-() ON (r.peso);

CREATE INDEX roots_rel_ocorre_em_rel_id_idx IF NOT EXISTS
FOR ()-[r:OCORRE_EM]-() ON (r.rel_id);

CREATE INDEX roots_rel_ocorre_em_peso_idx IF NOT EXISTS
FOR ()-[r:OCORRE_EM]-() ON (r.peso);

CREATE INDEX roots_rel_originario_de_rel_id_idx IF NOT EXISTS
FOR ()-[r:ORIGINARIO_DE]-() ON (r.rel_id);

CREATE INDEX roots_rel_originario_de_peso_idx IF NOT EXISTS
FOR ()-[r:ORIGINARIO_DE]-() ON (r.peso);

CREATE INDEX roots_rel_patrimonio_de_rel_id_idx IF NOT EXISTS
FOR ()-[r:PATRIMONIO_DE]-() ON (r.rel_id);

CREATE INDEX roots_rel_patrimonio_de_peso_idx IF NOT EXISTS
FOR ()-[r:PATRIMONIO_DE]-() ON (r.peso);

CREATE INDEX roots_rel_localizado_em_bioma_rel_id_idx IF NOT EXISTS
FOR ()-[r:LOCALIZADO_EM_BIOMA]-() ON (r.rel_id);

CREATE INDEX roots_rel_localizado_em_bioma_peso_idx IF NOT EXISTS
FOR ()-[r:LOCALIZADO_EM_BIOMA]-() ON (r.peso);

CREATE INDEX roots_rel_deriva_de_rel_id_idx IF NOT EXISTS
FOR ()-[r:DERIVA_DE]-() ON (r.rel_id);

CREATE INDEX roots_rel_deriva_de_peso_idx IF NOT EXISTS
FOR ()-[r:DERIVA_DE]-() ON (r.peso);

CREATE INDEX roots_rel_variante_regional_rel_id_idx IF NOT EXISTS
FOR ()-[r:VARIANTE_REGIONAL]-() ON (r.rel_id);

CREATE INDEX roots_rel_variante_regional_peso_idx IF NOT EXISTS
FOR ()-[r:VARIANTE_REGIONAL]-() ON (r.peso);

CREATE INDEX roots_rel_similar_a_rel_id_idx IF NOT EXISTS
FOR ()-[r:SIMILAR_A]-() ON (r.rel_id);

CREATE INDEX roots_rel_similar_a_peso_idx IF NOT EXISTS
FOR ()-[r:SIMILAR_A]-() ON (r.peso);
