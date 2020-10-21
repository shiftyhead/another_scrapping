import sys

import requests
import json
import urllib3
import decimal
import re
import copy

from html import unescape
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin, urlparse
from decimal import Decimal


class EstateObject():

    possible_types = ['flat', 'apartment', 'parking', 'commercial',
                      'storeroom', 'townhouse']

    empty_values = ['null', '-', '0']

    def __init__(self):
        self.complex = None
        self.type = None
        self.building = None
        self.section = None
        self.price = None
        self.price_base = 0
        self.area = None
        self.number = None
        self.number_on_site = None
        self.rooms = None
        self.floor = None
        self.in_sale = 1
        self.finished = 0

        self.sale_status = None
        self.living_area = None
        self.ceil = None
        self.article = None
        self.finishing_name = None
        self.price_sale = None
        self.price_finished = None
        self.price_finished_sale = None
        self.furniture_price = None
        self.furniture = 0
        self.plan = None
        self.feature = None
        self.view = None
        self.euro_planning = 0
        self.sale = None
        self.discount_percent = None
        self.discount = None

    @staticmethod
    def remove_restricted(value, restricted):
        if isinstance(value, str):
            value = value.strip()
            for part in restricted:
                value = re.sub(part, '', value, flags=re.I).strip()
        return value

    @staticmethod
    def correct_decimal_delimeter(value):
        if isinstance(value, str):
            return value.replace(',', '.')
        return value

    def set_complex(self, value):
        restricted_parts = ['\t', '\n']
        value = self.remove_restricted(value, restricted_parts)
        value = value.title().replace('Жк', 'ЖК')
        self.complex = value

    def set_obj_type(self, value):
        value = value.lower()
        if 'квартира' in value:
            self.type = 'flat'
        elif 'апаратамен' in value or 'апартамент' in value:
            self.type = 'apartment'
        elif 'сьюты' in value:
            return self.apartment
        elif 'кладов' in value:
            self.type = 'storeroom'
        elif 'нежилое помещение' in value:
            self.type = 'commercial'
        elif 'коммерческое' in value:
            self.type = 'commercial'
        elif 'офис' in value:
            self.type = 'commercial'
        elif 'машиноместо' in value or 'гараж' in value:
            self.type = 'parking'
        elif 'парк' in value:
            self.type = 'parking'
        elif 'место для мотоцикла' in value:
            self.type = 'parking'
        elif 'таунхаус' in value:
            self.type = 'townhouse'
        else:
            self.type = value

    def set_building(self, value):
        restricted_parts = ['корпус', 'корп.', 'корп', 'строение',
                            '№', 'дом', ':',
                            '\t', '\n', 'квартал']
        value = self.remove_restricted(value, restricted_parts)
        self.building = value

    def set_section(self, value):
        restricted_parts = ['секция', 'парадная', '№', ':', '\t', 'подъезд', 'блок']
        value = self.remove_restricted(value, restricted_parts)
        if not value or value == '-' or value == '–':
            return
        self.section = value

    def _decode_price(self, value, multi=1):
        if isinstance(value, str):
            if 'запрос' in value.lower() or 'прода' in value.lower():
                return
        restricted_parts = ['cтоимость', 'стоимость', 'рублей', 'цена базовая',
                            'руб.', 'руб', 'цена', 'выгода до', 'выгода', 'млн.',
                            'млн', 'от', '₽', 'р.',
                            'р', ' ', ' ', ':', '’', 'p', r'\s']
        value = self.correct_decimal_delimeter(value)
        value = self.remove_restricted(value, restricted_parts)
        if value:
            return round(Decimal(value) * multi, 0)

    def _check_price_value(self, price):
        if price:
            if (price > 0 and price < 10000) or \
                    price > 1000000 * 100000:
                raise Exception('Wrong price value')

    def set_price_base(self, value, sale=None, multi=1):
        self.price_base = self._decode_price(value, multi)
        if sale:
            price_sale = self._decode_price(sale, multi)
            if price_sale:
                if price_sale < self.price_base:
                    self.price_sale = price_sale
                elif price_sale > self.price_base:
                    raise Exception('wrong price order')
        self._check_price_value(self.price_base)

    def _area_cleaner(self, value) -> Decimal:
        # restricted_parts = ['общая', 'площадь', 'м²', 'м2', 'кв.м.', 'кв.м',
        #                     'м', 'жилая', '\t', '\n', ' ']
        value = self.correct_decimal_delimeter(value)
        if isinstance(value, str):
            value = re.findall(r'[+-]?[0-9]*[.]?[0-9]+', value)[0]
        # value = self.remove_restricted(value, restricted_parts)
        return Decimal(value)

    def set_area(self, value):
        if value:
            self.area = self._area_cleaner(value)

    def set_number(self, value):
        restricted_parts = ['офис', 'квартира', '№', 'машиноместо', 'кладовая',
                            'нежилое помещение', 'коммерческое помещение',
                            'паркинг', 'кладовка', 'номер', 'лот', 'помещение',
                            'ком.пом.', 'пом.']
        value = self.remove_restricted(value, restricted_parts)
        self.number = value

    def set_number_on_site(self, value):
        restricted_parts = ['офис', 'квартира', '№', 'машиноместо', 'кладовая',
                            'нежилое помещение', 'коммерческое помещение',
                            'паркинг', 'кладовка', 'номер', 'лот']
        value = self.remove_restricted(value, restricted_parts)
        self.number_on_site = value

    def set_rooms(self, value, check_euro=True, check_type=True):
        if isinstance(value, str):
            value = value.lower().strip()
            value = value.replace('комнаты', '').replace('комната', '').strip()
            if check_euro and 'евро' in value:
                self.euro_planning = 1
            if check_type and 'апартамент' in value:
                self.set_obj_type('apartment')
            if 'одно' in value or '1-а' in value:
                self.rooms = 1
            elif 'двух' in value or '2-х' in value or 'двушка' in value:
                self.rooms = 2
            elif 'трех' in value or 'трёх' in value or '3-х' in value\
                    or 'трешка' in value or 'трёшка' in value:
                self.rooms = 3
            elif 'четырех' in value or 'четырёх' in value or\
                    '4-х' in value:
                self.rooms = 4
            elif 'пяти' in value:
                self.rooms = 5
            elif 'шести' in value:
                self.rooms = 6
            elif 'семи' in value:
                self.rooms = 7
            else:
                if 'студия' in value or 'студ' in value or\
                        'studio' in value or value == 'с'\
                        or value == 'c' or value == 's'\
                        or value == 'ст' or 'cтудия' in value:
                    self.rooms = 'studio'
                else:
                    if check_euro and 'e' in value or 'е' in value and len(value) < 4:
                        self.euro_planning = 1
                    value = re.findall(r'\d+', value)[0]
                    self.rooms = int(value)
        else:
            self.rooms = int(value)
        if self.rooms == 0:
            self.rooms = 'studio'

    def set_floor(self, value):
        if value:
            if isinstance(value, str):
                if 'цоколь' in value:
                    self.floor = -1
                    return
                if 'из' in value:
                    value = value.split('из')[0]
                if '/' in value:
                    value = value.split('/')[0]
                value = re.findall(r'-?\d+', value)[0]
            self.floor = int(value)

    def set_in_sale(self, value=1):
        if isinstance(value, str):
            if 'брон' in value.lower():
                self.set_sale_status('Забронирована')
                value = 1
            elif 'зарезерв' in value.lower():
                self.set_sale_status('Зарезервирована')
                value = 1
            elif 'вторичная продажа' in value.lower():
                self.set_sale_status('Вторичная продажа')
                value = 1
            elif 'свобод' in value.lower():
                value = 1
            elif 'в продаже' in value.lower():
                value = 1
            elif 'продан' in value.lower():
                value = 0
        if value not in [0, 1, None]:
            raise Exception('Wrong object in_sale attribute', value)
        if value:
            value = int(value)
        self.in_sale = value

    def set_finished(self, value=0):
        if value not in [0, 1, None, 'optional']:
            raise Exception('Wrong object finished attribute', value)
        self.finished = value

    def set_currency(self, value):
        self.currency = value

    # Next go v_2.2 part

    def set_sale_status(self, value):
        restricted_parts = ['статус', ':']
        value = self.remove_restricted(value, restricted_parts)
        self.sale_status = value

    def set_living_area(self, value):
        if value:
            if not isinstance(value, str) or value.lower().strip() not in self.empty_values:
                self.living_area = self._area_cleaner(value)

    def set_ceil(self, value):
        restricted_parts = ['высота', 'потолков', 'потолки', 'потолок',
                            ':', 'м.', 'м']
        value = self.correct_decimal_delimeter(value)
        value = self.remove_restricted(value, restricted_parts)
        self.ceil = Decimal(value)

    def set_article(self, value):
        restricted_parts = ['№', 'артикул:', 'тип планировки', 'тип']
        value = self.remove_restricted(value, restricted_parts)
        self.article = value

    def set_finishing_name(self, value):
        restricted_parts = []
        not_finished = ['без отделки', 'без ремонта', '–']
        value = self.remove_restricted(value, restricted_parts)
        for finish in not_finished:
            if finish in value.lower():
                return
        self.set_finished(1)
        self.finishing_name = value

    def set_price_sale(self, value, multi=1):
        price_sale = self._decode_price(value, multi)
        if self.price_base and price_sale >= self.price_base:
            return
        self.price_sale = price_sale
        self._check_price_value(self.price_sale)

    def set_price_finished(self, value, sale=None, multi=1):
        self.price_finished = self._decode_price(value, multi)
        self._check_price_value(self.price_finished)

    def set_price_finished_sale(self, value, sale=None, multi=1):
        self.price_finished_sale = self._decode_price(value, multi)
        self._check_price_value(self.price_finished_sale)

    def set_furniture_price(self, value, sale=None, multi=1):
        self.furniture_price = self._decode_price(value, multi)
        self._check_price_value(self.furniture_price)

    def set_furniture(self, value=0):
        if value not in [0, 1, 'optional', None]:
            raise Exception('Wrong object furniture attribute', value)
        self.furniture = value

    def set_plan(self, url, base_url=None):
        if url:
            if base_url:
                url = urljoin(base_url, url)
            self.plan = url

    def set_feature(self, value):
        if value:
            restricted_parts = ['\t', '\n']
            value = self.remove_restricted(value, restricted_parts)
            if self.feature:
                if isinstance(self.feature, str):
                    self.feature = [self.feature]
                self.feature.append(value)
            else:
                self.feature = value

    def set_view(self, value):
        if value:
            restricted_parts = ['\t', '\n']
            value = self.remove_restricted(value, restricted_parts)
            if self.view:
                self.view.append(value)
            else:
                self.view = [value]

    def set_euro_planning(self, value):
        value = int(value)
        if value not in [0, 1, None]:
            raise Exception('Wrong object euro_planning attribute', value)
        self.euro_planning = value

    def set_sale(self, value):
        if self.sale:
            self.sale += '; ' + value
        else:
            self.sale = value

    def set_discount_percent(self, value):
        restricted_parts = ['скидка', '%', '-']
        value = self.correct_decimal_delimeter(value)
        value = self.remove_restricted(value, restricted_parts)
        self.discount_percent = Decimal(value)

    def set_discount(self, value):
        self.discount = self._decode_price(value)

    def set_level(self, value):
        if isinstance(value, str) and 'двухуровневая' in value.lower():
            self.set_feature('Двухуровневая')
        elif '2' in str(value):
            self.set_feature('Двухуровневая')

    def set_balcon(self, value):
        if isinstance(value, str):
            if 'балкон' in value.lower():
                self.set_feature('Балкон')
            if 'лоджия' in value.lower():
                self.set_feature('Лоджия')
            if 'да' in value.lower():
                self.set_feature('Балкон')
            if 'есть' in value.lower():
                self.set_feature('Балкон')

    def final_check(self):
        self._set_not_in_sale_if_no_price()
        self._swap_base_price_and_finish_price()
        self._validate_prices()
        if self.type not in EstateObject.possible_types:
            raise Exception('Wrong object type', self.type)

    def _set_not_in_sale_if_no_price(self):
        if not (self.price_base or self.price_sale or self.price_finished or
                self.price_finished_sale):
            self.set_in_sale(0)

    def _swap_base_price_and_finish_price(self):
        if self.finished == 1 and self.price_base and not self.price_finished:
            self.price_finished = self.price_base
            self.price_base = None

        if self.finished == 1 and self.price_sale and not self.price_finished_sale:
            self.price_finished_sale = self.price_sale
            self.price_sale = None

    def _validate_prices(self):
        if self.price_base and self.price_sale:
            if self.price_base < self.price_sale:
                raise Exception('Wrond sale price', self.price_base,
                                self.price_sale)

        if self.price_finished and self.price_finished_sale:
            if self.price_finished < self.price_finished_sale:
                raise Exception('Wrond price_finished_sale price',
                                self.price_finished,
                                self.price_finished_sale)

        if self.discount_percent and self.discount_percent > 30:
            raise Exception('Too big discount rate', self.discount_percent)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __hash__(self):
        return hash(tuple(sorted(self.__dict__.items())))

    def __repr__(self):
        return str(self.__dict__)


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)


class Utils:

    @staticmethod
    def remove_restricted(value, restricted):
        if isinstance(value, str):
            value = value.strip()
            for part in restricted:
                value = re.sub(part, '', value, flags=re.I).strip()
        return value

    @staticmethod
    def _normalize_str(string):
        return ' '.join(re.sub(r'\s', ' ', string).strip().split())

    @staticmethod
    def get_domain(url):
        return '{uri.scheme}://{uri.netloc}/'.format(uri=urlparse(url))


class TableMapper:
    # helper class
    method_by_names = [
        (('цена за 1', 'цена за кв.м', 'площадь кухни', 'datePriceIncrease', 'withPriceIncrease'), None),
        (('статус', 'available', 'statusFlat', ), 'set_in_sale'),
        (('количество комнат', 'rooms_count', 'roomsQuantity', 'кол-во комнат', 'тип квартиры',
          'число комнат', 'комнат в квартире'), 'set_rooms'),
        (('общая площадь', 'area', 'fullFlat', 'метраж', 's общ', 'totalSquare'), 'set_area'),
        (('price', 'priceFlat', ), 'set_price_base', ),
        (('housing', 'building', 'дом', 'корпус'), 'set_building'),
        (('№ кв', '№ квартиры', ), 'set_number'),
        (('номер', ), 'set_number'),
        (('section', 'секция', 'парадная'), 'set_section'),
        (('жилая площадь', 'площадь комнат', 'жилая', 's комнат', 'livingSquare'), 'set_living_area'),
        (('высота потолков', ), 'set_ceil'),
        (('этаж', 'floor', ), 'set_floor'),
        (('отделка', 'decoration', ), 'set_finishing_name'),
        (('цена', 'стоимость', ), 'set_price_base'),
        (('imgLink', 'flatPlanImageUrl'), 'set_plan'),
        (('количество уровней', ), 'set_level'),
        (('балкон', ), 'set_balcon'),
        (('терраса', ), 'set_terrace'),
        (('площадь', ), 'set_area'),
        (('вид из окон', ), 'set_view'),
    ]

    @staticmethod
    def _clean_key(key, exact_match):
        if key and isinstance(key, Tag):
            key = key.get_text(separator=" ").strip()
        key = Utils._normalize_str(key)
        restricted = [',', 'м²', 'м2', 'кв.м.', 'кв.м']
        if exact_match:
            key = Utils.remove_restricted(key, restricted)
        return key

    @staticmethod
    def _clean_value(value):
        if value and isinstance(value, Tag):
            value = value.get_text(separator=" ").strip()
        value = Utils._normalize_str(value)
        restricted = []
        value = Utils.remove_restricted(value, restricted)
        return value

    @classmethod
    def map_by_dict(cls, obj, dict_, exact_match=False):
        if dict_:
            for key, value in dict_.items():
                key = cls._clean_key(key, exact_match)
                # print(key)
                for map_keys, map_method in cls.method_by_names:
                    if cls._compare_keys(key, map_keys, exact_match):
                        # print(key, value)
                        if map_method:
                            obj.__getattribute__(map_method)(value)
                        break

    @classmethod
    def map_by_one(cls, obj, key, value, exact_match=False):
        if key and value:
            key = cls._clean_key(key, exact_match)
            value = cls._clean_value(value)
            # print(repr(key))
            for map_keys, map_method in cls.method_by_names:
                if cls._compare_keys(key, map_keys, exact_match):
                    # print(repr(key), value)
                    if map_method:
                        obj.__getattribute__(map_method)(value)
                    break

    @classmethod
    def map_by_table(cls, obj, table, exact_match=False):
        head = None
        for tr in table.find_all('tr'):
            if not head:
                head = tr.find_all('th')
                if not head:
                    # this mean table without head, each row have name
                    info = tr.find_all('td')
                    cls.map_by_one(obj, info[0].text, info[1].text, exact_match)
                continue
            info = tr.find_all('td')
            for key, value in zip(head, info):
                cls.map_by_one(obj, key.text, value.text, exact_match)

    @classmethod
    def map(cls, obj, keys, values, exact_match=False):
        if len(keys) != len(values):
            raise Exception('keys and value have different lenght', len(keys), len(values))
        for key, value in zip(keys, values):
            key = cls._clean_key(key, exact_match)
            value = cls._clean_value(value)
            # print(repr(key), value)
            for map_keys, map_method in cls.method_by_names:
                if cls._compare_keys(key, map_keys, exact_match):
                    if map_method:
                        obj.__getattribute__(map_method)(value)
                    break

    @staticmethod
    def _compare_keys(check_key, keys, exact_match):
        for key in keys:
            if exact_match:
                if key.lower() == check_key.lower():
                    return True
            else:
                if key.lower() in check_key.lower():
                    return True


# ________ utils ________________
def parse_post_data(content, use_tuple=False):
    if use_tuple:
        r = []
    else:
        r = {}
    content = content.replace('\r', '\n')
    for line in content.split('\n'):
        if line.strip():
            x = line.split(':')
            k = x[0].strip()
            v = ':'.join(x[1:]).strip()
            if use_tuple:
                r.append((k, v))
            else:
                if k in r:
                    raise Exception('{0} уже есть'.format(k))
                r[k] = v
    return r


def test_out(data, file='Setun.txt'):
      pass
#    with open(file, 'w', encoding='utf-8') as f:
#        f.write(str(data))
# ________ over ________________


urllib3.disable_warnings()
loaded_objects = []
preloaded_objects = []
session = requests.Session()

# ___________________________PARSER_UNIQUE_BODY_______________________________________

URL_BASE = 'https://etalon.pro/web-api/FlatSelectionApi/GetResidentialList'
URL_COMM = 'https://etalon.pro/web-api/FlatSelectionApi/GetCommercialList'
URL_PARK = 'https://etalon.pro/web-api/FlatSelectionApi/GetParkingList'
URL_LOGIN = 'https://etalon.pro/login/Login/'
CITIES = {
    'c2deb16a-0330-4f05-821f-1d09c93331e6': 'Санкт-Петербург',
    '0c5b2444-70a0-4932-980c-b4dc0d3f02b5': 'Москва'
}


class EstateInstance(EstateObject):

    def __init__(self):
        super().__init__()
        self.type = 'flat'


def authorization():
    post_data = parse_post_data("""
        userName: R2030320@gmail.com
        Password: 1234567
        RememberMe: true
        BackUrl: https://etalon.pro/main
        g-recaptcha-response:
    """)

    with session.post(URL_LOGIN, data=post_data, verify=False) as req:
        bs = BeautifulSoup(req.content, 'lxml')
        # test_out(bs.prettify(), 'Setun.txt')
        form = bs.select('form')
        if not form:
            raise Exception('Изменился метод аутентификации, нужна ревизия кода')
        form_url = form[0]['action']
        items = form[0].select('input')
        data = {i['name']: i['value'] for i in items}
        with session.post(form_url, data=data, verify=False) as req:
            bs = BeautifulSoup(req.content, 'lxml')
            # test_out(bs.prettify(), 'Setun.txt')


def load_data():

    authorization()
    post_data = {
        "filters": {
            "cityId": "",
            "paymentType": 1,
            "subwayDistanceType": 0,
            "priceFor": 0,
            "statuses": [0, 1],
            "idn": None,
            "finishTypes": [],
            "isFromPartner": None,
            "isNotGroundFloor": False,
            "isNotTopFloor": False,
            "isSeparateBathroom": False,
            "isTradeIn": None,
            "kitchenSquareFrom": None,
            "kitchenSquareTo": None,
            "numberFloorFrom": None,
            "numberFloorTo": None,
            "priceFrom": None,
            "priceTo": None,
            "residentalComplexBuildingIds": [],
            "roomCounts": [],
            "specialPrice": False,
            "subwayDistanceTo": None,
            "totalSquareFrom": None,
            "totalSquareTo": None,
            "yearQuarters": []
        },
        "pageSize": 20,
        "pageNumber": 1,
        "sortColumnOrder": 0,
        "sortColumnName": "priceImmediately"
    }

    headers = {
        'Content-Type': 'application/json',
    }
    for city in ['c2deb16a-0330-4f05-821f-1d09c93331e6', '0c5b2444-70a0-4932-980c-b4dc0d3f02b5']:
        post_data['filters']['cityId'] = city
        for url in [URL_BASE, URL_COMM, URL_PARK]:
            page = 0
            while True:
                page += 1
                post_data['pageNumber'] = page
                # print(page)
                with session.post(url, data=json.dumps(post_data), headers=headers, verify=False) as req:
                    # test_out(req.text, 'Setun.txt')
                    loaded = req.json()['rows']
                    if not loaded:
                        break
                    for estate in loaded:
                        save_JS_obj(extract_data(estate, CITIES.get(city), url))


def extract_data(data, city, url):
    obj = EstateInstance()
    TableMapper.map_by_dict(obj, data)
    if data['status'] == 1:
        obj.set_sale_status('Резерв')
    complex_name = data['objectFullName']

    if 'апарт' in complex_name.lower():
        obj.set_obj_type('apartment')
    if 'кладов' in complex_name.lower():
        obj.set_obj_type('storeroom')
    if 'помещен' in complex_name.lower():
        obj.set_obj_type('commercial')
    if 'паркинг' in complex_name.lower():
        obj.set_obj_type('parking')
    if 'гараж' in complex_name.lower() or url == URL_PARK:
        obj.set_obj_type('parking')
    building = re.findall(r'корпус (\d+)', complex_name, flags=re.I)
    complex_name = complex_name.split(',')[0]
    complex_name += f' ({city})'
    section = re.sub(r'[а-яА-Я,-]', '', data['sectionName']).strip()
    obj.section = section if section else None
    obj.set_complex(complex_name)
    obj.set_number(data['idn'])
    if building:
        obj.set_building(building[0])
    obj.set_price_base(data['price'])
    obj.set_price_sale(data['priceImmediately'])
    obj.set_sale('При 100% Оплате')
    if 'finish' in data:
        if data['finish'] == 1:
            obj.set_finished(1)
            obj.set_finishing_name('Чистовая')
        elif data['finish'] == 0:
            pass
        elif data['finish'] == 2:
            obj.set_finished(1)
            obj.set_finishing_name('Предчистовая')
        else:
            raise Exception('new finish type', data['finish'])
    # Фильтр по балконам неточно работает, не стал добавлять
    # obj.set_feature(feature)
    if obj.area <= 1.0 and obj.type == 'parking':
        # Ошибка в данных
        return
    return obj


def save_JS_obj(obj, extract=True):
    if obj:
        if extract:
            obj.final_check()
            loaded_objects.append(obj.__dict__)
        else:
            preloaded_objects.append(obj)


def price():
    load_data()
    output = json.dumps(loaded_objects, cls=DecimalEncoder, indent=1,
                        sort_keys=False, ensure_ascii=False)
    sys.stdout.write(output)


if __name__ == "__main__":
    price()
