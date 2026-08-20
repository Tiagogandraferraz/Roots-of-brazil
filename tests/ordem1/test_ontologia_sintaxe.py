```python
"""Teste mínimo de sintaxe da Ordem 1 — balanceamento estrutural, sem reasoner real (sem rede nesta sandbox)."""
from pathlib import Path
import json

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"


def test_ontologia_ttl_balanceado():
    s = (SCHEMAS / "ontologia.ttl").read_text(encoding="utf-8")
    assert s.count("[") == s.count("]")
    assert s.count("(") == s.count(")")


def test_shapes_ttl_balanceado():
    s = (SCHEMAS / "shapes.shacl.ttl").read_text(encoding="utf-8")
    assert s.count("[") == s.count("]")
    assert s.count("(") == s.count(")")


def test_context_jsonld_valido():
    data = json.loads((SCHEMAS / "context.jsonld").read_text(encoding="utf-8"))
    assert "@context" in data


def test_8_classes_presentes():
    s = (SCHEMAS / "ontologia.ttl").read_text(encoding="utf-8")
    for classe in ["Ingrediente", "Receita", "Tecnica", "Povo", "Territorio", "Patrimonio", "Bioma", "LivroFonte"]:
        assert f"roots:{classe} a owl:Class" in s


def test_12_tipos_relacao_presentes():
    s = (SCHEMAS / "ontologia.ttl").read_text(encoding="utf-8")
    tipos = ["USA_INGREDIENTE", "ASSOCIADO_A_POVO", "CULTIVADO_EM", "UTILIZA_TECNICA",
             "PREPARADO_COM", "OCORRE_EM", "ORIGINARIO_DE", "PATRIMONIO_DE",
             "LOCALIZADO_EM_BIOMA", "DERIVA_DE", "VARIANTE_REGIONAL", "SIMILAR_A"]
    for t in tipos:
        assert f"roots:{t} a owl:ObjectProperty" in s
```
