import io
import pandas as pd
import qrcode
import base64
from django.urls import reverse


def parse_uploaded_file(file_obj):
    try:
        if file_obj.name.endswith('.csv'):
            df = pd.read_csv(file_obj, dtype=str)
        elif file_obj.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_obj, dtype=str)
        else:
            return None, 'Unsupported file format. Use CSV or Excel.'
    except Exception as e:
        return None, f'Error parsing file: {str(e)}'

    df = df.dropna(how='all')
    headers = list(df.columns)
    rows = df.to_dict(orient='records')
    return {'headers': headers, 'rows': rows, 'row_count': len(rows)}, None


EXPECTED_FIELDS = ['barcode', 'product_name', 'expected_quantity']

STANDARD_HEADERS = {
    'barcode': [
        'barcode', 'barcode_id', 'item_code', 'item_code_id', 'item code',
        'sku', 'upc', 'ean', 'code', 'item_barcode', 'item barcode',
        'bar_code', 'product_code', 'product code',
    ],
    'product_name': [
        'product_name', 'product name', 'name', 'item_name', 'item name',
        'description', 'product_description', 'product description',
        'item_description', 'item description', 'desc', 'title',
    ],
    'expected_quantity': [
        'expected_quantity', 'expected quantity', 'quantity', 'qty',
        'expected_qty', 'expected qty', 'system_qty', 'system qty',
        'book_qty', 'book qty', 'count', 'remaining_quantity',
        'remaining quantity', 'stock_qty', 'stock qty', 'on_hand',
        'on hand', 'units',
    ],
    'category': [
        'category', 'department', 'dept', 'group', 'section', 'aisle',
    ],
}


def normalize_header(h):
    if pd.isna(h) or h is None:
        return ''
    return str(h).lower().strip().replace('-', '_').replace('  ', ' ')


def detect_column_mapping(headers):
    mapping = {}
    norm_headers = {normalize_header(h): h for h in headers}

    for field, aliases in STANDARD_HEADERS.items():
        for alias in aliases:
            if alias in norm_headers:
                mapping[field] = norm_headers[alias]
                break

    return mapping


def apply_mapping_and_parse(rows, column_mapping):
    parsed = []
    for row in rows:
        item = {}
        for field, source_col in column_mapping.items():
            raw_val = row.get(source_col) if source_col else None
            if pd.isna(raw_val) or raw_val is None:
                value = ''
            elif isinstance(raw_val, float) and raw_val.is_integer():
                value = str(int(raw_val)).strip()
            else:
                value = str(raw_val).strip()

            if field == 'expected_quantity':
                try:
                    value = int(float(value)) if value else None
                except (ValueError, TypeError):
                    value = None
            item[field] = value
        if item.get('barcode'):
            parsed.append(item)
    return parsed


def generate_qr_code_base64(url):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#090d16', back_color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f'data:image/png;base64,{img_str}'
