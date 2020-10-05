"""
Парсер цен с сайта loftfm.mrloft.ru.
Использует данные из API getflatdatasearchLoftfm, затем приводит их к формату FIELDS с необходимыми преобразованиями.
Выводит данные в формате JSON  в поток вывода
"""
import argparse
import json
import http.client
import re
import sys

MIN_S = 0
MAX_S = 200000000000
MIN_PRICE = 0
MAX_PRICE = 25000000000000000
ROOM_COUNT = 10

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
    'complex': {
        'calc': lambda x: 'Новокрасково (Москва)'
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
        'calc': lambda x: {x == -1: 'Без отделки', x == 1: 'Черновая', x == 3: 'Классика', x == 4: 'Модерн'}[True]
    },
    'furniture': {
        'name': 'furniture',
        'calc': lambda x: x if x else None
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


def check_sales_and_finishing(obj):
    """
    Преобразовывает объект напрямую, ничего не возвращает, это просто вынесенный в функцию кусок кода
    :param obj: Объект, который нужно преобразовать
    :return:
    """
    sale = obj.get('sale')
    if sale and isinstance(sale, str):
        rub = sale.find('Цена указана с учетом скидки')
        if rub >= 0:
            pattern = re.compile(r'\d')
            discount = float(''.join(pattern.findall(sale)))
            obj['discount'] = discount
            obj['price_sale'] = obj['price_base']
            obj['price_base'] = None
        finishing = sale.find(' отделка в подарок')
        if finishing >= 0:
            pattern = re.compile(r'\w+ отделка')
            finishing_name = ''.join(pattern.findall(sale)).replace(' отделка', '')
            obj['finishing_name'] = finishing_name
            obj['finished'] = 1
            # Если есть акция на ремонт - цена уже как бы со скидкой
            obj['price_finished_sale'] = obj['price_base']
            obj['price_base'] = None
            if obj.get('price_sale'):
                obj['price_finished_sale'] = obj['price_sale']
                obj['price_sale'] = None


def main(room_filter=ROOM_COUNT):
    rooms = ''.join([f'&room%5B%5D={room}' for room in range(room_filter)])
    conn = http.client.HTTPSConnection("nk.ilike.ru")
    payload = ''
    conn.request("GET", "/api/flatmodels", payload)
    res = conn.getresponse()
    data = res.read()
    data = data.decode("utf-8")
    json_data = json.loads(data)
    with open('response.json', 'w', encoding='utf-8') as f:
        json.dump(json_data, f)
    # with open('response.json', encoding='utf-8') as f:
    #     json_data = json.load(f)
    result = []
    for house in json_data:
        for record in house.get('data'):
            # Получаем основные поля из матчинга
            obj = cast_fields(record, FIELDS, MATCHING)

            if obj['finished']:
                obj['price_finished'] = obj['price_base']
                obj['price_base'] = None

            # Ссылка на план
            obj['plan'] = f'https://nk.ilike.ru/api/pdf?' \
                          f'flatNumber={record["flat_numer"]}&' \
                          f'uid={record["uid"]}&' \
                          f'cost={record["price"]}&' \
                          f'space={record["space"]}&' \
                          f'section={record["section"]}&' \
                          f'floor={record["floor"]}&' \
                          f'decor={record["decor"]}&' \
                          f'room_count={record["room_count"]}&' \
                          f'house={house["name"]}'
            result.append(obj)

    output = json.dumps(result, ensure_ascii=False)
    # Выводим данные в поток
    sys.stdout.write(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--rooms", type=int, nargs='?',
                        const=10, default=False,
                        help="Rooms filter.")

    args = parser.parse_args()
    rooms_param = ROOM_COUNT if not args.rooms else args.rooms + 1
    main(room_filter=rooms_param)
