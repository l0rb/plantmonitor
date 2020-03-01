import os

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

def conf(key, default=None):
    value = os.getenv(key)
    return value if value is not None else default

def nodeurl(id_, schema='http'):
    url6 = conf(f'NODE{id_}')
    port = conf(f'NODE{id_}_PORT', 8080)
    return f'{schema}://[{url6}]:{port}'
