from src.agents.fundamental.domain.normalization.standardize import standardize_year_rows


def row(account_id, amount, **overrides):
    return dict(account_id=account_id, account_nm=account_id, thstrm_amount=amount,
                rcept_no='20260301000001', sj_div='BS', currency='KRW', **overrides)


def test_nonfinite_amounts_are_not_financial_values():
    for amount in ('NaN', 'nan', 'Infinity', '-inf', '1e4000', float('nan'), float('inf')):
        assert standardize_year_rows([row('ifrs-full_Assets', amount)], '2025') == {}


def test_zero_negative_and_comma_amounts_are_preserved():
    for amount, expected in ((0, 0.0), ('-100', -100.0), ('1,234.50', 1234.5)):
        assert standardize_year_rows([row('ifrs-full_Assets', amount)], '2025')['assets'].value == expected


def test_invalid_newer_filing_does_not_replace_known_amount():
    newer = row('ifrs-full_Assets', 'NaN')
    newer['rcept_no'] = '20260302000001'
    metrics = standardize_year_rows([row('ifrs-full_Assets', 100), newer], '2025')
    assert metrics['assets'].value == 100
    assert metrics['assets'].rcept_no == '20260301000001'


def test_derivation_requires_matching_known_filing_currency_and_balance_sheet():
    base = row('ifrs-full_EquityAndLiabilities', 100)
    equity = row('ifrs-full_Equity', 40)
    for change in ({'rcept_no': '20260302000001'}, {'currency': 'USD'}, {'sj_div': 'IS'}):
        changed = dict(equity, **change)
        assert 'liabilities' not in standardize_year_rows([base, changed], '2025')
    for missing in ('', None, 'unknown', '123', '２０２６０３０１０００００１'):
        assert 'liabilities' not in standardize_year_rows([
            dict(base, rcept_no=missing), dict(equity, rcept_no=missing)], '2025')
    assert 'liabilities' not in standardize_year_rows([
        dict(base, sj_div=''), dict(equity, sj_div='')], '2025')


def test_matching_sources_derive_liabilities_without_replacing_reported_amount():
    base = row('ifrs-full_EquityAndLiabilities', 100)
    equity = row('ifrs-full_Equity', 40)
    derived = standardize_year_rows([base, equity], '2025')['liabilities']
    assert derived.value == 60
    assert derived.rcept_no == base['rcept_no']
    assert derived.currency == 'KRW' and derived.sj_div == 'BS'
    reported = standardize_year_rows([base, equity, row('ifrs-full_Liabilities', 55)], '2025')['liabilities']
    assert reported.value == 55 and reported.account_id == 'ifrs-full_Liabilities'


def test_nonfinite_derived_difference_is_not_emitted():
    assert 'liabilities' not in standardize_year_rows([
        row('ifrs-full_EquityAndLiabilities', '1e308'), row('ifrs-full_Equity', '-1e308')], '2025')


def test_missing_currency_never_proves_derivation_but_keeps_explicit_amounts():
    base = row('ifrs-full_EquityAndLiabilities', 100)
    equity = row('ifrs-full_Equity', 40)
    for missing in (None, '', '   ', 0, False):
        for rows in ([dict(base, currency=missing), equity],
                     [base, dict(equity, currency=missing)],
                     [dict(base, currency=missing), dict(equity, currency=missing)]):
            metrics = standardize_year_rows(rows, '2025')
            assert 'liabilities' not in metrics
            assert metrics['equity_and_liabilities'].value == 100
            assert metrics['equity'].value == 40
        reported = standardize_year_rows([dict(base, currency=missing), equity,
            dict(row('ifrs-full_Liabilities', 55), currency=missing)], '2025')
        assert reported['liabilities'].value == 55
    no_currency = dict(base)
    no_currency.pop('currency')
    metrics = standardize_year_rows([no_currency, equity], '2025')
    assert 'liabilities' not in metrics
    assert metrics['equity_and_liabilities'].currency == 'KRW'


def test_currency_provenance_follows_selected_latest_row_not_any_row():
    base = row('ifrs-full_EquityAndLiabilities', 100)
    equity = row('ifrs-full_Equity', 40)
    latest_unknown = dict(base, rcept_no='20260302000001', currency=None)
    latest_equity = dict(equity, rcept_no='20260302000001')
    for rows in ([base, latest_unknown, latest_equity], [latest_unknown, base, latest_equity]):
        metrics = standardize_year_rows(rows, '2025')
        assert 'liabilities' not in metrics
        assert metrics['equity_and_liabilities'].rcept_no == '20260302000001'
    # 더 오래된 결측 행은 최신 정상 근거의 통화 provenance를 지우지 않는다.
    old_unknown = dict(base, currency=None)
    known_latest = dict(base, rcept_no='20260302000001')
    for rows in ([old_unknown, known_latest, latest_equity], [known_latest, old_unknown, latest_equity]):
        assert standardize_year_rows(rows, '2025')['liabilities'].value == 60


def test_same_filing_duplicate_keeps_first_value_currency_and_provenance_together():
    equity = row('ifrs-full_Equity', 40)
    for first_currency, later_currency, derivable in (
            ('KRW', 'USD', True), ('USD', 'KRW', False),
            ('KRW', None, True), (None, 'KRW', False)):
        first = dict(row('ifrs-full_EquityAndLiabilities', 100), currency=first_currency)
        duplicate = dict(row('ifrs-full_EquityAndLiabilities', 200), currency=later_currency)
        metrics = standardize_year_rows([first, duplicate, equity], '2025')
        chosen = metrics['equity_and_liabilities']
        assert chosen.value == 100
        assert chosen.currency == (first_currency or 'KRW')
        assert ('liabilities' in metrics) is derivable
        if derivable:
            assert metrics['liabilities'].value == 60


def test_explicit_other_business_year_is_not_relabelled_as_requested_year():
    for year in ("2024", 2024, " 2024 "):
        assert standardize_year_rows([dict(row("ifrs-full_Assets", 999), bsns_year=year)], "2025") == {}
    for year in ("2025", 2025, " 2025 "):
        result = standardize_year_rows([dict(row("ifrs-full_Assets", 0), bsns_year=year)], "2025")
        assert result["assets"].value == 0 and result["assets"].fiscal_year == "2025"


def test_wrong_year_latest_filing_cannot_override_or_supply_derived_component():
    current = dict(row("ifrs-full_Assets", 100), bsns_year="2025")
    wrong = dict(row("ifrs-full_Assets", 999), bsns_year="2024", rcept_no="20260302000001", currency="USD")
    for rows in ([current, wrong], [wrong, current]):
        provenance = {}
        result = standardize_year_rows(rows, "2025", currency_provenance=provenance)
        assert result["assets"].value == 100 and result["assets"].currency == "KRW"
        assert provenance == {"assets": True}
    base = dict(row("ifrs-full_EquityAndLiabilities", 100), bsns_year="2025")
    equity = dict(row("ifrs-full_Equity", 40), bsns_year="2024")
    assert "liabilities" not in standardize_year_rows([base, equity], "2025")


def test_absent_business_year_legacy_compatibility_is_not_year_proof():
    for missing in (None, "", "   "):
        result = standardize_year_rows([dict(row("ifrs-full_Assets", -10), bsns_year=missing)], "2025")
        assert result["assets"].value == -10
    assert standardize_year_rows([row("ifrs-full_Assets", 100)], "2025")["assets"].value == 100


def test_explicit_report_period_mismatch_cannot_override_amount_or_provenance():
    codes = ('11011', '11013', '11012', '11014')
    for expected in codes:
        valid = row('ifrs-full_Assets', 0, reprt_code=expected)
        for other in codes:
            if other == expected:
                continue
            wrong = dict(valid, thstrm_amount='999', reprt_code=other,
                         rcept_no='20260302000001', currency='USD')
            proof = {}
            result = standardize_year_rows([valid, wrong], '2025',
                                          reprt_code=expected, currency_provenance=proof)
            assert result['assets'].value == 0 and result['assets'].currency == 'KRW'
            assert proof == {'assets': True}
            assert standardize_year_rows([wrong], '2025', reprt_code=expected) == {}


def test_explicit_report_period_mismatch_cannot_supply_derived_liabilities():
    base = row('ifrs-full_EquityAndLiabilities', 100, reprt_code='11011')
    equity = row('ifrs-full_Equity', 40, reprt_code='11013')
    assert 'liabilities' not in standardize_year_rows([base, equity], '2025', reprt_code='11011')
    equity['reprt_code'] = '11011'
    assert standardize_year_rows([base, equity], '2025', reprt_code='11011')['liabilities'].value == 60


def test_missing_or_nonstandard_report_code_is_legacy_not_period_proof():
    for code in (None, '', 'unknown', '１１０１３', 11013):
        value = row('ifrs-full_Assets', -100, reprt_code=code)
        assert standardize_year_rows([value], '2025', reprt_code='11011')['assets'].value == -100
    # A legacy caller with no expected period retains its original behavior.
    assert standardize_year_rows([row('ifrs-full_Assets', 5, reprt_code='11013')], '2025')['assets'].value == 5


def test_matching_report_keeps_current_amount_not_previous_comparison_columns():
    from copy import deepcopy
    for code in ('11011', '11013', '11012', '11014'):
        current = row('ifrs-full_Assets', -100, reprt_code=code, bsns_year='2025',
                      frmtrm_amount='999', frmtrm_nm='2024', bfefrmtrm_amount='888')
        before = deepcopy(current)
        result = standardize_year_rows([current], '2025', reprt_code=code)
        assert result['assets'].value == -100 and result['assets'].fiscal_year == '2025'
        assert current == before
        previous = dict(current, bsns_year='2024', thstrm_amount='50')
        assert standardize_year_rows([previous], '2024', reprt_code=code)['assets'].value == 50
