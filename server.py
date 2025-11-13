import os
from flask import Flask, request, jsonify, render_template, send_file
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import subprocess
import threading
import json
import requests
import time
import queue
# from app_client import main_api_client

# ===== 追加: sheet_logger からインポート =====
from sheet_logger import (
    log_user_message_to_sheet,
    log_robot_message_to_sheet,
    log_robot_function_to_sheet,
    log_system_event_to_sheet,
    log_error_event_to_sheet,
    log_security_event_to_sheet,
)
# log_system_event_to_sheet("server launched")


app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

process = None
robot_id = "SR05_2502110006"
# robot_id = "chimera5095"
# robot_id = "SR05_2505070010"


is_function_executing = False


def run_python_script():
    global process
    process = subprocess.Popen(["python3", "main.py"])


@app.route('/appstart', methods=['POST'])
def app_start():
    global process
    # locations_data = load_json("locations.json")
    # point_name = '会話位置'
    # point = locations_data["points"]
    # initialize_pose = {
    #     'name': point_name,
    #     'x': point[point_name]['x'],
    #     'y': point[point_name]['y'],
    #     'angle': point[point_name]['angle'],
    # }
    # init_response = main_api_client(
    #     robot_id, 'navigation', initialize_pose)
    if process is None or process.poll() is not None:  # プロセスが停止中であれば開始
        thread = threading.Thread(target=run_python_script)
        thread.start()
        return jsonify({"status": "started"})
    else:
        return jsonify({"status": "already running"})


@app.route('/start', methods=['POST'])
def start_script():
    global process
    if process is None or process.poll() is not None:  # プロセスが停止中であれば開始
        thread = threading.Thread(target=run_python_script)
        thread.start()
        return jsonify({"status": "started"})
    else:
        return jsonify({"status": "already running"})


@app.route('/stop', methods=['POST'])
def stop_script():
    global process
    if process and process.poll() is None:  # プロセスが実行中であれば停止
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        process = None
        # log_system_event_to_sheet("chat closed")
        return jsonify({"status": "stopped"})
    else:
        return jsonify({"status": "not running"})


@app.route('/restart', methods=['POST'])
def restart_script():
    global process

    # Stop the script if it's running
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        process = None
        # log_system_event_to_sheet("chat closed")

    # Start the script again
    thread = threading.Thread(target=run_python_script)
    thread.start()

    return jsonify({"status": "restarted"})


@app.route('/initpose', methods=['POST'])
def initialize_pose():
    locations_data = load_json("locations.json")
    point_name = '会話位置'
    point = locations_data["points"]
    initialize_pose_data = {
        'name': point_name,
        'x': point[point_name]['x'],
        'y': point[point_name]['y'],
        'angle': point[point_name]['angle'],
    }
    init_response = main_api_client(
        robot_id, 'initialize_pose', initialize_pose_data)

    if init_response.get('status') != "SUCCEEDED":
        return jsonify({"status": "failed"}), 401
    else:
        # log_system_event_to_sheet("initialize pose")
        return jsonify({"status": "success"}), 200


@app.route('/homepose', methods=['POST'])
def home_pose():
    locations_data = load_json("locations.json")
    point_name = '会話位置'
    point = locations_data["points"]
    home_pose_data = {
        'name': point_name,
        'x': point[point_name]['x'],
        'y': point[point_name]['y'],
        'angle': point[point_name]['angle'],
    }
    home_response = main_api_client(
        robot_id, 'navigation', home_pose_data)
    if home_response.get('status') != "SUCCEEDED":
        return jsonify({"status": "failed"}), 401
    else:
        # log_system_event_to_sheet("initialize pose")
        return jsonify({"status": "success"}), 200


@app.route('/send_name', methods=['POST'])
def send_name():
    data = request.get_json()
    item_name = data.get("name")
    print(item_name)
    return jsonify({"status": "success"}), 200


@app.route('/send_message', methods=['POST'])
def send_message():
    # AIの発話をwebsocket
    data = request.json
    message = data.get("message", "")
    # print(message)
    if message:
        socketio.emit("assistant_message", {"message": message})
        return jsonify({'status': "error"})
    # return render_template('index.html')
    else:
        return jsonify({'status': "error", "message": "No message provided"})


# 関数実行状態を管理
@app.route('/set_flag', methods=['POST'])
def set_flag():
    global is_function_executing
    data = request.get_json()
    is_function_executing = data.get('value', False)
    print(is_function_executing)
    return jsonify({"status": "ok", "flag": is_function_executing})


@app.route('/flag_status', methods=['GET'])
def get_flag():
    global is_function_executing
    return jsonify({"function_flag": is_function_executing})


@app.route('/')
def index():
    return render_template('index.html')


def load_json(filename):
    with open(filename, "r",  encoding="utf-8") as file:
        return json.load(file)


# if __name__ == '__main__':
#     # 初回起動時に main.py を実行
#     # thread = threading.Thread(target=run_python_script)
#     # thread.start()
#     # socketio.run(app, host='0.0.0.0', port=5000)
#     app.run(host='0.0.0.0', port=5000)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    # eventletで動かす（後でインストールする）
    socketio.run(app, host='0.0.0.0', port=port)
