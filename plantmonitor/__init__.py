import json
from datetime import datetime, timedelta

import plotly
import requests
from flask import Flask, session, g, redirect, url_for, render_template
from flask_migrate import Migrate
from flask_debugtoolbar import DebugToolbarExtension
from bind import bind
from sqlalchemy import and_, desc

from config import conf, nodeurl
from .db import db, Plant, MMType, Point


def create_app():
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=conf('FLASK_SECRET'),
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{conf("DB_SQLITE")}',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    db.init_app(app)
    toolbar = DebugToolbarExtension(app)
    migrate = Migrate(app, db)

    @app.route('/')
    def main():
        plants = Plant.query.all()
        return render_template('landing.html', plants=plants)

    @app.route('/graph/<int:plant_id>')
    @app.route('/graph/<int:plant_id>/<int:type_id>')
    def graph(plant_id, type_id=1):
        plant = Plant.query.get(plant_id)
        type_ = MMType.query.get(type_id)
        moisture_list = requests.get(nodeurl(plant.node_id)).json()
        moisture = -1
        for m in moisture_list:
            if m['plant_id']==plant_id:
                moisture = m['relative'] * 100
                break
        indicator = [{
            'domain': { 'x': [0, 1], 'y': [0, 1] },
            'value': moisture,
            'title': { 'text': 'aktueller Wert' },
            'type': "indicator",
            'mode': "gauge+number",
            #'delta': { 'reference': 100 },
            'gauge': { 'axis': { 'range': [None, 100] } },
            'number': { 'suffix': "%" }
        }]
        indicator = json.dumps(indicator, cls=plotly.utils.PlotlyJSONEncoder)
        data = Point.query.filter_by(plant_id=plant_id).order_by(Point.time).all()
        chart = [
            {
                'x': [point.time for point in data if point.type_id==type_id],
                'y': [point.value for point in data if point.type_id==type_id],
                'name': type_.name,
                'yaxis': 'y1',
                'type': 'scatter'
            },
            {
                'x': [point.time for point in data if point.type_id==2],
                'y': [point.value for point in data if point.type_id==2],
                'name': 'Temperatur',
                'yaxis': 'y2',
                'type': 'scatter'
            },
            {
                'x': [point.time for point in data if point.type_id==3],
                'y': [point.value/100 for point in data if point.type_id==3],
                'name': 'Luftfeucht.',
                'yaxis': 'y1',
                'type': 'scatter'
            },
        ]
        chart = json.dumps(chart, cls=plotly.utils.PlotlyJSONEncoder)
        return render_template('graph.html', chart=chart, plant=plant, type=type_, indicator=indicator)

    @app.route('/getmeta/<int:node_id>')
    def meta(node_id):
        def create_if_not_exist(entity_list, node_id, ModelClass):
            for entity in entity_list:
                fields = {
                    'node_id': node_id,
                    'node_entity_id': entity['id']
                }
                model = db.session.query(ModelClass).filter_by(**fields).first()
                if not model:
                    model = ModelClass(**fields, name=entity['name'])
                    db.session.add(model)
        try:
            meta_response = requests.get(bind([nodeurl(node_id),'meta'], safe='/:[]'))
        except requests.exceptions.ConnectionError:
            return 'ConnectionError when requesting node. Maybe node_id is wrong?'
        meta_data = meta_response.json()
        create_if_not_exist(meta_data['plants'], node_id, Plant)
        create_if_not_exist(meta_data['types'], node_id, MMType)
        db.session.commit()
        return str(meta_data)
        #meta = fetch_meta()
        #store_meta(meta)

    @app.route('/fetch/<int:node_id>')
    def fetch(node_id):
        two_hour_ago = datetime.now() - timedelta(minutes=120) # there are still some timezone issues between the nodes and the monitor server
        checkpoint = Point.query.filter(and_(Point.time >= two_hour_ago, Point.node_id==node_id)).first()
        if checkpoint:
            return f'Last point is not old enough to allow fetch: {datetime.now() - checkpoint.time}'
        latest = Point.query.order_by(desc('time')).first()
        start = str(int(latest.time.timestamp() - 12*3600)) # add 12 hours of overlap when fetching data
        try:
            data_response = requests.get(bind([nodeurl(node_id),'data'], safe='/:[]'), params={'start':start})
        except requests.exceptions.ConnectionError:
            return 'ConnectionError when requesting node. Maybe node_id is wrong?'
        data = data_response.json()
        counter = 0
        for point in data:
            fields = {
                'node_id': node_id,
                'node_entity_id': point['id']
            }
            if db.session.query(Point).filter_by(**fields).first():
                continue
            plant = Plant.query.filter_by(node_id=node_id, node_entity_id=point['plant']).first()
            type_ = MMType.query.filter_by(node_id=node_id, node_entity_id=point['type']).first()
            # todo: if type unknow, do one fetch-meta
            point['time'] = datetime.fromisoformat(point['time'])
            model = Point(**fields, plant_id=plant.id, type_id=type_.id, value=point['value'], time=point['time'])
            db.session.add(model)
            counter += 1
        db.session.commit()
        return f'{counter} datapoints added'

    return app


application = create_app()
