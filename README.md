# NewQL

[![CI](https://github.com/nayaverdier/newql/actions/workflows/ci.yml/badge.svg)](https://github.com/nayaverdier/newql/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/nayaverdier/newql/branch/main/graph/badge.svg)](https://codecov.io/gh/nayaverdier/newql)
[![pypi](https://img.shields.io/pypi/v/newql)](https://pypi.org/project/newql)
[![license](https://img.shields.io/github/license/nayaverdier/newql.svg)](https://github.com/nayaverdier/newql/blob/main/LICENSE)

A simplified GraphQL-esque library

Notable features:

- Schema defined using pythonic classes
- Introspection for support with the GraphiQL interface
  - Field / type / argument docstrings
  - Nested types
- Aliases
- Query variables
- Enums (can simply use pure python enums)
- Flexible type system (unlike GraphQL which coerces and validates more strictly)

What `NewQL` does not support:

- Fragments
- Directives
- Subscriptions
- Per-field or per-type introspection (the introspection returns all or nothing)

## Installation

Requires python 3.7+

```bash
pip install newql
```

## Usage

```python
from newql import ExecutionContext, Schema, field

class Product:
    """Represents a product in stock"""

    product_id = field(type=int)
    product_name = field(type=str)
    price = field(type=float)

class ProductQuery:
    # pass 'type' here since the function returns a dictionary,
    # but we want to actually resolve to a Product
    @field(type=Product)
    def product(_, context: ExecutionContext, product_id: int) -> dict:
        # The "Args" section of the docstring is parsed out to add
        # docs to the arguments (can be seen in GraphiQL)
        """Find a specific product by id

        Args:
            product_id: The ID of the product to find
        """

        products = {1: ("Product1", 49.99), 2: ("Product2", 94.49)}
        if product_id in products:
            name, price = products[product_id]
            return {"product_id": product_id, "product_name": name, "price": price}
        else:
            raise ValueError(f"Product not found: {product_id}")

schema = Schema(ProductQuery)
```

Explore the above example using `python -m newql.dev_server --schema newql.example.product_schema`:

```graphql
{
  product(product_id: 1) {
    price
    product_name
  }
}
```

Or execute a query through code:

```python
QUERY = """
{
  product(product_id: 1) {
    price
    product_name
  }
}
"""

from newql.example import product_schema
product_schema.execute(QUERY)
# => {"data": {"product": {"price": 49.99, "product_name": "Product1"}}}
```

A mutation class can be defined in exactly the same way as a query class,
and can be passed to `Schema` as a second positional argument or by the
`mutation` keyword argument.

```python
class Mutation:
    ...

schema = Schema(mutation=Mutation)
```

To start a dev server serving a GraphiQL interface:

```bash
python -m newql.dev_server  # uses the schema in newql.example

# can specify a custom schema
python -m newql.dev_server --schema <full import name of your schema>
# for example:
python -m newql.dev_server --schema my_module.nested_module.my_schema
```

Note that when defining a field inline and not specifying the field name,
the field name will be determined by the name of the variable to which it
is assigned. For example:

```python
class MyClass:
    my_field = field(type=str)
```

The field will be named `my_field`. This is achieved by the library `varname`,
however since it needs to parse AST to determine the name, it can take time.

If there are more than a couple hundred fields, it is recommended to explicitly
set the name of the field to avoid this performance hit:

```python
class MyClass:
    my_field = field("my_field", type=str)
```

## Development

Clone the repo, then from the project directory:

```bash
python3 -m venv .venv
. .venv/bin/activate

make install-dev
```

To run tests (and show coverage):

```bash
make test
```

Before making changes, fix formatting and check changes (isort, black, flake8, mypy):

```bash
make format check
```
