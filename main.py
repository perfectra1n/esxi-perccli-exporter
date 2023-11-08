import os
import yaml
from flask import Flask, request, jsonify

app = Flask(__name__)

def load_config(file_path):
    with open(file_path, 'r') as f:
        config = yaml.safe_load(f)
    return config

def example_function(username, password):
    # Your implementation here
    pass

@app.route('/metrics')
def metrics():
    target = request.args.get('target')
    if target and target in config['targets']:
        username = config['targets'][target]['username']
        password = config['targets'][target]['password']
        example_function(username, password)
        return jsonify({"message": "Credentials found and passed to example_function"})
    else:
        return jsonify({"message": "Credentials not found"}), 500

if __name__ == '__main__':
    config_file_path = os.environ.get('CONFIG_FILE_PATH', 'config.yaml')
    config = load_config(config_file_path)
    port = int(os.environ.get('PORT', 10424))
    app.run(port=port)