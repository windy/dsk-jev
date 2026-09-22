"""Versioned public-price estimates; unknown usage is never interpreted as free."""
import json
from decimal import Decimal
from pathlib import Path
PRICING = json.loads((Path(__file__).resolve().parents[1] / 'config/pricing.json').read_text())
def estimate(event, scenario):
    price = PRICING[scenario]
    inp, out, cache = (event.get(k) for k in ('input_tokens', 'output_tokens', 'cached_tokens'))
    if any(type(v) is not int or v < 0 for v in (inp, out)):
        return None
    if 'cached' in price:
        if type(cache) is not int or not 0 <= cache <= inp:
            return None
    else:
        cache = 0
    return ((inp-cache)*Decimal(price['input']) + cache*Decimal(price.get('cached', '0')) + out*Decimal(price['output']))/Decimal(1000000)
def costs(events, scenario):
    values = [estimate(e, scenario) for e in events]
    known = sum((v for v in values if v is not None), Decimal(0))
    return {'known_estimated_usd': str(known), 'unknown_cost_attempts': sum(v is None for v in values),
            'total_estimated_usd': str(known) if all(v is not None for v in values) else None}
