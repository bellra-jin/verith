"""Pure internal Technical plan. It never changes CF020 public Flow capability."""
from src.supervisor.domain.planning.interpret import interpret
from src.agents.technical.domain.boundary_contracts import parse_request,BoundaryInvalid

def build_plan(request):
    parsed=parse_request(request);query=parsed.data.original_query;intent=interpret(query)
    if intent.requested_views!=('technical',) or any(x in query.lower() for x in ('종합','주식 정보','주식정보','모든 관점','전체 분석','전부 실행','시장','증시','코스피','코스닥','전체 종목','말고','제외','빼고','아니라')):raise BoundaryInvalid()
    return parsed
