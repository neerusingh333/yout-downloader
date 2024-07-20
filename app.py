import os
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import yt_dlp
import threading
import time
import logging

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER

progress_data = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_video():
    data = request.json
    url = data['url']
    resolution = data['format']
    download_id = str(int(time.time()))
    progress_data[download_id] = {'status': 'Starting', 'progress': 0}

    def download():
        output_template = os.path.join(app.config['DOWNLOAD_FOLDER'], f'output_{download_id}.%(ext)s')
        ydl_opts = {
            'format': f'bestvideo[height<={resolution[:-1]}]+bestaudio/best[height<={resolution[:-1]}]',
            'outtmpl': output_template,
            'progress_hooks': [lambda d: update_progress(download_id, d)],
            'merge_output_format': 'mp4',
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Check for the file with any extension
            for ext in ['mp4', 'webm', 'mkv']:
                final_filename = f'output_{download_id}.{ext}'
                if os.path.exists(os.path.join(app.config['DOWNLOAD_FOLDER'], final_filename)):
                    progress_data[download_id] = {'status': 'done', 'progress': 100, 'filename': final_filename}
                    logger.info(f"Download completed: {final_filename}")
                    return

            raise FileNotFoundError(f"Expected file not found for download_id: {download_id}")
        except Exception as e:
            logger.error(f"Error during download: {str(e)}")
            progress_data[download_id] = {'status': 'error', 'progress': 0, 'message': str(e)}

    threading.Thread(target=download).start()
    return jsonify({"download_id": download_id})

@app.route('/progress/<download_id>')
def progress(download_id):
    data = progress_data.get(download_id, {'status': 'Not found', 'progress': 0})
    # Ensure progress is always a number
    if not isinstance(data['progress'], (int, float)):
        data['progress'] = 0
    return jsonify(data)

@app.route('/get_video/<download_id>')
def get_video(download_id):
    logger.info(f"Attempting to retrieve video for download_id: {download_id}")
    progress_info = progress_data.get(download_id)
    
    if not progress_info:
        logger.error(f"No progress data found for download_id: {download_id}")
        return "Download information not found", 404
    
    filename = progress_info.get('filename')
    if not filename:
        logger.error(f"Filename not found in progress data for download_id: {download_id}")
        return "Filename not found", 500
    
    file_path = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        logger.info(f"File found, sending: {file_path}")
        return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename, as_attachment=True)
    else:
        logger.error(f"File not found: {file_path}")
        return "File not found", 404

def update_progress(download_id, d):
    if d['status'] == 'downloading':
        progress_data[download_id] = {
            'status': 'downloading',
            'progress': float(d.get('percentage', 0))
        }
    elif d['status'] == 'finished':
        progress_data[download_id] = {
            'status': 'processing',
            'progress': 99,
            'filename': d['filename']
        }

if __name__ == '__main__':
    app.run(debug=True)