"""실제 Pydantic으로 계산 회귀만 실행한다. 설정/DART 모듈은 실행하지 않는다.
Python 3.12와 lock 버전 Pydantic이 설치된 격리 환경에서 직접 실행한다.
"""
from __future__ import annotations


def run_calculator_tests():
    import ast
    from dataclasses import dataclass
    import os
    from pathlib import Path
    import runpy
    import sys
    from types import ModuleType

    root = Path(__file__).resolve().parents[2]
    source = root / 'src/agents/fundamental'
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root))
    # 검토한 기존 회귀 fixture 두 개만 읽는다. 임의 JSON/설정 허용은 아니다.
    fixtures = {root / 'tests/fundamental/fixtures' / name for name in
                ('synthetic_derived_liabilities_rows.json', 'lgchem_2025_cfs_rows.json')}

    def guard(event, args):
        if event in {'socket.connect', 'socket.getaddrinfo', 'subprocess.Popen', 'os.system'}:
            raise AssertionError('External operation blocked: ' + event)
        if event == 'open' and isinstance(args[0], (str, bytes)):
            path = Path(os.fsdecode(args[0])).resolve()
            mode, flags = args[1:3]
            if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or flags & (os.O_WRONLY | os.O_RDWR):
                raise AssertionError('File write blocked')
            if path.name == '.env' or (path.is_relative_to(root) and path.suffix not in {'.py', '.pyc'} and path not in fixtures):
                raise AssertionError('Project configuration/data read blocked')

    sys.addaudithook(guard)
    # 설정 모듈은 실행하지 않고 순수 literal 점수표만 읽는다.
    config_tree = ast.parse((source / 'core/config.py').read_text(encoding='utf8'))
    tables = next(n.value for n in config_tree.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'SCORE_TABLES' for t in n.targets))
    config = ModuleType('src.agents.fundamental.core.config')
    config.SCORE_TABLES = ast.literal_eval(tables)
    sys.modules[config.__name__] = config
    # DART 구현을 import하지 않고 실제 순수 ShareCountData 선언만 로드한다.
    name = 'src.agents.fundamental.infrastructure.data.regular_disclosure'
    regular = ModuleType(name)
    regular.__dict__['dataclass'] = dataclass
    sys.modules[name] = regular
    path = source / 'infrastructure/data/regular_disclosure.py'
    tree = ast.parse(path.read_text(encoding='utf8'))
    declaration = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ShareCountData')
    exec(compile(ast.Module(body=[declaration], type_ignores=[]), str(path), 'exec'), regular.__dict__)
    tests = {}
    for filename in ('test_calculators.py', 'test_standardize.py', 'test_ratio_currency.py', 'test_currency_display.py', 'test_currency_provenance.py', 'test_fallback_semantics.py', 'test_metric_claim_binding.py', 'test_verdict_guard.py',
                     'test_formatting.py', 'test_schema_builder.py', 'test_html_builder.py',
                     'test_golden_derived_liabilities.py', 'test_golden_lgchem.py'):
        namespace = runpy.run_path(str(root / 'tests/fundamental' / filename))
        for name, function in namespace.items():
            if name.startswith('test_'):
                if name in tests:
                    raise AssertionError('Duplicate test name: ' + name)
                tests[name] = function
    failed = []
    names = sorted(n for n in tests if n.startswith('test_'))
    for name in names:
        try:
            tests[name]()
            print('PASS', name)
        except Exception as exc:
            failed.append(name)
            print('FAIL', name, type(exc).__name__, str(exc))
    print(f'{len(names)-len(failed)}/{len(names)} calculator regressions passed')
    if failed:
        raise AssertionError('Failed regressions: ' + ', '.join(failed))


if __name__ == '__main__':
    run_calculator_tests()
