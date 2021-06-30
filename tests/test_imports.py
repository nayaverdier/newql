def test_module_import():
    import newql

    assert newql.__all__ == [
        "ExecutionContext",
        "Field",
        "NewQLError",
        "ParsedOperation",
        "ParsedEnum",
        "ParsedField",
        "ParsedVariable",
        "QueryError",
        "Schema",
        "VERSION",
        "field",
        "parse_document",
        "parse_query",
    ]
    for attr in newql.__all__:
        assert getattr(newql, attr)


def test_direct_import():
    from newql import (  # noqa: F401
        VERSION,
        ExecutionContext,
        Field,
        NewQLError,
        ParsedEnum,
        ParsedField,
        ParsedOperation,
        ParsedVariable,
        QueryError,
        Schema,
        field,
        parse_document,
        parse_query,
    )


def test_submodule_import():
    from newql import errors, parse, schema  # noqa: F401
