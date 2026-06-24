from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Allow dict lookup with a variable key in templates: {{ my_dict|get_item:key }}"""
    if dictionary is None:
        return None
    return dictionary.get(key)
