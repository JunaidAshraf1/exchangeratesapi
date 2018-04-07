from __future__ import division

import datetime
from decimal import ROUND_HALF_UP, Decimal

import falcon
import ujson
from peewee import fn

from exchangerates.models import ExchangeRates, db


class PeeweeConnectionMiddleware(object):
    def process_request(self, req, resp):
        db.connect()

    def process_response(self, req, resp, resource):
        if not db.is_closed():
           db.close()


class CORSMiddleware(object):
    def process_response(self, req, resp, resource, req_succeeded):
        resp.set_header('Access-Control-Allow-Origin', '*')

        if (req_succeeded
            and req.method == 'OPTIONS'
            and req.get_header('Access-Control-Request-Method')
        ):

            allow = resp.get_header('Allow')
            resp.delete_header('Allow')

            allow_headers = req.get_header(
                'Access-Control-Request-Headers',
                default='*'
            )

            resp.set_headers((
                ('Access-Control-Allow-Methods', allow),
                ('Access-Control-Allow-Headers', allow_headers),
                ('Access-Control-Max-Age', '86400'),  # 24 hours
            ))


class ExchangeRateResource(object):
    def on_get(self, request, response, date=None):
        if not date:
            date = datetime.date.today()

        subquery = ExchangeRates.filter(ExchangeRates.date <= date).\
            select(fn.MAX(ExchangeRates.date))

        exchangerates = ExchangeRates.\
            select(ExchangeRates.currency, ExchangeRates.rate).\
            filter(ExchangeRates.date == subquery).\
            order_by(ExchangeRates.currency)

        # Symbols
        if 'symbols' in request.params:
            exchangerates = exchangerates.\
                where(ExchangeRates.currency << request.params['symbols'])
        
        # Base
        base = 'EUR'
        rates = {er['currency']:er['rate'] for er in exchangerates.dicts()}
        if 'base' in request.params:
            base = request.params['base']
            # TODO: For better performance this can probably be done within Postgres already
            rates = {currency:(rate / rates[base]).quantize(Decimal('0.0001'), ROUND_HALF_UP) for currency, rate in rates.iteritems()}
            del rates[base]

        response.body = ujson.dumps({
            'base': base,
            'date': date.strftime('%Y-%m-%d'),
            'rates': rates
        })


exchangerates = ExchangeRateResource()

app = falcon.API(middleware=[
    PeeweeConnectionMiddleware(),
    CORSMiddleware(),
])
app.add_route('/api/latest/', exchangerates)
app.add_route('/api/{date:dt("%Y-%m-%d")}/', exchangerates)
