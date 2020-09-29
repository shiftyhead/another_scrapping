import json
import http.client
import csv

from matching import MATCHING
MIN_S = 0
MAX_S = 2000000
MIN_PRICE = 0
MAX_PRICE = 25000000
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


if __name__ == '__main__':
    # rooms = ''.join([f'&room%5B%5D={room}' for room in range(ROOM_COUNT)])
    #
    # conn = http.client.HTTPSConnection("loftfm.mrloft.ru")
    # payload = f'min_s={MIN_S}&max_s={MAX_S}&min_price={MIN_PRICE}&max_price={MAX_PRICE}{rooms}'
    # conn.request("POST", "/getflatdatasearchLoftfm", payload, HEADERS)
    # res = conn.getresponse()
    # data = res.read()
    # data = data.decode("utf-8")
    # json_data = json.loads(data)
    # with open('response.json', 'w', encoding='utf-8') as f:
    #     json.dump(json_data, f)
    with open('response.json', encoding='utf-8') as f:
        data = json.load(f)

    with open('fields_desc.csv', encoding='utf-8-sig') as f:
        reader = csv.reader(f, dialect='excel', delimiter=';')
        fields = [row[0] for row in reader]
    result = []
    for record in data.get('data'):
        obj = {}
        for field in fields:
            site_field = MATCHING.get(field)
            value = record.get(site_field)
            obj[field] = value
        result.append(obj)

    print(result)

