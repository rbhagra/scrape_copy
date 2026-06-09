import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

from web.api.jurisdictions import jurisdictions_bp
from web.api.bills import bills_bp
from web.api.scrapes import scrapes_bp
from web.api.db import init_app
from apscheduler.schedulers.background import BackgroundScheduler
from web.file_cleanup import file_cleanup

load_dotenv()

app = Flask(__name__)
CORS(app)
init_app(app)

app.config['DB_HOST'] = os.getenv('host_name')
app.config['DB_USER'] = os.getenv('user_name')
app.config['DB_PASSWORD'] = os.getenv('password')
app.config['DB_NAME'] = os.getenv('database_name')

app.register_blueprint(jurisdictions_bp, url_prefix='/api')
app.register_blueprint(bills_bp, url_prefix='/api')
app.register_blueprint(scrapes_bp, url_prefix='/api')

#file cleanup scheduling
scheduler = BackgroundScheduler()
scheduler.add_job(func=file_cleanup, trigger='interval', hours=12)
scheduler.start()


@app.route('/api/health')
def health():
    return {'status': 'ok'}


if __name__ == '__main__':
    backend_port = int(os.getenv('app_port', '5001'))
    app.run(debug=True, port=backend_port)
