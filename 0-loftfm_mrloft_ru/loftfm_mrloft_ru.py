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

HEADERS = {
    'authority': 'loftfm.mrloft.ru',
    'accept': '*/*',
    'x-requested-with': 'XMLHttpRequest',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/85.0.4183.121 Safari/537.36',
    'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'origin': 'https://loftfm.mrloft.ru',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-mode': 'cors',
    'sec-fetch-dest': 'empty',
    'referer': 'https://loftfm.mrloft.ru/',
    'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
}
FIELDS = ['complex', 'type', 'phase', 'building', 'section', 'price', 'price_base', 'price_finished', 'price_sale',
          'price_finished_sale', 'area', 'living_area', 'number', 'number_on_site', 'rooms', 'floor', 'in_sale',
          'sale_status', 'finished', 'currency', 'ceil', 'article', 'finishing_name', 'furniture', 'furniture_price',
          'plan', 'feature', 'view', 'euro_planning', 'sale', 'discount_percent', 'discount', 'comment']
MATCHING = {
    'area': {
        'name': 's',
        'calc': lambda x: float(x) if x else None
    },
    'living_area': {
        'name': 's_living',
        'calc': lambda x: float(x) if x else None
    },
    'complex': {
        'calc': lambda x: 'LOFT FM (Москва)'
    },
    'price_base': {
        'name': 'priceToSort',
        'calc': lambda x: float(x) if x else None
    },
    'number': {
        'name': 'number',
        'calc': lambda x: str(x) if x else None
    },
    'rooms': {
        'name': 'rooms',
        'calc': lambda x: int(x) if x else None
    },
    'floor': {
        'name': 'floor',
        'calc': lambda x: int(x) if x else None
    },
    'in_sale': {
        'name': 'sold',
        'calc': lambda x: 0 if x else 1
    },
    'plan': {
        'name': 'first_plan_url',
        'calc': lambda x: str(x[0][0]) if x else None
    },
    'sale': {
        'name': 'special_text',
        'calc': lambda x: str(x) if x else None
    },
    'finished': {
        'calc': lambda x: 0
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
    conn = http.client.HTTPSConnection("loftfm.mrloft.ru")
    payload = f'min_s={MIN_S}&max_s={MAX_S}&min_price={MIN_PRICE}&max_price={MAX_PRICE}{rooms}'
    conn.request("POST", "/getflatdatasearchLoftfm", payload, HEADERS)
    res = conn.getresponse()
    data = res.read()
    data = data.decode("utf-8")
    json_data = json.loads(data)
    result = []
    for record in json_data.get('data'):
        # Получаем основные поля из матчинга
        obj = cast_fields(record, FIELDS, MATCHING)

        # Отдельно читаем информацию о скидках и отделках из акций
        check_sales_and_finishing(obj)

        # Аккумулируем значение статуса из полей "Продано" и "Забронировано"
        if not obj['in_sale']:
            obj['sale_status'] = 'Продано'
        elif record['reserved']:
            obj['sale_status'] = 'Забронировано'
        else:
            obj['sale_status'] = 'Продается'

        # Аккумулируем значение типа, тут это облако тегов. Если помещение нежилое - считаем его коммерческим
        obj_type = [r['name'] for r in record['type']]
        if 'Апартаменты' in obj_type:
            obj['type'] = 'apartment'
        else:
            obj['type'] = 'commercial'
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
