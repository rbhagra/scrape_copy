import os
import sys
import json
import subprocess
import psutil
import time
import glob

JOBS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'jobs'))
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PIPELINE_DIR = os.path.join(PROJECT_ROOT, 'pipeline')

DB_DIR = os.path.join(PROJECT_ROOT, 'db related')
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results', 'bills')
STALL_AFTER_SECONDS = 180


def get_log_metadata(log_path):
    if not os.path.exists(log_path):
        return {'size': 0, 'age_seconds': None}
    mtime = os.path.getmtime(log_path)
    return {
        'size': os.path.getsize(log_path),
        'age_seconds': max(0, int(time.time() - mtime)),
    }


def start_scrape_job(job_id, config_path):
    job_dir = os.path.join(JOBS_DIR, job_id)
    log_path = os.path.join(job_dir, 'output.log')

    run_scheduled_path = os.path.join(PIPELINE_DIR, 'run_scheduled.py')
    if not os.path.exists(run_scheduled_path):
        raise FileNotFoundError(
            f"Pipeline entry point not found: {run_scheduled_path}"
        )


    env = os.environ.copy()
    extra_paths = [PIPELINE_DIR, PROJECT_ROOT, DB_DIR]
    existing = env.get('PYTHONPATH', '')
    env['PYTHONPATH'] = os.pathsep.join(
        [p for p in extra_paths + [existing] if p]
    )
    # Ensure pipeline output appears in job logs immediately.
    env['PYTHONUNBUFFERED'] = '1'
    # Set db_type for the subprocess independently of the Flask server's .env
    env['db_type'] = 'SQLite'

    with open(log_path, 'w') as log_file:
        process = subprocess.Popen(
            [sys.executable, '-u', run_scheduled_path, '--config', os.path.abspath(config_path)],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=PIPELINE_DIR,
            env=env,
            start_new_session=True,
        )

    return process.pid


def find_latest_status_json(after_time):
    """Find the most recent status.json created after the given timestamp."""
    if not os.path.exists(RESULTS_DIR):
        return None
    
    latest_status = None
    latest_mtime = 0
    
    for results_subdir in glob.glob(os.path.join(RESULTS_DIR, '*')):
        if not os.path.isdir(results_subdir):
            continue
        status_path = os.path.join(results_subdir, 'status.json')
        if os.path.exists(status_path):
            mtime = os.path.getmtime(status_path)
            if mtime > after_time and mtime > latest_mtime:
                latest_mtime = mtime
                latest_status = status_path
    
    return latest_status


def is_process_running(pid):
    try:
        process = psutil.Process(pid)
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def get_job_status(job_id):
    job_dir = os.path.join(JOBS_DIR, job_id)
    job_json_path = os.path.join(job_dir, 'job.json')
    log_path = os.path.join(job_dir, 'output.log')
    
    if not os.path.exists(job_json_path):
        return {'job_id': job_id, 'status': 'not_found'}
    
    with open(job_json_path) as f:
        job_info = json.load(f)
    
    pid = job_info.get('pid')
    running = is_process_running(pid) if pid else False
    start_time = job_info.get('start_time', 0)
    
    result = {
        'job_id': job_id,
        'config': job_info.get('config', {}),
    }
    
    if running:
        log_meta = get_log_metadata(log_path)
        runtime_seconds = max(0, int(time.time() - start_time))
        stalled = (
            runtime_seconds >= STALL_AFTER_SECONDS
            and (
                log_meta['size'] == 0
                or (
                    log_meta['age_seconds'] is not None
                    and log_meta['age_seconds'] >= STALL_AFTER_SECONDS
                )
            )
        )

        result['status'] = 'running'
        result['runtime_seconds'] = runtime_seconds
        result['log_size_bytes'] = log_meta['size']
        result['last_log_update_seconds_ago'] = log_meta['age_seconds']
        result['activity_state'] = 'stalled' if stalled else 'active'
        if stalled:
            result['activity_note'] = (
                f"No log activity for >= {STALL_AFTER_SECONDS}s. "
                "The worker may be stuck."
            )
    else:
        status_json_path = find_latest_status_json(start_time)
        if status_json_path:
            with open(status_json_path) as f:
                status_data = json.load(f)
            result['status'] = 'completed'
            result['results'] = status_data
            
            job_info['status'] = 'completed'
            job_info['results_path'] = os.path.dirname(status_json_path)
            with open(job_json_path, 'w') as f:
                json.dump(job_info, f, indent=2)
        else:
            result['status'] = 'failed'
            if os.path.exists(log_path):
                with open(log_path) as f:
                    result['log'] = f.read()[-5000:]
            
            job_info['status'] = 'failed'
            with open(job_json_path, 'w') as f:
                json.dump(job_info, f, indent=2)
    
    return result
