"""정규화 회귀를 외부 IO·설정·파일쓰기 차단 아래 직접 실행한다."""
from __future__ import annotations


def run_standardize_tests():
    import os
    from pathlib import Path
    import runpy
    import sys
    root = Path(__file__).resolve().parents[2]
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root))

    def guard(event, args):
        if event in {'socket.connect', 'socket.getaddrinfo', 'subprocess.Popen', 'os.system'}:
            raise AssertionError('External operation blocked: ' + event)
        if event == 'open' and isinstance(args[0], (str, bytes)):
            path = Path(os.fsdecode(args[0])).resolve()
            mode, flags = args[1:3]
            if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or flags & (os.O_WRONLY | os.O_RDWR):
                raise AssertionError('File write blocked')
            if path.name == '.env' or (path.is_relative_to(root) and path.suffix not in {'.py', '.pyc'}):
                raise AssertionError('Project configuration/data read blocked')
    sys.addaudithook(guard)
    tests = runpy.run_path(str(root / 'tests/fundamental/test_standardize.py'))
    failed = []
    names = sorted(n for n in tests if n.startswith('test_'))
    for name in names:
        try:
            tests[name]()
            print('PASS', name)
        except Exception as exc:
            failed.append(name)
            print('FAIL', name, type(exc).__name__, str(exc))
    print(f'{len(names)-len(failed)}/{len(names)} normalization regressions passed')
    if failed:
        raise AssertionError('Failed regressions: ' + ', '.join(failed))


if __name__ == '__main__':
    run_standardize_tests()
