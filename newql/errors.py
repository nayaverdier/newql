class NewQLError(RuntimeError):
    pass


class QueryError(NewQLError):
    pass


class SchemaWarning(Warning):
    pass
