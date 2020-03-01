import json
from datetime import datetime

import plotly
import requests
from flask import Flask, session, g, redirect, url_for, render_template
from flask_migrate import Migrate
from flask_debugtoolbar import DebugToolbarExtension
from bind import bind

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
        data = requests.get(nodeurl(1))
        moisture = data.json()['relative'] * 100
        return render_template('base.html', moisture=moisture)

    @app.route('/graph/<int:plant_id>')
    def graph(plant_id):
        data = Point.query.filter_by(plant_id=plant_id).order_by(Point.time).all()
        chart = [{
            'x': [point.time for point in data],
            'y': [point.value for point in data],
            'type': 'scatter'
        }]
        chart = json.dumps(chart, cls=plotly.utils.PlotlyJSONEncoder)
        return render_template('graph.html', chart=chart)

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
        try:
            data_response = requests.get(bind([nodeurl(node_id),'data'], safe='/:[]'))
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
            point['time'] = datetime.fromisoformat(point['time'])
            model = Point(**fields, plant_id=plant.id, type_id=type_.id, value=point['value'], time=point['time'])
            db.session.add(model)
            counter += 1
        db.session.commit()
        return f'{counter} datapoints added'
    
    return app


application = create_app()
