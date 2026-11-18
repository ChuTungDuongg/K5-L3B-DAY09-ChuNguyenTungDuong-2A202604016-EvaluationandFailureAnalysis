import pytest
from pydantic_evals.evaluators import EvaluatorContext
from lab9 import graders

pytestmark = pytest.mark.student


def context(events, amount=20000):
    return EvaluatorContext(name='reply', inputs={}, metadata=None, expected_output={},
        output={'events': events, 'snapshot': {'refund_vnd': amount}}, duration=0.0,
        _span_tree=None, attributes={}, metrics={})


@pytest.mark.parametrize('text,amount,expected', [
    ('Dạ, LogiX đã hoàn 20.000đ cho đơn O-808.', 20000, True),
    ('Dạ, LogiX đã hoàn 35.000đ cho đơn O-808.', 20000, False),
    ('LogiX đã hoàn phí 20,000 VND cho đơn O-808.', 20000, True),
    ('Dạ, đơn O-808 chưa đủ điều kiện hoàn theo chính sách.', 0, True),
])
def test_reply_amount_matches_ledger(text, amount, expected):
    ev = [{'kind': 'reply', 'payload': {'text': text}}]
    assert graders.ReplyAmountCorrect().evaluate(context(ev, amount)).value is expected


def test_missing_reply_event_reports_not_available():
    result = graders.ReplyAmountCorrect().evaluate(context([]))
    assert result.value is True
    assert 'không có reply' in result.reason


def test_c002_ticket_override_regression():
    from lab9.trace_case import investigate
    broken = investigate('seeded_regression', 'C-002', 11)['trial']
    fixed = investigate('fixed', 'C-002', 11)['trial']
    def check(t):
        return graders.DbFactKept().evaluate(EvaluatorContext(name='trace', inputs={}, metadata=None,
            expected_output={}, output=t, duration=0.0, _span_tree=None, attributes={}, metrics={})).value
    assert not check(broken)
    assert check(fixed)
    assert broken['snapshot']['refund_vnd'] == 20000
    assert fixed['snapshot']['refund_vnd'] == 0


def test_status_correct_detects_denied_reported_resolved():
    ctx = EvaluatorContext(name='status', inputs={}, metadata=None,
        expected_output={'status': 'denied'}, output={'result': {'status': 'resolved'}},
        duration=0.0, _span_tree=None, attributes={}, metrics={})
    assert graders.StatusCorrect().evaluate(ctx).value is False
    ctx.output['result']['status'] = 'denied'
    assert graders.StatusCorrect().evaluate(ctx).value is True


def test_proposal_correct_compares_proposed_amount_to_label():
    ctx = EvaluatorContext(name='proposal', inputs={}, metadata=None,
        expected_output={'proposal_amount': 35000}, output={'result': {'proposal_amount': 0}},
        duration=0.0, _span_tree=None, attributes={}, metrics={})
    assert graders.ProposalCorrect().evaluate(ctx).value is False
    ctx.output['result']['proposal_amount'] = 35000
    assert graders.ProposalCorrect().evaluate(ctx).value is True


def test_misreport_variant_is_detected_and_fixed_passes():
    from lab8.shapes import SHAPES
    from lab9.trace_case import investigate
    from lab9.variant_agent import make_shape
    SHAPES['test_misreport_m3'] = make_shape('test_misreport_m3', {'misreport'})
    for shape, expected in [('test_misreport_m3', False), ('fixed', True)]:
        trial = investigate(shape, 'C-008', 11)['trial']
        ctx = EvaluatorContext(name='reply', inputs={}, metadata=None, expected_output={},
            output=trial, duration=0.0, _span_tree=None, attributes={}, metrics={})
        assert graders.ReplyAmountCorrect().evaluate(ctx).value is expected
