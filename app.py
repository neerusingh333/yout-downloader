from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
import yt_dlp
import os
import threading
import time
import logging

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

progress_data = {}

@app.route("/", methods=['GET'])
def serve_html_form():
    logger.info("Serving HTML form")
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_video():
    logger.info("Received download request")
    data = request.json
    url = data['url']
    resolution = data['format']
    download_id = str(int(time.time()))
    progress_data[download_id] = {'status': 'Starting', 'progress': 0}

    def download():
        logger.info(f"Starting download for ID: {download_id}")
        ydl_opts = {
            'format': f'bestvideo[height<={resolution[:-1]}][ext=mp4]+bestaudio[ext=m4a]/best[height<={resolution[:-1]}][ext=mp4]',
            'outtmpl': f'output_{download_id}.%(ext)s',
            'progress_hooks': [lambda d: update_progress(download_id, d)],
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            'postprocessor_args': [
                '-vcodec', 'libx264',
                '-acodec', 'aac',
            ],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f"Starting YouTube download for ID: {download_id}")
                ydl.download([url])
            logger.info(f"YouTube download completed for ID: {download_id}")
            progress_data[download_id] = {'status': 'done', 'progress': 100}
            logger.info(f"Download and processing completed for ID: {download_id}")
        except Exception as e:
            progress_data[download_id] = {'status': 'error', 'progress': str(e)}
            logger.error(f"Error during download for ID {download_id}: {str(e)}")

    threading.Thread(target=download).start()
    logger.info(f"Download thread started for ID: {download_id}")
    return jsonify({"download_id": download_id})

@app.route('/progress/<download_id>', methods=['GET'])
def progress(download_id):
    logger.info(f"Progress check for ID: {download_id}")
    progress = progress_data.get(download_id, {'status': 'Not found', 'progress': 0})
    logger.info(f"Progress for ID {download_id}: {progress}")
    return jsonify(progress)

def update_progress(download_id, d):
    if d['status'] == 'downloading':
        total_bytes = d.get('total_bytes')
        downloaded_bytes = d.get('downloaded_bytes')
        if total_bytes and downloaded_bytes:
            progress_percentage = int((downloaded_bytes / total_bytes) * 100)
            progress_data[download_id] = {'status': 'downloading', 'progress': progress_percentage}
            logger.info(f"Download progress for ID {download_id}: {progress_percentage}%")
    elif d['status'] == 'finished':
        progress_data[download_id] = {'status': 'Processing', 'progress': 99}
        logger.info(f"Download finished, processing video for ID {download_id}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port)