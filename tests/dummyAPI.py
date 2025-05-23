from flask import Flask, request, jsonify, redirect, make_response, abort
import time

# API to test the functionality of the PostMaker

app = Flask(__name__)

@app.route('/api/test', methods=['POST'])
def test_postmaker_post():
    data = request.get_json()
    response = {
        "received": data,
        "status": "success",
        "message": "POST method: PostMaker API test successful."
    }
    return jsonify(response), 200

@app.route('/api/test', methods=['GET'])
def test_postmaker_get():
    response = {
        "status": "success",
        "message": "GET method: PostMaker API test successful."
    }
    return jsonify(response), 200

@app.route('/api/test', methods=['PUT'])
def test_postmaker_put():
    data = request.get_json()
    response = {
        "received": data,
        "status": "success",
        "message": "PUT method: PostMaker API test successful."
    }
    return jsonify(response), 200

@app.route('/api/test', methods=['DELETE'])
def test_postmaker_delete():
    data = request.get_json()
    response = {
        "received": data,
        "status": "success",
        "message": "DELETE method: PostMaker API test successful."
    }
    return jsonify(response), 200

# --- Additional endpoints for status code testing ---

@app.route('/api/status/<int:code>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def test_status_code(code):
    # Return a response with the requested status code
    messages = {
        200: "OK",
        201: "Created",
        202: "Accepted",
        204: "No Content",
        301: "Moved Permanently",
        302: "Found",
        304: "Not Modified",
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        409: "Conflict",
        418: "I'm a teapot",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout"
    }
    msg = messages.get(code, "Custom Status")
    if code == 204:
        return '', 204
    return jsonify({"status": code, "message": msg}), code

@app.route('/api/redirect', methods=['GET'])
def test_redirect():
    # 302 redirect to /api/test
    return redirect('/api/test', code=302)

@app.route('/api/auth', methods=['GET'])
def test_auth():
    auth = request.headers.get('Authorization', '')
    if not auth or not auth.startswith('Bearer '):
        return jsonify({"error": "Unauthorized"}), 401
    token = auth.split(' ', 1)[1]
    if token != "testtoken":
        return jsonify({"error": "Forbidden"}), 403
    return jsonify({"message": "Authenticated"}), 200

@app.route('/api/validation', methods=['POST'])
def test_validation():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({"error": "Missing 'name' field"}), 400
    if len(data['name']) < 3:
        return jsonify({"error": "Name too short"}), 422
    return jsonify({"message": f"Hello, {data['name']}!"}), 201

@app.route('/api/timeout', methods=['GET'])
def test_timeout():
    # Simulate a slow response
    time.sleep(5)
    return jsonify({"message": "Delayed response"}), 200

@app.route('/api/conflict', methods=['POST'])
def test_conflict():
    data = request.get_json()
    if data and data.get('id') == 1:
        return jsonify({"error": "Resource already exists"}), 409
    return jsonify({"message": "Resource created"}), 201

@app.route('/api/teapot', methods=['GET'])
def test_teapot():
    return jsonify({"message": "I'm a teapot"}), 418

@app.route('/api/empty', methods=['GET'])
def test_empty():
    # Return empty body with 204
    return '', 204

@app.route('/api/html', methods=['GET'])
def test_html():
    html = "<html><body><h1>Hello, HTML!</h1></body></html>"
    return make_response(html, 200, {"Content-Type": "text/html"})

@app.route('/api/echo', methods=['POST'])
def test_echo():
    # Echo back posted data
    data = request.get_json()
    return jsonify({"echo": data}), 200

@app.route('/api/headers', methods=['GET'])
def test_headers():
    # Return request headers in response
    return jsonify({"headers": dict(request.headers)}), 200

@app.route('/api/large', methods=['GET'])
def test_large():
    # Return a large payload
    data = {"numbers": list(range(1000))}
    return jsonify(data), 200

@app.route('/api/error', methods=['GET'])
def test_error():
    # Simulate server error
    abort(500)

if __name__ == '__main__':
    app.run(debug=True)