"""혼합 회계기준의 collect→기존 부족 응답을 무키·무외부IO로 검증한다."""
from __future__ import annotations


def run_basis_tests():
    import ast
    from dataclasses import asdict
    from datetime import datetime, timezone
    import json
    import os
    from pathlib import Path
    import runpy
    import sys
    from types import SimpleNamespace as NS
    import unittest

    root = Path(__file__).resolve().parents[2]
    source = root / 'src/agents/fundamental'
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
    from src.agents.fundamental.domain.contracts import FundamentalRequest, FundamentalResponse
    from src.agents.fundamental.domain.normalization.standardize import standardize_year_rows
    from src.agents.fundamental.domain.reporting.period import period_basis

    def functions(path, namespace):
        tree = ast.parse(path.read_text(encoding='utf8'))
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
        return namespace

    failures = runpy.run_path(str(source / 'application/failures.py'))
    workflow = ast.parse((source / 'application/nodes/workflow.py').read_text(encoding='utf8'))
    route = eval(compile(ast.Expression(next(n for n in ast.walk(workflow) if isinstance(n, ast.Lambda))), '<route>', 'eval'))

    class Cases(unittest.TestCase):
        def collect(self, missing=(), empty=False, fs_div='CFS', latest=False, missing_currency=False, wrong_year=False, cached=False, unsupported=False, wrong_period=False):
            self.calls, self.extra = [], []
            def fetch(corp, year, *, reprt_code, fs_div, use_cache):
                self.calls.append((year, fs_div))
                rows = [] if empty or (year, fs_div) in missing else [dict(
                    account_id='ifrs-full_Revenue', account_nm='매출액', thstrm_amount='100',
                    rcept_no=str(year)+'0301000001', sj_div='IS', currency='KRW')]
                if wrong_period:
                    for row in rows:
                        row["reprt_code"] = "11013"
                if wrong_year:
                    for row in rows:
                        row['bsns_year'] = str(year - 1)
                if missing_currency:
                    for row in rows:
                        row.pop('currency')
                return NS(rows=rows, source_record=NS(reason=None, year=year, fs_div=fs_div, source='cache' if cached else 'dart'))
            def shares(*a, **kw):
                self.extra.append('shares')
                return None
            def insights(*a, **kw):
                self.extra.append('insights')
                return {}, 0
            def summary(records):
                return dict(financial_network_calls=sum(r.source == 'dart' for r in records), financial_source_count=len(records),
                    financial_sources=[dict(year=r.year, fs_div=r.fs_div) for r in records])
            selection = NS(bsns_year=2025, reprt_code='11011', reprt_name='사업보고서',
                mode='latest' if latest else 'annual', probe_calls=3 if latest else 0,
                probe_records=[NS(reason='latest_report_probe', year=2025, fs_div='CFS', source=origin)
                               for origin in ('dart','cache','dart')] if latest else [])
            def resolver(ticker):
                if unsupported:
                    raise LookupError('synthetic unsupported ticker')
                return 'synthetic'
            ns = dict(Any=object, FundamentalAgentState=dict, DartSourceRecord=object, asdict=asdict,
                resolve=resolver, resolution_metadata=lambda t:None,
                resolve_name=lambda t:'합성 기업', UnknownStockCodeError=LookupError,
                latest_annual_selection=lambda:selection, discover_latest_report=lambda *a:selection,
                fetch_financial_statement_rows=fetch, standardize_year_rows=standardize_year_rows,
                summarize_source_records=summary, fetch_share_count=shares,
                fetch_regular_report_insights=insights, period_basis=period_basis)
            ns = functions(source / 'application/nodes/collect_node.py', ns)
            request = FundamentalRequest(request_id='synthetic', trace_id='synthetic', ticker='005930', years=3, fs_div=fs_div, report_mode='latest' if latest else 'annual')
            state = ns['collect_node'](dict(request=request, use_cache=False))
            return dict(state, request=request)

        def test_mixed_basis_blocks_calculation_inputs_and_extra_fetches(self):
            state = self.collect(missing={(2024,'CFS')})
            self.assertEqual(self.calls, [(2023,'CFS'),(2024,'CFS'),(2024,'OFS'),(2025,'OFS')])
            self.assertEqual(self.extra, [])
            self.assertEqual(state['data_status'], 'empty_data')
            self.assertEqual(state['yearly_metrics'], {})
            self.assertEqual(state['fs_div'], '')
            self.assertIn('MIXED_ACCOUNTING_BASIS', state['risk_flags'])
            self.assertNotIn('DART_EMPTY_DATA', state['risk_flags'])
            self.assertEqual(state['dart_calls'], 4)
            self.assertEqual(len(state['source_records']), 4)
            self.assertEqual(route(state), 'report')

        def test_mixed_report_uses_existing_schema_without_fake_verified_or_zero_calls(self):
            state = self.collect(missing={(2024,'CFS')})
            history = []
            ns = dict(Any=object, FundamentalAgentState=dict, FundamentalResponse=FundamentalResponse,
                datetime=datetime, timezone=timezone, record_failure=failures['record_failure'],
                append_history=history.append, recent_stats=lambda:{})
            ns = functions(source / 'application/nodes/report_node.py', ns)
            response = ns['report_node'](state)['response']
            self.assertEqual(response.verdict_label, 'insufficient_data')
            self.assertEqual(response.ratios, {})
            self.assertEqual(response.trend['years'], [])
            self.assertEqual(response.evidence, [])
            self.assertEqual(response.meta['fs_div'], '')
            self.assertEqual(response.meta['workflow'], ['collect','report'])
            summary = response.meta['verification_summary']
            for key in ('binding_passed','consistency_passed','guard_passed','verdict_stable'):
                self.assertIs(summary[key], False)
            self.assertEqual(summary['outcome'], 'insufficient_data')
            self.assertEqual(response.meta['cost_summary']['dart_network_calls'], 4)
            self.assertEqual(response.meta['cost_summary']['probe_calls'], 0)
            self.assertEqual(response.meta['cost_summary']['llm_calls'], 0)
            self.assertEqual(response.meta['retrieval_summary']['financial_source_count'], 4)
            self.assertIn('회계 기준이 혼합', response.verdict)
            self.assertEqual(len(history), 1)
            self.assertIs(response.meta['failures'][-1]['retryable'], False)
            json.dumps(response.model_dump(), ensure_ascii=False, allow_nan=False)

        def test_latest_mixed_basis_preserves_actual_network_probe_not_cached_probe(self):
            state = self.collect(missing={(2024,'CFS')}, latest=True)
            history = []
            ns = dict(Any=object, FundamentalAgentState=dict, FundamentalResponse=FundamentalResponse,
                datetime=datetime, timezone=timezone, record_failure=failures['record_failure'],
                append_history=history.append, recent_stats=lambda:{})
            ns = functions(source / 'application/nodes/report_node.py', ns)
            response = ns['report_node'](state)['response']
            self.assertEqual(state['dart_calls'], 7)
            self.assertEqual(len(state['source_records']), 7)
            self.assertEqual(response.meta['cost_summary']['dart_network_calls'], 6)
            self.assertEqual(response.meta['cost_summary']['probe_calls'], 2)
            self.assertEqual(response.meta['cost_summary']['llm_calls'], 0)
            self.assertEqual(self.extra, [])

        def test_homogeneous_cfs_preserves_normal_path(self):
            state = self.collect()
            self.assertEqual(state['data_status'], 'normal')
            self.assertEqual(state['fs_div'], 'CFS')
            self.assertEqual(route(state), 'normalize')
            self.assertEqual(len(state['yearly_metrics']), 3)
            self.assertNotIn('MIXED_ACCOUNTING_BASIS', state['risk_flags'])
            self.assertEqual(self.extra, ['shares','insights'])

        def test_homogeneous_ofs_fallback_and_explicit_ofs_remain_supported(self):
            for missing, requested in (({(2023,'CFS')}, 'CFS'), (set(), 'OFS')):
                state = self.collect(missing=missing, fs_div=requested)
                self.assertEqual(state['data_status'], 'normal')
                self.assertEqual(state['fs_div'], 'OFS')
                self.assertNotIn('MIXED_ACCOUNTING_BASIS', state['risk_flags'])
                self.assertEqual(route(state), 'normalize')

        def test_collect_preserves_missing_currency_sidecar_without_changing_metric_shape(self):
            state = self.collect(missing_currency=True)
            self.assertEqual(state['data_status'], 'normal')
            self.assertEqual(state['yearly_metrics']['2025']['revenue'].currency, 'KRW')
            self.assertEqual(state['yearly_metrics']['2025']['revenue'].value, 100)
            self.assertEqual(state['metric_currency_provenance'],
                             {year: {'revenue': False} for year in ('2023','2024','2025')})
            known = self.collect()
            self.assertTrue(all(proof['revenue'] for proof in known['metric_currency_provenance'].values()))

        def test_wrong_year_rows_cannot_reach_calculation_or_normal_report(self):
            state = self.collect(wrong_year=True)
            self.assertEqual(state['data_status'], 'empty_data')
            self.assertFalse(any(state['yearly_metrics'].values()))
            self.assertEqual(route(state), 'report')
            self.assertEqual(self.extra, [])
            ns = dict(Any=object, FundamentalAgentState=dict, FundamentalResponse=FundamentalResponse,
                datetime=datetime, timezone=timezone, record_failure=failures['record_failure'],
                append_history=lambda item: None, recent_stats=lambda:{})
            ns = functions(source / 'application/nodes/report_node.py', ns)
            response = ns['report_node'](state)['response']
            self.assertEqual(response.verdict_label, 'insufficient_data')
            self.assertEqual(response.ratios, {})
            self.assertEqual(response.evidence, [])
            self.assertEqual(response.trend['years'], [])
            self.assertEqual(response.meta['workflow'], ['collect', 'report'])
            self.assertEqual(state['retrieval_summary']['financial_network_calls'], 3)
            json.dumps(response.model_dump(), ensure_ascii=False, allow_nan=False)

        def insufficient(self, state):
            ns = dict(Any=object, FundamentalAgentState=dict, FundamentalResponse=FundamentalResponse,
                datetime=datetime, timezone=timezone, record_failure=failures['record_failure'],
                append_history=lambda item: None, recent_stats=lambda:{})
            ns = functions(source / 'application/nodes/report_node.py', ns)
            return ns['report_node'](state)['response']

        def test_unexecuted_checks_never_pass_for_any_insufficient_route(self):
            for options in ({'empty': True}, {'unsupported': True}, {'wrong_year': True},
                            {'missing': {(2024, 'CFS')}}):
                state = self.collect(**options)
                # Stale input must not promote a route which did not execute verify.
                state['verification_summary'] = dict(outcome='passed', binding_passed=True)
                response = self.insufficient(state)
                summary = response.meta['verification_summary']
                self.assertEqual(summary['outcome'], 'insufficient_data')
                for key in ('binding_passed', 'consistency_passed', 'guard_passed', 'verdict_stable'):
                    self.assertIs(summary[key], False)
                self.assertTrue(summary['reasons'])
                self.assertEqual(response.meta['workflow'], ['collect', 'report'])
                self.assertEqual(response.verdict_label, 'insufficient_data')
                self.assertNotIn('erd_payload', response.meta)
                wire = json.loads(response.model_dump_json())
                self.assertEqual(wire['meta']['verification_summary'], summary)

        def test_badge_requires_passed_outcome_not_legacy_insufficient_true(self):
            tree = ast.parse((source / 'api/rendering/html_builder.py').read_text(encoding='utf8'))
            node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_verification_passed')
            ns = dict(Any=object)
            exec(compile(ast.Module(body=[node], type_ignores=[]), '<badge>', 'exec'), ns)
            check = ns['_verification_passed']
            fields = dict.fromkeys(('binding_passed', 'consistency_passed', 'guard_passed', 'verdict_stable'), True)
            self.assertTrue(check({'verification_summary': dict(fields, outcome='passed')}))
            for outcome in ('insufficient_data', 'failed', 'not_run', None):
                self.assertFalse(check({'verification_summary': dict(fields, outcome=outcome)}))
            self.assertFalse(check({'verification_summary': dict(fields, outcome='passed', guard_passed=False)}))

        def test_explicit_wrong_report_period_routes_to_insufficient_without_extra_calls(self):
            state = self.collect(wrong_period=True)
            self.assertEqual(state['data_status'], 'empty_data')
            self.assertFalse(any(state['yearly_metrics'].values()))
            self.assertFalse(any(state['metric_currency_provenance'].values()))
            self.assertEqual(route(state), 'report')
            self.assertEqual(self.extra, [])
            response = self.insufficient(state)
            self.assertEqual(response.ratios, {})
            self.assertEqual(response.meta['verification_summary']['outcome'], 'insufficient_data')
            self.assertFalse(response.meta['verification_summary']['binding_passed'])
            self.assertEqual(response.meta['cost_summary']['dart_network_calls'], 3)

        def test_general_empty_response_preserves_observed_source_counts(self):
            for cached, expected in ((False, 4), (True, 0)):
                state = self.collect(empty=True, cached=cached)
                response = self.insufficient(state)
                self.assertEqual(response.meta['cost_summary']['dart_network_calls'], expected)
                self.assertEqual(response.meta['cost_summary']['probe_calls'], 0)
                self.assertEqual(response.meta['cost_summary']['llm_calls'], 0)
                self.assertIsNone(response.meta['cost_summary']['prompt_tokens'])
                self.assertNotIn('call_usage', response.meta)
                self.assertNotIn('complete_usage', response.meta)
                self.assertEqual(self.extra, [])

        def test_latest_empty_preserves_network_probes_without_cached_probes(self):
            state = self.collect(empty=True, latest=True)
            response = self.insufficient(state)
            self.assertEqual(response.meta['cost_summary']['dart_network_calls'], 6)
            self.assertEqual(response.meta['cost_summary']['probe_calls'], 2)

        def test_empty_without_observations_is_unknown_not_zero(self):
            state = self.collect(empty=True)
            for summary in ({}, None):
                state['retrieval_summary'] = summary
                response = self.insufficient(state)
                self.assertIsNone(response.meta['cost_summary']['dart_network_calls'])
                self.assertIsNone(response.meta['cost_summary']['probe_calls'])
                json.dumps(response.model_dump(), ensure_ascii=False, allow_nan=False)

        def test_unsupported_before_collection_preserves_known_zero(self):
            state = self.collect(unsupported=True)
            response = self.insufficient(state)
            self.assertEqual(self.calls, [])
            self.assertEqual(self.extra, [])
            self.assertEqual(response.meta['cost_summary']['dart_network_calls'], 0)
            self.assertEqual(response.meta['cost_summary']['probe_calls'], 0)
            self.assertEqual(response.meta['cost_summary']['llm_calls'], 0)

        def test_genuine_empty_data_keeps_existing_reason_and_path(self):
            state = self.collect(empty=True)
            self.assertEqual(state['data_status'], 'empty_data')
            self.assertIn('DART_EMPTY_DATA', state['risk_flags'])
            self.assertNotIn('MIXED_ACCOUNTING_BASIS', state['risk_flags'])
            self.assertEqual(route(state), 'report')
            self.assertEqual(self.extra, [])

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Cases))
    if not result.wasSuccessful():
        raise AssertionError('Accounting-basis regression failed')


if __name__ == '__main__':
    run_basis_tests()
