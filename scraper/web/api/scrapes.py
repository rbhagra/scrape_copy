import os
import json
import uuid
import time
from flask import Blueprint, jsonify, request, current_app
from web.api.job_runner import start_scrape_job, get_job_status, query_job_results, get_job_bill

scrapes_bp = Blueprint('scrapes', __name__)

JOBS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'jobs')


@scrapes_bp.route('/scrapes', methods=['POST'])
def create_scrape():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    terms = data.get('terms', [])
    jurisdictions = data.get('jurisdictions', {})
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    if not terms:
        return jsonify({'error': 'At least one search term is required'}), 400
    if not jurisdictions:
        return jsonify({'error': 'At least one jurisdiction is required'}), 400
    
    config = {
        'Terms': terms,
        'Jurisdictions and signal': jurisdictions,
        'Settings': {}
    }
    
    if start_date:
        config['Settings']['Start Date'] = start_date
    if end_date:
        config['Settings']['End Date'] = end_date
    
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(JOBS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    config_path = os.path.join(job_dir, 'config.json')
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    try:
        start_time = time.time()
        pid = start_scrape_job(job_id, config_path)
        
        job_info = {
            'job_id': job_id,
            'status': 'running',
            'pid': pid,
            'start_time': start_time,
            'config': config
        }
        with open(os.path.join(job_dir, 'job.json'), 'w') as f:
            json.dump(job_info, f, indent=2)
        
        return jsonify({'job_id': job_id, 'status': 'running'}), 202
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@scrapes_bp.route('/scrapes/<job_id>')
def get_scrape(job_id):
    job_dir = os.path.join(JOBS_DIR, job_id)
    
    if not os.path.exists(job_dir):
        return jsonify({'error': 'Job not found'}), 404
    
    status = get_job_status(job_id)
    return jsonify(status)


@scrapes_bp.route('/scrapes')
def list_scrapes():
    if not os.path.exists(JOBS_DIR):
        return jsonify([])
    
    jobs = []
    for job_id in os.listdir(JOBS_DIR):
        job_dir = os.path.join(JOBS_DIR, job_id)
        if os.path.isdir(job_dir):
            job_json = os.path.join(job_dir, 'job.json')
            if os.path.exists(job_json):
                with open(job_json) as f:
                    job_info = json.load(f)
                    jobs.append({
                        'job_id': job_id,
                        'status': job_info.get('status', 'unknown')
                    })
    
    return jsonify(jobs)


@scrapes_bp.route('/scrapes/<job_id>/bills')
def get_job_bills(job_id):
    """Get bills from a specific job's SQLite database."""
    job_dir = os.path.join(JOBS_DIR, job_id)
    
    if not os.path.exists(job_dir):
        return jsonify({'error': 'Job not found'}), 404
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 100)
    
    results = query_job_results(job_id, page=page, per_page=per_page)
    
    if results is None:
        return jsonify({'error': 'Results database not found for this job'}), 404
    
    return jsonify(results)


@scrapes_bp.route('/scrapes/<job_id>/bills/<int:bill_id>')
def get_job_bill_detail(job_id, bill_id):
    """Get a single bill from a specific job's SQLite database."""
    job_dir = os.path.join(JOBS_DIR, job_id)
    
    if not os.path.exists(job_dir):
        return jsonify({'error': 'Job not found'}), 404
    
    bill = get_job_bill(job_id, bill_id)
    
    if bill is None:
        return jsonify({'error': 'Bill not found'}), 404
    
    return jsonify(bill)
