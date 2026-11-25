"""
Custom template filters.
Usage in templates:  {% load tracker_filters %}  then  {{ value|inr }}
"""
from django import template
import locale

register = template.Library()


@register.filter
def inr(value):
    """Format a number as Indian Rupees: ₹1,23,456"""
    try:
        value = float(value)
        # Indian numbering: last 3 digits, then groups of 2
        sign = '-' if value < 0 else ''
        value = abs(value)
        integer_part = int(value)
        decimal_part = round(value - integer_part, 2)

        s = str(integer_part)
        if len(s) > 3:
            last3 = s[-3:]
            rest = s[:-3]
            # Group remaining digits in pairs from the right
            groups = []
            while rest:
                groups.insert(0, rest[-2:])
                rest = rest[:-2]
            formatted = ','.join(groups) + ',' + last3
        else:
            formatted = s

        if decimal_part:
            return f'{sign}₹{formatted}.{str(decimal_part).split(".")[1][:2]}'
        return f'{sign}₹{formatted}'
    except (ValueError, TypeError):
        return value


@register.filter
def subtract(value, arg):
    """Subtract: {{ a|subtract:b }}"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return value
