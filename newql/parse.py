from ast import literal_eval
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from parsimonious import Grammar, NodeVisitor  # type: ignore

# Note: null and enum have "" suffix so that the visitor function is
# called, see https://github.com/erikrose/parsimonious/issues/111
grammar = Grammar(
    r'''
document                 = _? (operation _?)+

operation                = named_explicit_operation / explicit_operation / fields
explicit_operation       = operation_type operation_variables? _? fields
named_explicit_operation = operation_type _ identifier operation_variables? _? fields
operation_variables      = _? "(" _? operation_variable (separator operation_variable)* _? ")"
operation_variable       = "$" identifier _? ":" _? identifier (_? "=" _? value)?
operation_type           = "query" / "mutation"

fields                   = "{" _? field (separator field)* _? "}"
separator                = _? ","? _?
field                    = field_alias? identifier field_arguments? (_? fields)?
field_alias              = identifier _? ":" _?
field_arguments          = _? "(" _? pair (separator pair)* _? ")"
pair                     = identifier _? ":" _? value
value                    = list / object / boolean / null / string / number / integer / variable / enum

boolean                  = "true" / "false"
null                     = "null" ""
string                   = ~r'"""(\\.|(?!""").)*"""'s / ~r'"(\\[^\n]|[^\\"\n])*"'
variable                 = "$" identifier
enum                     = identifier ""
integer                  = ~"-?(0|[1-9][0-9]*)"
number                   = scientific / decimal
decimal                  = ~r"-?[0-9]+\.[0-9]+"
scientific               = ~r"-?(0|[1-9][0-9]*)(\.[0-9]+)?[eE]-?[0-9]+"
list                     = "[" _? (value (separator value)* _?)? "]"
object                   = "{" _? (pair (separator pair)* _?)? "}"

identifier               = ~"[_a-zA-Z][_a-zA-Z0-9]*"
white                    = ~r"[\s]+"
_                        = (white / comment)+
comment                  = "#" ~r".*(\n|$)"
'''
)


MISSING = object()


@dataclass
class ParsedField:
    """Represents a parsed field requested in an operation"""

    name: str
    alias: str = None  # type: ignore
    arguments: Optional[Dict[str, Any]] = None
    subfields: Optional[List["ParsedField"]] = None

    def __post_init__(self):
        if self.alias is None:
            self.alias = self.name


@dataclass
class ParsedEnum:
    """Represents an enum used as an argument value"""

    name: str


@dataclass
class ParsedVariable:
    """Represents a variable defined in or used by a query"""

    name: str


@dataclass
class ParsedOperation:
    """Represents a parsed operation from a NewQL query"""

    operation: str  # 'query' or 'mutation'
    fields: List[ParsedField]
    variables: Optional[List[str]] = None
    variable_defaults: Optional[Dict[str, Any]] = None
    name: Optional[str] = None


class NewQLVisitor(NodeVisitor):
    def visit_document(self, _, visited_children):
        output = {}
        for operation, _ in visited_children[1] or ():
            if operation.name in output:
                if operation.name is None:
                    message = "Multiple anonymous operations defined, only one allowed"
                else:
                    message = f"Operation name duplicated: '{operation.name}'"
                raise ValueError(message)
            output[operation.name] = operation

        return output

    def visit_operation(self, _, visited_children):
        operation = visited_children[0]
        # anonymous operation case
        if isinstance(operation, list):
            operation = ParsedOperation(operation="query", name=None, fields=operation)
        return operation

    def visit_explicit_operation(self, _, visited_children):
        operation, parsed_variables, _, fields = visited_children
        if parsed_variables:
            variables, variable_defaults = parsed_variables[0]
        else:
            variables = variable_defaults = None

        return ParsedOperation(operation, fields, variables, variable_defaults)

    def visit_named_explicit_operation(self, _, visited_children):
        operation, _, name, parsed_variables, _, fields = visited_children
        if parsed_variables:
            variables, variable_defaults = parsed_variables[0]
        else:
            variables = variable_defaults = None

        return ParsedOperation(operation, fields, variables, variable_defaults, name)

    def visit_operation_variables(self, _, visited_children):
        variable, default_value = visited_children[3]

        variables = [variable]
        variable_defaults = {}
        if default_value is not MISSING:
            variable_defaults[variable] = default_value

        for variable_match in visited_children[4] or ():
            variable, default_value = variable_match[1]
            if variable in variables:
                raise ValueError(f"Duplicate variable in operation: '{variable}'")
            variables.append(variable)
            if default_value is not MISSING:
                variable_defaults[variable] = default_value

        return variables, variable_defaults

    def visit_operation_variable(self, _, visited_children):
        variable_name = visited_children[1]
        # variable_type = visited_children[5]
        variable_default = visited_children[6]
        if variable_default is None:
            default_value = MISSING
        else:
            default_value = variable_default[0][3]

        return variable_name, default_value

    def visit_operation_type(self, node, _):
        return node.text

    def visit_fields(self, _, visited_children):
        fields = [visited_children[2]]

        additional_fields = visited_children[3]
        if additional_fields:
            for (_, field) in additional_fields:
                fields.append(field)

        return fields

    def visit_field(self, _, visited_children):
        name = visited_children[1]
        alias = visited_children[0]
        if alias is None:
            alias = name
        else:
            alias = alias[0]

        arguments = visited_children[2]
        if arguments is not None:
            arguments = arguments[0]

        subfields = visited_children[3]
        if subfields is not None:
            subfields = subfields[0][1]

        return ParsedField(name=name, alias=alias, arguments=arguments, subfields=subfields)

    def visit_field_alias(self, _, visited_children):
        return visited_children[0]

    def visit_field_arguments(self, _, visited_children):
        key, value = visited_children[3]
        arguments = {key: value}
        for additional_argument in visited_children[4] or ():
            key, value = additional_argument[1]
            if key in arguments:
                raise ValueError(f"Argument found twice in feature: '{key}'")
            arguments[key] = value

        return arguments

    def visit_pair(self, _, visited_children):
        argument_name = visited_children[0]
        value = visited_children[4]
        return argument_name, value

    def visit_value(self, _, visited_children):
        return visited_children[0]

    def visit_boolean(self, node, _):
        return node.text == "true"

    def visit_null(self, _node, _):
        return None

    def visit_string(self, node, _):
        return literal_eval(node.text)

    def visit_variable(self, _, visited_children):
        return ParsedVariable(visited_children[1])

    def visit_enum(self, _, visited_children):
        return ParsedEnum(visited_children[0])

    def visit_integer(self, node, _):
        return int(node.text)

    def visit_number(self, _, visited_children):
        return float(visited_children[0].text)

    def visit_list(self, _, visited_children):
        data = visited_children[2]
        if data is None:
            return []
        else:
            data = data[0]

        result = [data[0]]
        for _, additional in data[1] or ():
            result.append(additional)

        return result

    def visit_object(self, _, visited_children):
        data = visited_children[2]
        if data is None:
            return {}
        else:
            data = data[0]

        key, value = data[0]
        result = {key: value}
        for _, (key, value) in data[1] or ():
            if key in result:
                raise ValueError(f"Key found twice in object: '{key}'")
            result[key] = value

        return result

    def visit_identifier(self, node, _):
        return node.text

    def generic_visit(self, node, visited_children):
        if not visited_children and node.text == "":
            return None

        return visited_children or node


# TODO: replace VisitationError with the original errors (instead of stringifying them)
def parse_document(query_string: str) -> Dict[str, ParsedOperation]:
    visitor = NewQLVisitor()
    tree = grammar.parse(query_string)
    return visitor.visit(tree)


def parse_query(query_string: str, name: str = None) -> ParsedOperation:
    document = parse_document(query_string)
    if name is None:
        if len(document) > 1:
            raise ValueError("Multiple operations defined but none selected")

        return next(iter(document.values()))

    if name not in document:
        raise ValueError(f"Operation with name '{name}' not defined in document")

    return document[name]
