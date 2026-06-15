import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret')

    MONGODB_DB   = os.environ.get('MONGODB_DB', 'taskman_db')
    _mongo_host  = os.environ.get('MONGODB_HOST', 'localhost')
    _mongo_port  = int(os.environ.get('MONGODB_PORT', 27017))

    # Jika MONGODB_HOST adalah full URI (Atlas/SRV), gunakan langsung
    if _mongo_host.startswith('mongodb'):
        MONGODB_URI = _mongo_host
    else:
        MONGODB_URI = f"mongodb://{_mongo_host}:{_mongo_port}/{MONGODB_DB}"

    MONGODB_SETTINGS = {
        'db': MONGODB_DB,
        'host': MONGODB_URI,
        'connect': False,
        'serverSelectionTimeoutMS': 5000
    }

    JWT_EXPIRES_MINUTES = int(os.environ.get('JWT_EXPIRES_MINUTES', 60))