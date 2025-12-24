from datetime import date, datetime


def parse_date_ddmmyyyy(date_str):
    if not date_str:
        return None
    date_str = date_str.strip()
    try:
        if '.' in date_str:
            return datetime.strptime(date_str, '%d.%m.%Y').date()
        elif '-' in date_str:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return None
    return None


def format_name_short(lname, fname, tname=None):
    result = lname or ''
    if fname:
        result += f' {fname[0].upper()}.'
    if tname:
        result += f' {tname[0].upper()}.'
    return result.strip()
