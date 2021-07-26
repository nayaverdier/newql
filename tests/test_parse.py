import pytest
from parsimonious.exceptions import ParseError, VisitationError

from newql import parse_document, parse_query
from newql.parse import ParsedEnum, ParsedField, ParsedOperation, ParsedVariable


def doc_test(*lines, doc):
    if isinstance(doc, ParsedOperation):
        doc = {doc.name: doc}

    assert parse_document("\n".join(lines)) == doc


COMMAS = ["", ",", " , ", ",,", " ,  , ,,, ", " ,\n\n ,,"]
EXCLAMATIONS = ["", "!", " ! ", ",,!,", " , ! ,"]
VARIABLE_BRACKETS = [("", ""), ("[", "]"), ("[ ", " ]"), ("[,", ",]"), (" [ , ", " , ] ")]


@pytest.mark.parametrize(
    "doc",
    (
        "",
        "# just a single comment",
        "# first line\n# second line\n  \t\t# third line",
        "# first line\n\n\n# last line",
        "\t\t\n# comment\n# another comment    \t\t  \n\n",
        *COMMAS,
    ),
)
def test_empty_document(doc):
    with pytest.raises(ParseError) as info:
        parse_document(doc)
    error = str(info.value)
    assert error.startswith("Rule 'document' didn't match at ''") or error.startswith(
        "Rule 'operation' didn't match at ''"
    )


@pytest.mark.parametrize("comma", COMMAS)
def test_unnamed_query(comma):
    query = comma + "{" + comma + " query_field " + comma + "}" + comma
    doc_test(query, doc=ParsedOperation("query", [ParsedField("query_field")]))
    doc_test("query" + query, doc=ParsedOperation("query", fields=[ParsedField("query_field")]))


@pytest.mark.parametrize("comma", COMMAS)
def test_unnamed_mutation(comma):
    doc_test(
        "mutation" + comma + "{" + comma + " mutation_field " + comma + "}" + comma,
        doc=ParsedOperation("mutation", [ParsedField("mutation_field")]),
    )


@pytest.mark.parametrize("name", ["MyQuery", "__", "_query1", "_123"])
def test_named_query(name):
    doc_test(f"query {name} {{ query_field }}", doc=ParsedOperation("query", [ParsedField("query_field")], name=name))


@pytest.mark.parametrize("name", ["MyMutation", "__", "_mutation1", "_123"])
def test_named_mutation(name):
    doc_test(
        f"mutation {name} {{ mutation_field }}",
        doc=ParsedOperation("mutation", [ParsedField("mutation_field")], name=name),
    )


def test_multi_byte_character():
    doc_test(
        "# This comment has a \u0A0A multi-byte character.",
        '{ field(arg: "Has a \u0A0A multi-byte character.") }',
        doc=ParsedOperation(
            operation="query",
            fields=[ParsedField(name="field", alias="field", arguments={"arg": "Has a \u0A0A multi-byte character."})],
        ),
    )


def test_comments_everywhere():
    doc_test(
        "# comment on first line",
        "{ # comment after brace",
        "  # comment inside block",
        "  my_field # comment after field",
        "  , # comment after comma",
        "  # comment after field",
        "  another_field",
        "}  # comment after brace",
        "# comment on last line",
        doc=ParsedOperation("query", [ParsedField("my_field"), ParsedField("another_field")]),
    )


def test_commas_everywhere():
    doc_test(
        ", ,",
        ", ,{ ,",
        "  ,, ,,",
        "  my_field , , ,",
        "  , ",
        "  ,",
        "  another_field",
        "}  , ,",
        ", ,",
        doc=ParsedOperation("query", [ParsedField("my_field"), ParsedField("another_field")]),
    )


def test_simple_nested_query():
    doc_test("{ node { id } }", doc=ParsedOperation("query", [ParsedField("node", subfields=[ParsedField("id")])]))


def test_nested_query_with_arguments():
    doc_test(
        '{ node(arg1: 100) { id(arg2: "example") } }',
        doc=ParsedOperation(
            "query",
            [
                ParsedField(
                    "node", arguments={"arg1": 100}, subfields=[ParsedField("id", arguments={"arg2": "example"})]
                )
            ],
        ),
    )


def test_simple_alias():
    doc_test("{ alias: field }", doc=ParsedOperation("query", [ParsedField("field", "alias")]))


def test_alias_with_arguments():
    doc_test(
        "{ alias: field(arg: true) }",
        doc=ParsedOperation("query", [ParsedField("field", "alias", arguments={"arg": True})]),
    )


def test_alias_with_complex_field():
    doc_test(
        "{ alias: field(arg: false) { nested } }",
        doc=ParsedOperation(
            "query", [ParsedField("field", "alias", arguments={"arg": False}, subfields=[ParsedField("nested")])]
        ),
    )


@pytest.mark.parametrize("comma", COMMAS)
@pytest.mark.parametrize("exclamation", EXCLAMATIONS)
@pytest.mark.parametrize("left,right", VARIABLE_BRACKETS)
def test_named_query_with_variable(comma, exclamation, left, right):
    doc_test(
        "query MyQuery($var1: " + left + "int" + exclamation + right + comma + ") { foo(arg: $var1) }",
        doc=ParsedOperation(
            "query",
            [ParsedField("foo", arguments={"arg": ParsedVariable("var1")})],
            ["var1"],
            {},
            "MyQuery",
        ),
    )


@pytest.mark.parametrize("comma", COMMAS)
@pytest.mark.parametrize("exclamation", EXCLAMATIONS)
@pytest.mark.parametrize("left,right", VARIABLE_BRACKETS)
def test_unnamed_query_with_variable(comma, exclamation, left, right):
    doc_test(
        "query($var1: " + left + "int" + exclamation + right + comma + ") { foo(arg: $var1) }",
        doc=ParsedOperation(
            "query",
            [ParsedField("foo", arguments={"arg": ParsedVariable("var1")})],
            ["var1"],
            {},
        ),
    )


@pytest.mark.parametrize("comma", COMMAS)
@pytest.mark.parametrize("exclamation", EXCLAMATIONS)
@pytest.mark.parametrize("left,right", VARIABLE_BRACKETS)
def test_named_query_with_default_variable(comma, exclamation, left, right):
    doc_test(
        "query MyQuery($var1: " + left + "int" + exclamation + right + " = 1" + comma + ") { foo(arg: $var1) }",
        doc=ParsedOperation(
            "query",
            [ParsedField("foo", arguments={"arg": ParsedVariable("var1")})],
            ["var1"],
            {"var1": 1},
            "MyQuery",
        ),
    )


@pytest.mark.parametrize("comma", COMMAS)
@pytest.mark.parametrize("exclamation", EXCLAMATIONS)
@pytest.mark.parametrize("left,right", VARIABLE_BRACKETS)
def test_unnamed_query_with_default_variable(comma, exclamation, left, right):
    doc_test(
        "query($var1: " + left + "int" + exclamation + right + " = 1" + comma + ") { foo(arg: $var1) }",
        doc=ParsedOperation(
            "query",
            [ParsedField("foo", arguments={"arg": ParsedVariable("var1")})],
            ["var1"],
            {"var1": 1},
        ),
    )


@pytest.mark.parametrize("comma", COMMAS)
@pytest.mark.parametrize("exclamation", EXCLAMATIONS)
@pytest.mark.parametrize("left,right", VARIABLE_BRACKETS)
def test_unnamed_query_with_variables(comma, exclamation, left, right):
    doc_test(
        "query($var1: "
        + left
        + "int"
        + exclamation
        + right
        + ", $var2: "
        + left
        + "str"
        + exclamation
        + right
        + ", $__1var3: "
        + left
        + "bool"
        + exclamation
        + right
        + comma
        + ") { foo(arg: $var1) }",
        doc=ParsedOperation(
            "query",
            [ParsedField("foo", arguments={"arg": ParsedVariable("var1")})],
            ["var1", "var2", "__1var3"],
            {},
        ),
    )


@pytest.mark.parametrize("comma", COMMAS)
@pytest.mark.parametrize("exclamation", EXCLAMATIONS)
@pytest.mark.parametrize("left,right", VARIABLE_BRACKETS)
def test_named_query_with_variables(comma, exclamation, left, right):
    doc_test(
        "query MyQuery($var1: "
        + left
        + "int"
        + exclamation
        + right
        + ", $var2: "
        + left
        + "str"
        + exclamation
        + right
        + ", $__1var3: "
        + left
        + "bool"
        + exclamation
        + right
        + comma
        + ") { foo(arg: $var1) }",
        doc=ParsedOperation(
            "query",
            [ParsedField("foo", arguments={"arg": ParsedVariable("var1")})],
            ["var1", "var2", "__1var3"],
            {},
            "MyQuery",
        ),
    )


@pytest.mark.parametrize("comma", COMMAS)
@pytest.mark.parametrize("exclamation", EXCLAMATIONS)
@pytest.mark.parametrize("left,right", VARIABLE_BRACKETS)
def test_unnamed_query_with_default_variables(comma, exclamation, left, right):
    doc_test(
        "query($var1: "
        + left
        + "int"
        + exclamation
        + right
        + ", $var2: "
        + left
        + "str"
        + exclamation
        + right
        + ' = "foo", $__1var3: '
        + left
        + "bool"
        + exclamation
        + right
        + comma
        + ") { foo(arg: $var1) }",
        doc=ParsedOperation(
            "query",
            [ParsedField("foo", arguments={"arg": ParsedVariable("var1")})],
            ["var1", "var2", "__1var3"],
            {"var2": "foo"},
        ),
    )


@pytest.mark.parametrize("comma", COMMAS)
@pytest.mark.parametrize("exclamation", EXCLAMATIONS)
@pytest.mark.parametrize("left,right", VARIABLE_BRACKETS)
def test_named_query_with_default_variables(comma, exclamation, left, right):
    doc_test(
        "query TestQuery($var1: "
        + left
        + "int"
        + exclamation
        + right
        + ", $var2: "
        + left
        + "str"
        + exclamation
        + right
        + ' = "foo", $__1var3: '
        + left
        + "bool"
        + exclamation
        + right
        + comma
        + ") { foo(arg: $var1) }",
        doc=ParsedOperation(
            "query",
            [ParsedField("foo", arguments={"arg": ParsedVariable("var1")})],
            ["var1", "var2", "__1var3"],
            {"var2": "foo"},
            "TestQuery",
        ),
    )


@pytest.mark.parametrize("exclamation", EXCLAMATIONS)
def test_duplicate_query_variables(exclamation):
    with pytest.raises(VisitationError) as info:
        parse_document("query MyQuery($var: int, $var: str" + exclamation + ") { foo }")
    assert str(info.value).splitlines()[0] == "ValueError: Duplicate variable in operation: 'var'"


@pytest.mark.parametrize("comma", COMMAS)
@pytest.mark.parametrize(
    ["raw_arg", "parsed_arg"],
    {
        "null": None,
        "1": 1,
        "123456789101112": 123456789101112,
        "0": 0,
        "-0": 0,
        "-100000": -100000,
        "0.0": 0.0,
        "-0.0": 0.0,
        "0e0": 0.0,
        "1e0": 1.0,
        "-1.1": -1.1,
        "-1.23e4": -1.23e4,
        "-1.2E-3": -1.2e-3,
        "1.5E6": 1.5e6,
        "true": True,
        "false": False,
        '""': "",
        '"foo"': "foo",
        '"\\""': '"',
        '"\u0A0A"': "\u0A0A",
        '"ʇǝɯɐ ʇᴉs ɹolop ɯnsdᴉ ɯǝɹo˥"': "ʇǝɯɐ ʇᴉs ɹolop ɯnsdᴉ ɯǝɹo˥",
        '"""triple quoted string"""': "triple quoted string",
        '"""three quote\\"""and more"""': 'three quote"""and more',
        r'"abcdef123~!@#$%^&*()_+{}|[]\n\r\t\"\\"': 'abcdef123~!@#$%^&*()_+{}|[]\n\r\t"\\',
        "$my_variable": ParsedVariable("my_variable"),
        "$__123_variable": ParsedVariable("__123_variable"),
        "$_": ParsedVariable("_"),
        "my_enum": ParsedEnum("my_enum"),
        "__123_enum": ParsedEnum("__123_enum"),
        "_": ParsedEnum("_"),
        "[]": [],
        "[1]": [1],
        '[[], "a"]': [[], "a"],
        "[$var1, enum2, 123]": [ParsedVariable("var1"), ParsedEnum("enum2"), 123],
        "{}": {},
        '{a: "foo"}': {"a": "foo"},
        '{a: [1, 2], b: "bar"}': {"a": [1, 2], "b": "bar"},
        '{a: ["a", "b"], b: 123, c: "test", d: true}': {"a": ["a", "b"], "b": 123, "c": "test", "d": True},
    }.items(),
)
def test_argument_types(comma, raw_arg, parsed_arg):
    doc_test(
        "{ field(arg: " + raw_arg + comma + ") }",
        doc=ParsedOperation("query", [ParsedField("field", arguments={"arg": parsed_arg})]),
    )
    doc_test(
        "{ field(list_arg: [" + raw_arg + comma + "]) }",
        doc=ParsedOperation("query", [ParsedField("field", arguments={"list_arg": [parsed_arg]})]),
    )
    doc_test(
        "{ field(object_arg: {foo: " + raw_arg + comma + "}) }",
        doc=ParsedOperation("query", [ParsedField("field", arguments={"object_arg": {"foo": parsed_arg}})]),
    )


@pytest.mark.parametrize("comma", COMMAS)
def test_multiple_arguments(comma):
    doc_test(
        '{ field(arg1: 0, arg2: true, arg3: "test"' + comma + ") }",
        doc=ParsedOperation("query", [ParsedField("field", arguments={"arg1": 0, "arg2": True, "arg3": "test"})]),
    )


def test_duplicate_arguments():
    with pytest.raises(VisitationError) as info:
        parse_document("{ field(arg: 0, arg: 1) }")
    assert str(info.value).splitlines()[0] == "ValueError: Argument found twice in feature: 'arg'"


def test_duplicate_object_keys():
    with pytest.raises(VisitationError) as info:
        parse_document("{ field(arg: {a: 1, a: 2}) }")
    assert str(info.value).splitlines()[0] == "ValueError: Key found twice in object: 'a'"


def test_multiple_anonymous_errors():
    with pytest.raises(VisitationError) as info:
        parse_document("{ foo } { bar }")
    assert str(info.value).splitlines()[0] == "ValueError: Multiple anonymous operations defined, only one allowed"


def test_duplicate_operation_name():
    with pytest.raises(VisitationError) as info:
        parse_document("mutation a { foo } query a { bar }")

    assert str(info.value).splitlines()[0] == "ValueError: Operation name duplicated: 'a'"


def test_aliases():
    expected = ParsedOperation("query", [ParsedField("bar", "foo")])
    doc_test("{ foo: bar }", doc=expected)
    doc_test("{foo:bar}", doc=expected)
    doc_test("{  foo \t\t\n : \t\n bar \t }", doc=expected)
    doc_test("{ foo \n\n# comment here\n:# another comment\n\t  bar\n# final comment\n}", doc=expected)

    expected = ParsedOperation("query", [ParsedField("bar", "foo"), ParsedField("baz")])
    doc_test("{foo:bar baz}", doc=expected)
    doc_test("{foo: bar baz:baz }", doc=expected)
    doc_test("{foo: bar, baz}", doc=expected)


def test_full_document():
    parsed = parse_document(
        """#comment line

        \t\t#more comments

        query q1 {
          plain_field
          plain_field_comma,
          comma_on_newline
          # and after comment
          , # with a trailing comment
          field_arg_int(int: 1),
          ___underscores,
          _123123
          plain_nested {
            inner_plain
          }
          # nested field with argument
          arg_nested(s: "foo") { # end of line comment
            plain_inner
          }
        }

        query q2 {
          second_query
          alias1: field,
          alias2: field(a: "b")
        }

        mutation my_mutation {
          some {
            deeply {
              aliased: nested(arg: 10.5) {
                fields {
                  in
                  here
                }
              }
            }
          }
        }
        """
    )

    assert len(parsed) == 3
    assert parsed["q1"] == ParsedOperation(
        "query",
        name="q1",
        fields=[
            ParsedField("plain_field", "plain_field"),
            ParsedField("plain_field_comma", "plain_field_comma"),
            ParsedField("comma_on_newline", "comma_on_newline"),
            ParsedField("field_arg_int", "field_arg_int", arguments={"int": 1}),
            ParsedField("___underscores", "___underscores"),
            ParsedField("_123123", "_123123"),
            ParsedField("plain_nested", "plain_nested", subfields=[ParsedField("inner_plain", "inner_plain")]),
            ParsedField(
                "arg_nested",
                "arg_nested",
                arguments={"s": "foo"},
                subfields=[ParsedField("plain_inner", "plain_inner")],
            ),
        ],
    )
    assert parsed["q2"] == ParsedOperation(
        "query",
        [
            ParsedField("second_query"),
            ParsedField("field", "alias1"),
            ParsedField("field", "alias2", arguments={"a": "b"}),
        ],
        name="q2",
    )
    assert parsed["my_mutation"] == ParsedOperation(
        "mutation",
        [
            ParsedField(
                "some",
                subfields=[
                    ParsedField(
                        "deeply",
                        subfields=[
                            ParsedField(
                                "nested",
                                "aliased",
                                arguments={"arg": 10.5},
                                subfields=[ParsedField("fields", subfields=[ParsedField("in"), ParsedField("here")])],
                            )
                        ],
                    )
                ],
            )
        ],
        name="my_mutation",
    )


def test_parse_query():
    assert parse_query("{ foo }") == ParsedOperation("query", [ParsedField("foo")])
    assert parse_query("query { foo }") == ParsedOperation("query", [ParsedField("foo")])
    assert parse_query("query MyQuery { foo }") == ParsedOperation("query", [ParsedField("foo")], name="MyQuery")


def test_parse_query_mutation():
    assert parse_query("mutation { foo }") == ParsedOperation("mutation", [ParsedField("foo")])
    assert parse_query("mutation MyMutation { foo }") == ParsedOperation(
        "mutation", [ParsedField("foo")], name="MyMutation"
    )


def test_parse_query_multiple():
    document = """
        query Query1 {
          foo
        }
        query Query2 {
          bar
        }
        mutation Mutation1 {
          baz
        }
        """
    for name in ("Query1", "Query2", "Mutation1"):
        assert parse_query(document, name).name == name

    with pytest.raises(ValueError) as info:
        parse_query(document)
    assert str(info.value) == "Multiple operations defined but none selected"

    with pytest.raises(ValueError) as info:
        parse_query(document, "UNKNOWN")
    assert str(info.value) == "Operation with name 'UNKNOWN' not defined in document"
