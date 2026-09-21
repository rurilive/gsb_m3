"""事件 schema 与字段校验。

字段类型用字符串声明，可选 str / int / float / bool / list / dict。
defaults 给出字段的默认值，renames 声明字段改名（旧名到新名）。
"""

TYPE_NAMES = ("str", "int", "float", "bool", "list", "dict")


class SchemaError(Exception):
    """schema 定义或事件数据不合规时抛出。"""


def type_ok(value, type_name):
    """值是否符合声明的类型名。bool 不当作 int，int 不当作 float。"""
    if type_name == "str":
        return isinstance(value, str)
    if type_name == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "float":
        return isinstance(value, float)
    if type_name == "bool":
        return isinstance(value, bool)
    if type_name == "list":
        return isinstance(value, list)
    if type_name == "dict":
        return isinstance(value, dict)
    raise SchemaError("unknown type name: %s" % type_name)


class Schema:
    """一个事件类型的某个版本。"""

    def __init__(self, name, version, fields, required=(), defaults=None, renames=None):
        self.name = name
        self.version = version
        self.fields = dict(fields)
        self.required = tuple(required)
        self.defaults = dict(defaults or {})
        self.renames = dict(renames or {})
        for type_name in self.fields.values():
            if type_name not in TYPE_NAMES:
                raise SchemaError("unknown type name: %s" % type_name)
        for field in self.required:
            if field not in self.fields:
                raise SchemaError("required field not declared: %s" % field)
        for field, value in self.defaults.items():
            if field not in self.fields:
                raise SchemaError("default for undeclared field: %s" % field)
            if not type_ok(value, self.fields[field]):
                raise SchemaError(
                    "default for %s expects %s" % (field, self.fields[field])
                )

    def field_names(self):
        """本版本声明的字段名，按声明顺序。"""
        return list(self.fields)

    def validate(self, data):
        """校验一份事件数据，返回问题描述列表，空列表表示合规。"""
        problems = []
        for field in self.required:
            if field not in data:
                problems.append("missing required field: %s" % field)
        for field, value in data.items():
            if field not in self.fields:
                problems.append("unknown field: %s" % field)
            elif not type_ok(value, self.fields[field]):
                problems.append(
                    "field %s expects %s, got %s"
                    % (field, self.fields[field], type(value).__name__)
                )
        return problems

    def __repr__(self):
        return "Schema(%r, v%d, fields=%s)" % (
            self.name,
            self.version,
            list(self.fields),
        )


ORDER_V1 = Schema(
    "order",
    1,
    {"order_id": "str", "amount": "int", "note": "str"},
    required=("order_id", "amount"),
    defaults={"note": ""},
)
