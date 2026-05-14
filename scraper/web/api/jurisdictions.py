from flask import Blueprint, jsonify
from web.api.db import get_db

jurisdictions_bp = Blueprint('jurisdictions', __name__)


@jurisdictions_bp.route('/jurisdictions')
def list_jurisdictions():
    db = get_db()
    if not db:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT DISTINCT domain FROM leg_processed WHERE domain IS NOT NULL ORDER BY domain')
    rows = cursor.fetchall()
    cursor.close()
    
    jurisdictions = [row['domain'] for row in rows]
    return jsonify(jurisdictions)
