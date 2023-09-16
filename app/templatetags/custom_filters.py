from django import template
import os


register = template.Library()

@register.filter
def get_price_for_lot(current_price, lot_id):
    return current_price.get(lot_id, 0.0)

@register.filter
def file_exists(file_path):
    return os.path.exists(file_path)