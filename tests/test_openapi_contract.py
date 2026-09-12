from scripts.dump_openapi import SCHEMA_PATH, render


class TestOpenApiContract:
    def test_committed_schema_matches_app(self):
        assert SCHEMA_PATH.exists(), "нет openapi.json — запустите python scripts/dump_openapi.py"
        assert SCHEMA_PATH.read_text(encoding="utf-8") == render(), (
            "openapi.json разошёлся с приложением — запустите python scripts/dump_openapi.py "
            "и закоммитьте результат"
        )
