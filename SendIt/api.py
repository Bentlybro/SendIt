import os
import random
import threading
import time
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

files = {}
lock = threading.Lock()

def generate_code():
    return ''.join(random.choices('0123456789', k=6))

def remove_file_after_timeout(code, uploader_sid, timeout=600):
    start_time = time.time()
    while time.time() - start_time < timeout:
        with lock:
            if code not in files or files[code].get('downloading'):
                return
        remaining_time = int(timeout - (time.time() - start_time))
        socketio.emit('countdown', {'code': code, 'remaining_time': remaining_time}, room=uploader_sid)
        time.sleep(1)
    
    with lock:
        if code in files:
            del files[code]
            socketio.emit('file_expired', {'code': code}, room=uploader_sid)
            print(f"File transfer for code {code} has expired and been removed.")

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('upload_file')
def handle_upload_file(data):
    code = generate_code()
    file = data['file']
    uploader_sid = request.sid

    with lock:
        files[code] = {'file': file, 'uploader_sid': uploader_sid, 'downloading': False}

    threading.Thread(target=remove_file_after_timeout, args=(code, uploader_sid)).start()
    
    emit('file_uploaded', {'code': code}, room=uploader_sid)

@socketio.on('join')
def on_join(data):
    code = data['code']
    join_room(code)
    emit('joined_room', {'message': f'Joined room {code}'}, room=code)

@socketio.on('download_request')
def handle_download_request(data):
    code = data['code']
    with lock:
        if code in files:
            file_info = files[code]
            file = file_info['file']
            uploader_sid = file_info['uploader_sid']
            file_info['downloading'] = True
            emit('download_file', {'file': file}, room=code)
            emit('download_started', {'message': f'Download started for code {code}'}, room=code)
            emit('file_downloading', {'message': 'File is being downloaded'}, room=uploader_sid)
        else:
            emit('error', {'message': 'Invalid code or file does not exist'}, room=code)

@socketio.on('disconnect')
def on_disconnect():
    leave_room(request.sid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
