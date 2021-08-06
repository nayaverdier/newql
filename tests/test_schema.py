from enum import Enum
from typing import List, Optional

import pytest

from newql import ExecutionContext, QueryError, Schema, field
from newql.errors import SchemaWarning


@pytest.fixture
def full_schema():
    class User:
        name = field(type=str, doc="The full name of the user")
        email = field(type=str, doc="The users contact email")
        age = field(type=int, doc="The current age of the user")

        @field
        def phone(user, context: ExecutionContext, area_code: Optional[bool] = True) -> str:
            """The user's contact phone number

            Args:
                area_code: Whether or not to include the area code
            """

            if area_code:
                return user["area_code"] + "-" + user["phone"]
            else:
                return user["phone"]

        @field
        def custom_arg(user, context: ExecutionContext, argument: str) -> Optional[str]:
            return argument

    USERS = {
        "U1": {
            "name": "John Smith",
            "email": "johnsmith@example.com",
            "age": 34,
            "area_code": "555",
            "phone": "555-1234",
        },
        "U2": {
            "name": "Jane Doe",
            "email": "janedoe@example.com",
            "age": 31,
            "area_code": "555",
            "phone": "555-9876",
        },
        "U-buggy-phone": {
            "name": "Adam Appleseed",
            "email": "adamappleseed@example.com",
            "age": 28,
            "area_code": None,
            "phone": "555-0000",
        },
    }

    class Query:
        @field(type=User)
        def user(_, context: ExecutionContext, user_id: str) -> dict:
            if user_id in USERS:
                return USERS[user_id]
            else:
                raise ValueError(f"User '{user_id}' not found")

        @field(type=List[User])
        def users(_, context: ExecutionContext, user_ids: List[str]) -> List[dict]:
            return [user for user_id, user in USERS.items() if user_id in user_ids]

    class Mutation:
        pass

    return Schema(Query, Mutation)


def test_empty_schema():
    s = Schema()
    assert s.query is None
    assert s.mutation is None
    assert s.introspect() == {"queryType": None, "mutationType": None, "types": []}

    for operation in ("", "query", "mutation"):
        with pytest.raises(QueryError) as info:
            s.execute(operation + " { foo }")
        assert str(info.value) == f"Operation '{operation or 'query'}' is not defined for this schema"


def test_barebones_schema():
    class Query:
        pass

    class Mutation:
        pass

    schema = Schema(Query, Mutation)
    assert schema.query == Query
    assert schema.mutation == Mutation
    assert schema.introspect() == {
        "queryType": None,
        "mutationType": None,
        "types": [],
    }

    assert schema.execute("{ foo }") == {"data": {}, "errors": [{"foo": "Unknown field requested"}]}


def test_execute(full_schema):
    assert full_schema.execute('{ user(user_id: "U1") { name } }') == {"data": {"user": {"name": "John Smith"}}}

    # different from GraphQL, which would require the nested fields
    assert full_schema.execute('{ user(user_id: "U1") }') == {
        "data": {
            "user": {
                "name": "John Smith",
                "email": "johnsmith@example.com",
                "age": 34,
                "area_code": "555",
                "phone": "555-1234",
            }
        }
    }

    not_found_result = full_schema.execute('{ fake_user: user(user_id: "U-fake") { name } }')
    assert not_found_result["data"] == {"fake_user": None}
    assert not_found_result["errors"][0]["fake_user"] == "User 'U-fake' not found"


def test_execute_list_field(full_schema):
    assert full_schema.execute('{ users(user_ids: ["U1"]) { name } }') == {"data": {"users": [{"name": "John Smith"}]}}


def test_execute_string_list():
    class Query:
        @field
        def my_list(_parent, _context) -> List[str]:
            return ["foo", "bar"]

    schema = Schema(Query)

    assert schema.execute("{ my_list }") == {"data": {"my_list": ["foo", "bar"]}}


def test_untyped_list():
    class Query:
        @field
        def my_list(_parent, _context) -> list:
            return ["foo", "bar"]

    schema = Schema(Query)

    assert schema.execute("{ my_list }") == {"data": {"my_list": ["foo", "bar"]}}
    assert schema.introspect() == {
        "queryType": {"name": "Query"},
        "mutationType": None,
        "types": [
            {
                "kind": "SCALAR",
                "name": "object",
                "description": (
                    "An arbitrary, flexible type determined at runtime " "(can be str, int, float, bool, list, object)"
                ),
            },
            {
                "kind": "OBJECT",
                "name": "Query",
                "fields": [
                    {
                        "name": "my_list",
                        "description": None,
                        "args": [],
                        "type": {"kind": "LIST", "ofType": {"kind": "SCALAR", "name": "object"}},
                    }
                ],
                "description": None,
                "interfaces": [],
            },
        ],
    }


def test_untyped_typing_list():
    class Query:
        @field
        def my_list(_parent, _context) -> List:
            return ["foo", "bar"]

    schema = Schema(Query)

    assert schema.execute("{ my_list }") == {"data": {"my_list": ["foo", "bar"]}}
    assert schema.introspect() == {
        "queryType": {"name": "Query"},
        "mutationType": None,
        "types": [
            {
                "kind": "SCALAR",
                "name": "object",
                "description": (
                    "An arbitrary, flexible type determined at runtime " "(can be str, int, float, bool, list, object)"
                ),
            },
            {
                "kind": "OBJECT",
                "name": "Query",
                "fields": [
                    {
                        "name": "my_list",
                        "description": None,
                        "args": [],
                        "type": {"kind": "LIST", "ofType": {"kind": "SCALAR", "name": "object"}},
                    }
                ],
                "description": None,
                "interfaces": [],
            },
        ],
    }


def test_enum():
    class MyEnum(Enum):
        FOO = "foo"
        BAR = "bar"
        BAZ = "baz"

    class Query:
        @field
        def my_enum(_, _context, my_argument: MyEnum) -> str:
            if isinstance(my_argument, str):
                return f"Custom: {my_argument}"
            else:
                return my_argument.value

        @field
        def enum_optional(_, _context, my_argument: Optional[MyEnum]) -> str:
            if not my_argument:
                return "Argument None"
            elif isinstance(my_argument, str):
                return f"Custom: {my_argument}"
            else:
                return my_argument.value

        @field
        def enum_default_none(_, _context, my_argument: MyEnum = None) -> str:
            if not my_argument:
                return "Argument None"
            elif isinstance(my_argument, str):
                return f"Custom: {my_argument}"
            else:
                return my_argument.value

        @field
        def enum_optional_default_none(_, _context, my_argument: Optional[MyEnum] = None) -> str:
            if not my_argument:
                return "Argument None"
            elif isinstance(my_argument, str):
                return f"Custom: {my_argument}"
            else:
                return my_argument.value

        @field
        def enum_list(_, _context, my_argument: List[MyEnum]) -> List[str]:
            result = []
            for arg in my_argument:
                if not arg:
                    result.append("Argument None")
                elif isinstance(arg, str):
                    result.append(f"Custom: {arg}")
                else:
                    result.append(arg.value)

            return result

        @field
        def enum_optional_list(_, _context, my_argument: List[Optional[MyEnum]]) -> List[str]:
            result = []
            for arg in my_argument:
                if not arg:
                    result.append("Argument None")
                elif isinstance(arg, str):
                    result.append(f"Custom: {arg}")
                else:
                    result.append(arg.value)

            return result

    schema = Schema(Query)

    assert schema.execute("{ my_enum(my_argument: FOO) }") == {"data": {"my_enum": "foo"}}
    assert schema.execute("{ my_enum(my_argument: unknown) }") == {"data": {"my_enum": "Custom: unknown"}}

    for name in ("enum_optional", "enum_default_none", "enum_optional_default_none"):
        assert schema.execute("{ " + name + "(my_argument: FOO) }") == {"data": {name: "foo"}}
        assert schema.execute("{ " + name + "(my_argument: unknown) }") == {"data": {name: "Custom: unknown"}}
        assert schema.execute("{ " + name + "(my_argument: null) }") == {"data": {name: "Argument None"}}

    for name in ("enum_list", "enum_optional_list"):
        assert schema.execute("{ " + name + "(my_argument: []) }") == {"data": {name: []}}
        assert schema.execute("{ " + name + '(my_argument: [FOO, unknown, "random", null]) }') == {
            "data": {name: ["foo", "Custom: unknown", "Custom: random", "Argument None"]}
        }

    assert schema.introspect() == {
        "queryType": {"name": "Query"},
        "mutationType": None,
        "types": [
            {"kind": "SCALAR", "name": "String", "description": "A UTF-8 encoded string"},
            {
                "kind": "ENUM",
                "name": "MyEnum",
                "fields": [],
                "description": "An enumeration.",
                "enumValues": [{"name": "FOO"}, {"name": "BAR"}, {"name": "BAZ"}],
            },
            {
                "kind": "OBJECT",
                "name": "Query",
                "fields": [
                    {
                        "name": "enum_default_none",
                        "description": None,
                        "args": [
                            {
                                "name": "my_argument",
                                "description": None,
                                "type": {"kind": "ENUM", "name": "MyEnum"},
                                "defaultValue": "null",
                            }
                        ],
                        "type": {"kind": "SCALAR", "name": "String"},
                    },
                    {
                        "name": "enum_list",
                        "description": None,
                        "args": [
                            {
                                "name": "my_argument",
                                "description": None,
                                "type": {
                                    "kind": "NON_NULL",
                                    "ofType": {"kind": "LIST", "ofType": {"kind": "ENUM", "name": "MyEnum"}},
                                },
                                "defaultValue": None,
                            }
                        ],
                        "type": {"kind": "LIST", "ofType": {"kind": "SCALAR", "name": "String"}},
                    },
                    {
                        "name": "enum_optional",
                        "description": None,
                        "args": [
                            {
                                "name": "my_argument",
                                "description": None,
                                "type": {"kind": "ENUM", "name": "MyEnum"},
                                "defaultValue": None,
                            }
                        ],
                        "type": {"kind": "SCALAR", "name": "String"},
                    },
                    {
                        "name": "enum_optional_default_none",
                        "description": None,
                        "args": [
                            {
                                "name": "my_argument",
                                "description": None,
                                "type": {"kind": "ENUM", "name": "MyEnum"},
                                "defaultValue": "null",
                            }
                        ],
                        "type": {"kind": "SCALAR", "name": "String"},
                    },
                    {
                        "name": "enum_optional_list",
                        "description": None,
                        "args": [
                            {
                                "name": "my_argument",
                                "description": None,
                                "type": {
                                    "kind": "NON_NULL",
                                    "ofType": {
                                        "kind": "LIST",
                                        "ofType": {"kind": "NON_NULL", "ofType": {"kind": "ENUM", "name": "MyEnum"}},
                                    },
                                },
                                "defaultValue": None,
                            }
                        ],
                        "type": {"kind": "LIST", "ofType": {"kind": "SCALAR", "name": "String"}},
                    },
                    {
                        "name": "my_enum",
                        "description": None,
                        "args": [
                            {
                                "name": "my_argument",
                                "description": None,
                                "type": {"kind": "NON_NULL", "ofType": {"kind": "ENUM", "name": "MyEnum"}},
                                "defaultValue": None,
                            }
                        ],
                        "type": {"kind": "SCALAR", "name": "String"},
                    },
                ],
                "description": None,
                "interfaces": [],
            },
        ],
    }


def test_execute_untyped_list_with_children():
    class Query:
        @field
        def my_list(_parent, _context) -> list:
            return [{"nested": "foo"}, {"nested": "bar"}]

    schema = Schema(Query)

    assert schema.execute("{ my_list { nested } }") == {"data": {"my_list": [{"nested": "foo"}, {"nested": "bar"}]}}


def test_execute_untyped_typing_list_with_children():
    class Query:
        @field
        def my_list(_parent, _context) -> List:
            return [{"nested": "foo"}, {"nested": "bar"}]

    schema = Schema(Query)

    assert schema.execute("{ my_list { nested } }") == {"data": {"my_list": [{"nested": "foo"}, {"nested": "bar"}]}}


def test_execute_variables(full_schema):
    assert full_schema.execute(
        "query MyQuery($user_id: str) { user(user_id: $user_id) { name phone }}", {"user_id": "U2"}
    ) == {"data": {"user": {"name": "Jane Doe", "phone": "555-555-9876"}}}


def test_execute_default_variable(full_schema):
    assert full_schema.execute(
        'query($custom_var: str = "default") { user(user_id: "U1") { custom_arg(argument: $custom_var) } }'
    ) == {"data": {"user": {"custom_arg": "default"}}}


def test_execute_override_default_variable(full_schema):
    assert (
        full_schema.execute(
            'query($custom_var: str = "default") { user(user_id: "U1") { custom_arg(argument: $custom_var) } }',
            {"custom_var": "overridden"},
        )
        == {"data": {"user": {"custom_arg": "overridden"}}}
    )


def test_undefined_variables(full_schema):
    assert full_schema.execute('{ user(user_id: "U1") { name } }', {"user_id": "U2"}) == {
        "data": {"user": {"name": "John Smith"}}
    }


def test_missing_variables(full_schema):
    with pytest.raises(QueryError) as info:
        full_schema.execute("query($user_id: str) { user(user_id: $user_id) { name } }", {})
    assert str(info.value) == "Required variables not provided: ['user_id']"


def test_single_alias(full_schema):
    assert full_schema.execute('{ user(user_id: "U1") { full_name:name } }') == {
        "data": {"user": {"full_name": "John Smith"}}
    }


def test_multiple_nested_aliases(full_schema):
    assert (
        full_schema.execute(
            """
        {
          user(user_id: "U2") {
            full_phone: phone(area_code: true)
            partial_phone: phone(area_code: false)
            default_phone: phone
          }
        }"""
        )
        == {
            "data": {
                "user": {"full_phone": "555-555-9876", "partial_phone": "555-9876", "default_phone": "555-555-9876"}
            }
        }
    )


def test_multiple_top_level_alias(full_schema):
    assert full_schema.execute('{ user1: user(user_id: "U1") { name } user2: user(user_id: "U2") { name } }') == {
        "data": {"user1": {"name": "John Smith"}, "user2": {"name": "Jane Doe"}}
    }


def test_missing_argument(full_schema):
    result = full_schema.execute("{ user { name } }")
    assert result["data"] == {"user": None}
    assert result["errors"][0]["user"] == "user() missing 1 required positional argument: 'user_id'"


def test_nested_error(full_schema):
    result = full_schema.execute('{ user_alias: user(user_id: "U-buggy-phone") { full_phone: phone } }')
    assert result["data"] == {"user_alias": {"full_phone": None}}
    assert result["errors"][0]["user_alias"]["full_phone"] == "unsupported operand type(s) for +: 'NoneType' and 'str'"


def test_default_resolver_getattr():
    class Product:
        def __init__(self, product_id: int, product_name: str):
            self.product_id = product_id
            self.product_name = product_name

        product_name = field("product_name", type=str)

    class Query:
        @field
        def product(_, context: ExecutionContext, product_id: int) -> Product:
            return Product(product_id, f"Random Product {product_id}")

    schema = Schema(Query)

    assert schema.execute("{ product(product_id: 5) { product_name } }") == {
        "data": {"product": {"product_name": "Random Product 5"}}
    }


def test_custom_type_introspection():
    class CustomType:
        """Custom docs"""

        pass

    expected = {
        "queryType": {"name": "Query"},
        "mutationType": None,
        "types": [
            {"kind": "SCALAR", "name": "CustomType", "fields": [], "description": "Custom docs"},
            {
                "kind": "OBJECT",
                "name": "Query",
                "fields": [
                    {
                        "name": "custom_type",
                        "description": None,
                        "args": [],
                        "type": {"kind": "SCALAR", "name": "CustomType"},
                    }
                ],
                "description": None,
                "interfaces": [],
            },
        ],
    }

    class Query:
        custom_type = field(type=CustomType)

    assert Schema(Query).introspect() == expected

    class Query:
        custom_type = field(type=CustomType())

    assert Schema(Query).introspect() == expected


def test_duplicate_type_name():
    def create_type() -> type:
        class Type:
            pass

        return Type

    class Query:
        field_1 = field(type=create_type())
        field_2 = field(type=create_type())

    with pytest.warns(SchemaWarning, match="Multiple types found with the same name during introspection: Type"):
        assert Schema(Query).introspect() == {
            "queryType": {"name": "Query"},
            "mutationType": None,
            "types": [
                {"kind": "SCALAR", "name": "Type", "fields": [], "description": None},
                {
                    "kind": "OBJECT",
                    "name": "Query",
                    "fields": [
                        {
                            "name": "field_1",
                            "description": None,
                            "args": [],
                            "type": {"kind": "SCALAR", "name": "Type"},
                        },
                        {
                            "name": "field_2",
                            "description": None,
                            "args": [],
                            "type": {"kind": "SCALAR", "name": "Type"},
                        },
                    ],
                    "description": None,
                    "interfaces": [],
                },
            ],
        }


FULL_GRAPHIQL_INTROSPECTION = """
query IntrospectionQuery {
  __schema {
    queryType {
      name
    }
    mutationType {
      name
    }
    subscriptionType {
      name
    }
    types {
      ...FullType
    }
    directives {
      name
      description
      locations
      args {
        ...InputValue
      }
    }
  }
}

fragment FullType on __Type {
  kind
  name
  description
  fields(includeDeprecated: true) {
    name
    description
    args {
      ...InputValue
    }
    type {
      ...TypeRef
    }
    isDeprecated
    deprecationReason
  }
  inputFields {
    ...InputValue
  }
  interfaces {
    ...TypeRef
  }
  enumValues(includeDeprecated: true) {
    name
    description
    isDeprecated
    deprecationReason
  }
  possibleTypes {
    ...TypeRef
  }
}

fragment InputValue on __InputValue {
  name
  description
  type {
    ...TypeRef
  }
  defaultValue
}

fragment TypeRef on __Type {
  kind
  name
  ofType {
    kind
    name
    ofType {
      kind
      name
      ofType {
        kind
        name
        ofType {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
              }
            }
          }
        }
      }
    }
  }
}
"""


def test_full_schema_introspection(full_schema):
    assert full_schema.execute("{ __schema }")["data"]["__schema"] == full_schema.introspect()

    expected = {
        "queryType": {"name": "Query"},
        "mutationType": None,
        "types": [
            {"kind": "SCALAR", "name": "Integer", "description": "An integer"},
            {"kind": "SCALAR", "name": "String", "description": "A UTF-8 encoded string"},
            {"kind": "SCALAR", "name": "Boolean", "description": "A boolean, true or false"},
            {
                "kind": "OBJECT",
                "name": "User",
                "fields": [
                    {
                        "name": "age",
                        "description": "The current age of the user",
                        "args": [],
                        "type": {"kind": "SCALAR", "name": "Integer"},
                    },
                    {
                        "name": "custom_arg",
                        "description": None,
                        "args": [
                            {
                                "name": "argument",
                                "description": None,
                                "type": {"kind": "NON_NULL", "ofType": {"kind": "SCALAR", "name": "String"}},
                                "defaultValue": None,
                            }
                        ],
                        "type": {"kind": "NON_NULL", "ofType": {"kind": "SCALAR", "name": "String"}},
                    },
                    {
                        "name": "email",
                        "description": "The users contact email",
                        "args": [],
                        "type": {"kind": "SCALAR", "name": "String"},
                    },
                    {
                        "name": "name",
                        "description": "The full name of the user",
                        "args": [],
                        "type": {"kind": "SCALAR", "name": "String"},
                    },
                    {
                        "name": "phone",
                        "description": "The user's contact phone number",
                        "args": [
                            {
                                "name": "area_code",
                                "description": "Whether or not to include the area code",
                                "type": {"kind": "SCALAR", "name": "Boolean"},
                                "defaultValue": "true",
                            }
                        ],
                        "type": {"kind": "SCALAR", "name": "String"},
                    },
                ],
                "description": None,
                "interfaces": [],
            },
            {
                "kind": "OBJECT",
                "name": "Query",
                "fields": [
                    {
                        "name": "user",
                        "description": None,
                        "args": [
                            {
                                "name": "user_id",
                                "description": None,
                                "type": {"kind": "NON_NULL", "ofType": {"kind": "SCALAR", "name": "String"}},
                                "defaultValue": None,
                            }
                        ],
                        "type": {"kind": "OBJECT", "name": "User"},
                    },
                    {
                        "name": "users",
                        "description": None,
                        "args": [
                            {
                                "name": "user_ids",
                                "description": None,
                                "type": {
                                    "kind": "NON_NULL",
                                    "ofType": {"kind": "LIST", "ofType": {"kind": "SCALAR", "name": "String"}},
                                },
                                "defaultValue": None,
                            }
                        ],
                        "type": {"kind": "LIST", "ofType": {"kind": "OBJECT", "name": "User"}},
                    },
                ],
                "description": None,
                "interfaces": [],
            },
        ],
    }

    assert full_schema.introspect() == expected
    assert full_schema.execute(FULL_GRAPHIQL_INTROSPECTION) == {"data": {"__schema": expected}}


def test_invalid_query_response(full_schema):
    assert full_schema.execute("gibberish") == {
        "data": None,
        "errors": ["Rule 'document' didn't match at 'gibberish' (line 1, column 1)."],
    }
