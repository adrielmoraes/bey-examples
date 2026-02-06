
import os
from livekit import api
from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv
from flask_cors import CORS

load_dotenv()

app = Flask(__name__, static_folder='.')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
CORS(app)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_file(path):
    return send_from_directory('.', path)

@app.route('/token')
def get_token():
    room_name = request.args.get('room', 'gemini-room')
    participant_name = request.args.get('name', 'user-' + os.urandom(2).hex())

    api_key = os.getenv('LIVEKIT_API_KEY')
    api_secret = os.getenv('LIVEKIT_API_SECRET')

    if not api_key or not api_secret:
        return jsonify({'error': 'LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set'}), 500

    token = api.AccessToken(api_key, api_secret) \
        .with_identity(participant_name) \
        .with_name(participant_name) \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
        ))

    return jsonify({'token': token.to_jwt(), 'url': os.getenv('LIVEKIT_URL')})

if __name__ == '__main__':
    print("Starting server on http://localhost:8000")
    app.run(port=8000)
