from flask import Blueprint
from controllers.home import index

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def root():
    return index()
