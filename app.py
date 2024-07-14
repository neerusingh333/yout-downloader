from flask import Flask, request, jsonify, render_template, Response, send_file
from flask_cors import CORS
import yt_dlp
import os
import threading
import time

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

progress_data = {}

@app.route("/", methods=['GET'])
def serve_html_form():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_video():
    data = request.json
    url = data['url']
    resolution = data['format']
    download_id = str(int(time.time()))
    progress_data[download_id] = 0

    def download():
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
                ydl.download([url])
            progress_data[download_id] = 'done'
        except Exception as e:
            progress_data[download_id] = f'error: {str(e)}'

    threading.Thread(target=download).start()
    return jsonify({"download_id": download_id})

@app.route('/progress/<download_id>', methods=['GET'])
def progress(download_id):
    def generate():
        while True:
            progress = progress_data.get(download_id, 0)
            yield f'data: {{"progress": "{progress}"}}\n\n'
            if progress == 'done' or 'error' in str(progress):
                break
            time.sleep(1)
    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response

@app.route('/get_video/<download_id>', methods=['GET'])
def get_video(download_id):
    file_path = f'output_{download_id}.mp4'
    if os.path.exists(file_path):
        try:
            return send_file(file_path, as_attachment=True, mimetype='video/mp4')
        finally:
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Error deleting file: {e}")
    return "File not found", 404

def update_progress(download_id, d):
    if d['status'] == 'downloading':
        total_bytes = d.get('total_bytes')
        downloaded_bytes = d.get('downloaded_bytes')
        if total_bytes and downloaded_bytes:
            progress_percentage = int((downloaded_bytes / total_bytes) * 100)
            progress_data[download_id] = progress_percentage
    elif d['status'] == 'finished':
        progress_data[download_id] = 'Processing'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)