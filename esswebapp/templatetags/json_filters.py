"""Custom template filters for JSON serialization"""
import json
from django import template

register = template.Library()


@register.filter
def jsonify(value):
    """
    Convert a Python object to a JSON string.
    Usage: {{ value|jsonify }}
    """
    return json.dumps(value)