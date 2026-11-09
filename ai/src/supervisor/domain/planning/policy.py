"""Flow-only preparation policy; planning grants no execution authority."""
from src.supervisor.domain.models import StockContext
STOCK_DEPENDENT = frozenset({'technical','fundamental','flow'})
STOCK_OPTIONAL = frozenset({'industry'})

def decide(agent_type, resolution):
    return False, 'stock_not_resolved'

def context_for(resolution):
    return resolution.stock if resolution.status == 'resolved' else StockContext()

def final_status(resolution):
    return {'resolved':'ready_for_confirmation','ambiguous':'needs_stock_selection','not_found':'not_found'}[resolution.status]
