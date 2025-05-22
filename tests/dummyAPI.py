from flask import Flask, request, jsonify

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

if __name__ == '__main__':
    app.run(debug=True)