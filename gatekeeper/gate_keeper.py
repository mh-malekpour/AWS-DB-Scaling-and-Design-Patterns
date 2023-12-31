from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Configuration for forwarding requests
FORWARD_HOST_URL = 'http://ip_address:port'

def validate_mode(request_data):
    """
    Checks if the 'Mode' in the request is either 'random' or 'direct'.
    Throws a ValueError if the mode is invalid.

    :param request_data: The incoming request data
    """
    mode = request_data.get("Mode", "").lower()
    if mode not in ["random", "direct"]:
        raise ValueError("Invalid request mode. Only 'random' and 'direct' are acceptable.")

def forward_request(endpoint, data):
    """
    Forwards the request to the specified endpoint on the forward host.

    :param endpoint: The endpoint to forward to ('read' or 'write')
    :param data: The request data to forward
    :return: Response from the forward host
    """
    response = requests.request(method=request.method, url=f"{FORWARD_HOST_URL}/{endpoint}", json=data)
    return jsonify(response.json()), response.status_code

@app.route('/read', methods=['GET'])
def read_query_handler():
    """
    Handles incoming read queries, validates the mode, and forwards them.
    """
    request_data = request.json
    try:
        validate_mode(request_data)
        return forward_request('read', request_data)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

@app.route('/write', methods=['POST'])
def write_query_handler():
    """
    Handles incoming write queries, validates the mode, and forwards them.
    """
    request_data = request.json
    try:
        validate_mode(request_data)
        return forward_request('write', request_data)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)
