import json

from django.core.serializers.json import DjangoJSONEncoder


def to_jsonable(data):
    """Coerce serializer output into something a JSONField can store.

    DRF passes values from ReadOnlyField straight through, so model properties
    returning Decimal/date (Invoice.balance, Lease.monthly_rent_equivalent, ...)
    reach the JSONField unconverted and raise TypeError on insert.
    """
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))
