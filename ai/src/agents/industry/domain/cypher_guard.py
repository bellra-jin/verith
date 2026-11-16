"""Conservative generated-read subset guard, not a Neo4j authorization boundary."""
from __future__ import annotations


class UnsupportedCypher(ValueError):
    def __init__(self):
        super().__init__("Generated Cypher is outside the supported read subset")


# Parser-work/input cap only, not a database timeout/result/cost budget.
MAX_GENERATED_QUERY_CHARS = 16_384

_BLOCKED = frozenset("""
CREATE INSERT MERGE DELETE DETACH SET REMOVE DROP ALTER RENAME GRANT DENY REVOKE
LOAD CSV FOREACH CALL SHOW START STOP TERMINATE ENABLE DISABLE USE CYPHER PROFILE
EXPLAIN EXECUTE RUN
""".split())
_READ_START = {"MATCH", "OPTIONAL", "WITH", "UNWIND", "RETURN"}
_GROUP_WORDS = _READ_START | {
    "WHERE", "AND", "OR", "NOT", "IN", "AS", "UNION", "DISTINCT", "WHEN", "THEN", "ELSE",
}
_FUNCTIONS = frozenset("""
count collect size length nodes relationships type labels startnode endnode id elementid
coalesce tolower toupper trim tostring sum avg min max round abs substring exists
all any none single reduce head last keys properties tointeger tofloat isempty
""".split())


def _tokens(query: str) -> list[tuple[str, str]]:
    tokens = []
    i = 0
    while i < len(query):
        char = query[i]
        if char.isspace():
            i += 1
            continue
        if query.startswith("//", i):
            end = i + 2
            while end < len(query) and query[end] not in {chr(13), chr(10)}:
                end += 1
            comment = query[i + 2:end]
            if chr(92) in comment or any(c in comment for c in (chr(133), chr(8232), chr(8233))):
                raise UnsupportedCypher()
            i = end
            continue
        if query.startswith("/*", i):
            end = query.find("*/", i + 2)
            if end < 0 or "/*" in query[i + 2:end] or chr(92) in query[i + 2:end]:
                raise UnsupportedCypher()
            i = end + 2
            continue
        if char in {"'", '"', chr(96)}:
            quoted_name = char == chr(96)
            if not quoted_name and i and query[i - 1] in "sS":
                raise UnsupportedCypher()  # Do not interpret newer interpolated strings.
            end, value = i + 1, ""
            while end < len(query):
                current = query[end]
                if current == char:
                    if quoted_name and end + 1 < len(query) and query[end + 1] == char:
                        value += char
                        end += 2
                        continue
                    break
                if current == chr(92):
                    if quoted_name or end + 1 >= len(query):
                        raise UnsupportedCypher()
                    escape = query[end + 1]
                    if escape == "u":
                        digits = query[end + 2:end + 6]
                        if len(digits) != 4 or any(c not in "0123456789abcdefABCDEF" for c in digits):
                            raise UnsupportedCypher()
                        end += 6
                    elif escape in {"t", "b", "n", "r", "f", chr(92), chr(39), chr(34)}:
                        end += 2
                    else:
                        raise UnsupportedCypher()
                    continue
                if quoted_name:
                    value += current
                end += 1
            if end >= len(query):
                raise UnsupportedCypher()
            tokens.append((value if quoted_name else "", "quoted" if quoted_name else "literal"))
            i = end + 1
            continue
        if char.isalpha() or char == "_" or char == "$":
            parameter = char == "$"
            end = i + 1
            while end < len(query) and (query[end].isalnum() or query[end] == "_"):
                end += 1
            if parameter and end == i + 1:
                raise UnsupportedCypher()
            tokens.append((query[i:end], "parameter" if parameter else "word"))
            i = end
            continue
        if char.isdigit():
            end = i + 1
            while end < len(query) and (query[end].isdigit() or query[end] in "._"):
                end += 1
            tokens.append((query[i:end], "number"))
            i = end
            continue
        if char not in "()[]{}.,:+-*/%=<>|!^;":
            raise UnsupportedCypher()
        tokens.append((char, "symbol"))
        i += 1
    return tokens


def validate_generated_cypher(query: str) -> None:
    if not isinstance(query, str) or len(query) > MAX_GENERATED_QUERY_CHARS:
        raise UnsupportedCypher()
    tokens = _tokens(query)
    if not tokens or tokens[0][1] != "word" or tokens[0][0].upper() not in _READ_START:
        raise UnsupportedCypher()
    if tokens[0][0].upper() == "OPTIONAL" and (len(tokens) < 2 or tokens[1][0].upper() != "MATCH"):
        raise UnsupportedCypher()
    stack, returned = [], False
    pairs = {")": "(", "]": "[", "}": "{"}
    for index, (value, kind) in enumerate(tokens):
        upper = value.upper()
        if kind == "word" and upper in _BLOCKED:
            raise UnsupportedCypher()
        if kind == "symbol":
            if value in "([{":
                stack.append(value)
            elif value in pairs:
                if not stack or stack.pop() != pairs[value]:
                    raise UnsupportedCypher()
            if value == ";" and index != len(tokens) - 1:
                raise UnsupportedCypher()
        if kind == "word" and upper == "RETURN" and not stack:
            returned = True
        if kind in {"word", "quoted"} and index + 1 < len(tokens) and tokens[index + 1][0] == "(":
            group = kind == "word" and upper in _GROUP_WORDS
            if (index and tokens[index - 1][0] == "."
                    or not group and value.lower() not in _FUNCTIONS):
                raise UnsupportedCypher()
    if stack or not returned:
        raise UnsupportedCypher()
