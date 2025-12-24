from django import template
from clinic_admin.utils import format_name_short as format_name_short_util

register = template.Library()

@register.simple_tag
def format_name_short(lname, fname, tname=None):
    return format_name_short_util(lname, fname, tname)
