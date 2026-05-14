from flask import Blueprint, jsonify, request
from web.api.db import get_db

bills_bp = Blueprint('bills', __name__)


@bills_bp.route('/bills')
def list_bills():
    db = get_db()
    if not db:
        return jsonify({'error': 'Database connection failed'}), 500
    
    jurisdiction = request.args.get('jurisdiction')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 100)
    offset = (page - 1) * per_page
    
    cursor = db.cursor(dictionary=True)
    
    if jurisdiction:
        count_query = '''
            SELECT COUNT(*) as total
            FROM leg_processed p
            JOIN leg_html h ON p.raw_doc_id = h.search_id
            WHERE h.domain = %s
        '''
        cursor.execute(count_query, (jurisdiction,))
        total = cursor.fetchone()['total']
        
        query = '''
            SELECT p.id, p.source_url, p.search_term,
                   SUBSTRING(p.clean_text, 1, 500) as excerpt,
                   h.domain, h.created_at
            FROM leg_processed p
            JOIN leg_html h ON p.raw_doc_id = h.search_id
            WHERE h.domain = %s
            ORDER BY h.created_at DESC
            LIMIT %s OFFSET %s
        '''
        cursor.execute(query, (jurisdiction, per_page, offset))
    else:
        count_query = '''
            SELECT COUNT(*) as total
            FROM leg_processed p
            JOIN leg_html h ON p.raw_doc_id = h.search_id
        '''
        cursor.execute(count_query)
        total = cursor.fetchone()['total']
        
        query = '''
            SELECT p.id, p.source_url, p.search_term,
                   SUBSTRING(p.clean_text, 1, 500) as excerpt,
                   h.domain, h.created_at
            FROM leg_processed p
            JOIN leg_html h ON p.raw_doc_id = h.search_id
            ORDER BY h.created_at DESC
            LIMIT %s OFFSET %s
        '''
        cursor.execute(query, (per_page, offset))
    
    rows = cursor.fetchall()
    cursor.close()
    
    for row in rows:
        if row.get('created_at'):
            row['created_at'] = row['created_at'].isoformat()
    
    return jsonify({
        'bills': rows,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page
    })


@bills_bp.route('/bills/<int:bill_id>')
def get_bill(bill_id):
    db = get_db()
    if not db:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = db.cursor(dictionary=True)
    query = '''
        SELECT p.id, p.source_url, p.clean_text, p.search_term,
               p.text_processing_method,
               h.domain, h.created_at
        FROM leg_processed p
        JOIN leg_html h ON p.raw_doc_id = h.search_id
        WHERE p.id = %s
    '''
    cursor.execute(query, (bill_id,))
    row = cursor.fetchone()
    cursor.close()
    
    if not row:
        return jsonify({'error': 'Bill not found'}), 404
    
    if row.get('created_at'):
        row['created_at'] = row['created_at'].isoformat()
    
    return jsonify(row)
