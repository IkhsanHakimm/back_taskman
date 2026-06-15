from flask import jsonify


def index():
    return jsonify({'message': 'Hello, Flask project scaffold'})
