"""
Парсер цен с сайта nk.ilike.ru.
Использует данные из API flatmodels, затем приводит их к формату FIELDS с необходимыми преобразованиями.
Выводит данные в формате JSON  в поток вывода
"""
import json
import http.client
import logging
import sys
from json import JSONDecodeError

from bs4 import BeautifulSoup

FIELDS = ['complex', 'type', 'phase', 'building', 'section', 'price', 'price_base', 'price_finished', 'price_sale',
          'price_finished_sale', 'area', 'living_area', 'number', 'number_on_site', 'rooms', 'floor', 'in_sale',
          'sale_status', 'finished', 'currency', 'ceil', 'article', 'finishing_name', 'furniture', 'furniture_price',
          'plan', 'feature', 'view', 'euro_planning', 'sale', 'discount_percent', 'discount', 'comment']
MATCHING = {
    'type': {
        'name': 'type',
        'calc': lambda x: 'flat' if x in ['Квартира', 'Студия', 'Аппартаменты'] else 'commercial'
    },
    'area': {
        'name': 'space',
        'calc': lambda x: float(x) if x else None
    },
    'building': {
        'name': 'house',
        'calc': lambda x: int(x) if x else None
    },
    'euro_planning': {
        'name': 'isEuro',
        'calc': lambda x: int(x) if x else None
    },
    'section': {
        'name': 'section',
        'calc': lambda x: int(x) if x else None
    },
    'price_base': {
        'name': 'price',
        'calc': lambda x: float(x) if x else None
    },
    'number': {
        'name': 'flat_numer',
        'calc': lambda x: str(x) if x else None
    },
    'rooms': {
        'name': 'room_count',
        'calc': lambda x: int(x) if x else None
    },
    'floor': {
        'name': 'floor',
        'calc': lambda x: int(x) if x else None
    },
    'in_sale': {
        'name': 'flat_numer',
        'calc': lambda x: 1 if x else 0
    },
    'sale_status': {
        'name': 'reserved',
        'calc': lambda x: 'Забронировано' if x else 'Продается'
    },
    'finished': {
        'name': 'decor',
        'calc': lambda x: 0 if x == -1 else 1
    },
    'finishing_name': {
        'name': 'decor',
        'calc': lambda x: {x == -1: None, x == 1: 'Черновая', x == 3: 'Классика', x == 4: 'Модерн'}[True]
    },
    'furniture': {
        'name': 'furniture',
        'calc': lambda x: 1 if x else None
    },
    'furniture_price': {
        'name': 'furniture',
        'calc': lambda x: max([i['price'] for i in x]) if x else None
    },
    'article': {
        'name': 'uid',
        'calc': lambda x: str(x) if x else None
    },
}


def cast_fields(record: dict, fields: list, matching: dict):
    """
    Для каждого поля из fields определяет значение на основе матчинга полей и преобразований типов
    :param record: Данные из API
    :param fields: Поля, к которым нужно привести каждую запись
    :param matching: Данные для матчинга полей и преобразования
    :return:
    """
    obj = {}
    # Для каждого поля определяем значение на основе матчинга полей и преобразований типов
    for field in fields:
        matching_params = matching.get(field, {})
        site_field = matching_params.get('name')
        value = record.get(site_field)
        calc = matching_params.get('calc')
        if calc:
            value = calc(value)
        obj[field] = value
    return obj


def get_html(address, endpoint, method, payload):
    if 'https://' in address:
        address = address.replace('https://', '')
    if address[-1] == '/':
        address = address[:-1]
    conn = http.client.HTTPSConnection(address)
    conn.request(method, endpoint, payload)
    res = conn.getresponse()
    data = res.read()
    return data.decode("utf-8")


def get_subdomains():
    data = get_html('ilike.ru', '/#complexes', 'GET', '')

    soup = BeautifulSoup(data, 'html.parser')
    complexes = soup.findAll("li", {"class": "complexes__item"})
    complex_links = {f'{complex.a.figure.figcaption.h3.text} ({str(complex.a.figure.figcaption.p.text).strip()})': complex.a.attrs['href']
                     for complex in complexes}
    return complex_links


def process_data(complex_name, complex_url, endpoint):
    try:
        data = get_html(complex_url, endpoint, 'GET', '')
    except Exception as e:
        raise MyException(f'Сетевая ошибка, вероятно API {endpoint} не реализовано', e)
    try:
        json_data = json.loads(data)
    except JSONDecodeError as e:
        raise MyException(f'JSON не получен, вероятно API {endpoint} не реализовано', e)
    # with open('response.json', 'w', encoding='utf-8') as f:
    #     json.dump(json_data, f)
    # with open('response.json', encoding='utf-8') as f:
    #     json_data = json.load(f)
    json_data = [x for x in json_data if not x['reserved'] and 1000000 < x['price'] < 10000000 and 19 < x['space'] < 96]
    result = []
    for record in json_data:
        if record['reserved']:
            continue
        # Получаем основные поля из матчинга
        obj = cast_fields(record, FIELDS, MATCHING)

        if obj['finished']:
            obj['price_finished'] = obj['price_base']
            obj['price_base'] = None
        else:
            obj['finishing_name'] = None
        obj['complex'] = complex_name
        # Ссылка на план
        obj['plan'] = f'{complex_url}api/pdf?' \
                      f'flatNumber={record["flat_numer"]}&' \
                      f'cost={record["price"]}&' \
                      f'space={record["space"]}&' \
                      f'section={record["section"]}&' \
                      f'floor={record["floor"]}&' \
                      f'decor={record["decor"]}&' \
                      f'room_count={record["room_count"]}&' \
                      f'house={record["house"]}'
        result.append(obj)

    return result


class MyException(Exception):
    def __init__(self, msg, err):
        self.msg = msg
        self.err = err


def main():
    logger = logging.getLogger('ilike')
    complex_links = get_subdomains()
    result = []
    endpoint = '/api/flatmodels/getAllFlatData'
    for complex_name, complex_url in complex_links.items():
        try:
            result.extend(process_data(complex_name, complex_url, endpoint))
        except MyException as e:
            pass
            # logger.error(f'Ошибка при парсинге {complex_url + endpoint}: {e.msg}, подробнее: {e.err}')
    output = json.dumps(result, ensure_ascii=False)
    # Выводим данные в поток
    sys.stdout.write(output)


if __name__ == '__main__':
    main()
