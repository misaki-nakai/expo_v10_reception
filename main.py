import asyncio
import websockets
import pyaudio
import numpy as np
import base64
import json
import queue
import threading
import os
import time
import requests
from datetime import datetime
import aiohttp
from multiprocessing import Process, Queue
import functools
import subprocess
import tempfile
import sys

import concurrent.futures

# from app_client import main_api_client
# ===== 追加: sheet_logger からインポート =====
from sheet_logger import (
    log_user_message_to_sheet,
    log_robot_message_to_sheet,
    log_robot_function_to_sheet,
    log_system_event_to_sheet
)
# log_system_event_to_sheet("chat launched")


last_input_time = time.time()
TIMEOUT = 300  # 音声の入力がこの秒数間なければsocketを切る

# promptをテキストファイルから読み込む
with open("prompt.txt", "r", encoding="utf-8") as f:
    prompt_robot = f.read()

url = "https://exedy-robo.com/v1/robots/"
# url = 'https://robot-dev.net/v1/robots/'
robot_id = "SR05_2502110006"
# robot_id = "SR05_2505070010"
# robot_id = "chimera5095"
timeout_duration = 10
is_function_executing = False

API_KEY = ""  # sumagi
app_api_key = "sumagi1007"

# WebSocket URLとヘッダー情報
# OpenAI
WS_URL = (
    "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview-2024-12-17"
)
HEADERS = {"Authorization": "Bearer " + API_KEY, "OpenAI-Beta": "realtime=v1"}

# NIT状態管理URL IP固定
# NIT_URL = "http://192.168.11.10:5000"
NIT_URL = "http://192.168.113.195:5000"

# 外部ファイルからデータを読み込む


def load_locations():
    with open("locations.json", "r") as file:
        return json.load(file)


locations_data = load_locations()
# print(locations_data)


# 発話状態を示すフラグ（Trueなら会話中）
conversation_active = False
# 最後にユーザー発話を検知した時刻（秒）
last_speech_time = time.time()

# グローバル再接続フラグ
should_restart = threading.Event()

# 天気情報を返す関数


def get_weather_info(city_name):
    weather_base_url = "https://api.openweathermap.org/data/2.5/weather"
    weather_api_key = "14bbbafc2d27aac4900c9c90c085630b"
    params = {
        "q": f"{city_name},jp",
        "appid": weather_api_key,
        "lang": "ja",
        "units": "metric",
    }
    try:
        response = requests.get(weather_base_url, params=params)
        response.raise_for_status()
        data = response.json()
        print(data)
        # temperature = data["main"]["temp"]
        temperature = int(round(data["main"]["temp"]))
        weather_description = data["weather"][0]["main"]
        return f"天気は{weather_description}、温度は{temperature}°C、"
    except requests.exceptions.RequestException as e:
        return f"天気情報を取得できませんでした: {e}"


def time_search():
    now = datetime.now()
    formatted_time = now.strftime("%Y年%m月%d日%H時%M分")
    return formatted_time


def openai_tts_and_play(text, max_retry=3):
    url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o-mini-tts",
        "input": text,
        "voice": "shimmer",
        "instructions": "元気な口調で話してください",
        "response_format": "mp3",
    }

    retry_count = 0
    while retry_count < max_retry:
        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                    tmp.write(response.content)
                    tmp.flush()
                    tmp_filename = tmp.name
                subprocess.run(['play', tmp_filename])
                os.remove(tmp_filename)
                return
            else:
                print("エラー:", response.status_code)
                print(response.text)
                return
        except requests.exceptions.RequestException as e:
            retry_count += 1
            print(f"通信エラー（リトライ{retry_count}/{max_retry}）: {e}")
            time.sleep(2)  # 2秒待つ
    print("TTSリクエストに失敗しました")


def retry_main_api_client(robot_id, api_name, nav_data, max_retry=3, retry_wait=2):
    for retry_count in range(1, max_retry + 1):
        nav_res = main_api_client(robot_id, api_name, nav_data)
        status = nav_res.get('status') if nav_res else None
        if status == "SUCCEEDED":
            return nav_res
        elif status == "TIMEOUT":
            print(f"[navigation] TIMEOUT発生、再試行します（{retry_count}/{max_retry}）")
            time.sleep(retry_wait)
            continue
        else:
            print(f"[navigation] 失敗: {status}")
            return nav_res
    print(f"[navigation] リトライ上限（{max_retry}回）に達しました")
    return nav_res


# Function Callingの処理ロジック
async def handle_function_call(websocket, response_data):
    global last_speech_time, is_function_executing
    is_function_executing = True
    # notify_flask_flag(True)  # 実行中フラグON
    # result_queue = Queue()
    print("handle_functon_call")
    function_call_name = response_data.get("name", {})
    function_call_data = response_data.get("arguments", {})
    # loop = asyncio.get_event_loop()
    if function_call_name == "get_weather_info":
        data_dict = json.loads(function_call_data)
        function_arg = data_dict["city_name"]
        function_result = get_weather_info(function_arg)

    elif function_call_name == "time_search":
        function_arg = ""
        function_result = time_search()

    else:
        print("指定された関数は見つかりませんでした。")
        is_function_executing = False
        # notify_flask_flag(False)
        return

    # 関数実行完了後にキューをクリア
    while not audio_send_queue.empty():
        audio_send_queue.get()

    print(audio_send_queue)
    # サーバーに関数実行完了を通知
    function_output = {
        "type": "conversation.item.create",
        "item": {  # 追加するitemパラメータ
            "call_id": response_data.get("call_id"),
            "type": "function_call_output",
            "output": function_result,
        },
    }
    await websocket.send(json.dumps(function_output))
    # log_robot_function_to_sheet(
    #     function_call_name, function_arg, function_result)
    print(f"\n[Function Call Output] {function_result}")
    last_speech_time = time.time()
    is_function_executing = False
    # notify_flask_flag(False)
    return function_result


# キューを初期化
audio_send_queue = queue.Queue()
audio_receive_queue = queue.Queue()


# PCM16形式に変換する関数
def base64_to_pcm16(base64_audio):
    audio_data = base64.b64decode(base64_audio)
    return audio_data


# 音声を送信する非同期関数
async def send_audio_from_queue(websocket):
    global is_function_executing
    while True:
        # print(f"[is_function_executing] {is_function_executing}")
        # is_function_executing = check_flask_flag()
        if is_function_executing:
            # 関数実行中は送信をスキップ
            await asyncio.sleep(1)
            continue
        audio_data = await asyncio.get_event_loop().run_in_executor(
            None, audio_send_queue.get
        )
        if audio_data is None:
            continue

        # PCM16データをBase64にエンコード
        base64_audio = base64.b64encode(audio_data).decode("utf-8")
        audio_event = {"type": "input_audio_buffer.append",
                       "audio": base64_audio}

        # WebSocketで音声データを送信
        await websocket.send(json.dumps(audio_event))

        # キューの処理間隔を少し空ける
        await asyncio.sleep(0)


# マイクからの音声を取得しキューに入れる関数
def read_audio_to_queue(stream, CHUNK):
    while True:
        try:
            audio_data = stream.read(CHUNK, exception_on_overflow=False)
            audio_send_queue.put(audio_data)
        except Exception as e:
            print(f"音声読み取りエラー: {e}")
            should_restart.set()
            break


# サーバーから音声を受信してキューに格納する非同期関数
async def receive_audio_to_queue(websocket):
    global last_speech_time, conversation_active
    print("assistant: ", end="", flush=True)
    while True:
        try:
            # response = await asyncio.wait_for(websocket.recv(), timeout=40)
            response = await websocket.recv()
        except asyncio.TimeoutError:
            print("[受信タイムアウト] サーバーからの応答がありません。接続を閉じます。")
            await websocket.close()
            # return
            raise ConnectionError("WebSocket closed")
        except websockets.ConnectionClosed:
            print("[接続終了] WebSocketが切断されました。")
            os.execv(sys.executable, [sys.executable] + sys.argv)
            # return
            raise ConnectionError("WebSocket closed")

        if response:
            response_data = json.loads(response)

            if (
                "type" in response_data
                and response_data["type"]
                == "conversation.item.input_audio_transcription.completed"
            ):
                # log_user_message_to_sheet(response_data['transcript'].strip())
                print(f"\nuser: {response_data['transcript']}", flush=True)

            # サーバーからの応答をリアルタイムに表示
            if (
                "type" in response_data
                and response_data["type"] == "response.audio_transcript.delta"
            ):
                print(response_data["delta"], end="", flush=True)
            # サーバからの応答が完了したことを取得
            elif (
                "type" in response_data
                and response_data["type"] == "response.audio_transcript.done"
            ):
                print("\nassistant: ", end="", flush=True)
                send_message_to_websocket(response_data['transcript'])
                # log_robot_message_to_sheet(response_data['transcript'])

            # こちらの発話がスタートしたことをサーバが取得したことを確認する
            if (
                "type" in response_data
                and response_data["type"] == "input_audio_buffer.speech_started"
            ):
                last_speech_time = time.time()
                conversation_active = True
                print("---------------------")
                # すでに存在する取得したAI発話音声をリセットする
                while not audio_receive_queue.empty():
                    audio_receive_queue.get()

            # サーバーからの音声データをキューに格納
            if (
                "type" in response_data
                and response_data["type"] == "response.audio.delta"
            ):
                base64_audio_response = response_data["delta"]
                if base64_audio_response:
                    pcm16_audio = base64_to_pcm16(base64_audio_response)
                    audio_receive_queue.put(pcm16_audio)

            # Function Callingの応答を処理
            if (
                "type" in response_data
                and response_data["type"] == "response.function_call_arguments.done"
            ):
                print(response_data)
                function_call_name = response_data.get("name", {})
                # function_call_data = response_data.get("arguments", {})
                if function_call_name:
                    result = await handle_function_call(websocket, response_data)
                    print(result)
                    await websocket.send(json.dumps({"type": "response.create"}))

            if "type" in response_data and response_data["type"] == "error":
                print(response_data)

        await asyncio.sleep(0)


# サーバーからの音声を再生する関数
def play_audio_from_queue(output_stream):
    global last_speech_time
    while True:
        try:
            last_speech_time = time.time()
            pcm16_audio = audio_receive_queue.get()
            if pcm16_audio:
                output_stream.write(pcm16_audio)
        except OSError as e:
            print(f"[Audio Output Error] {e}")
            break  # スレッドを安全に終了


# セッションの存続時間を監視するタスク
async def session_lifetime_checker(websocket, session_start_time, threshold=300):
    """
    threshold: セッション継続時間の閾値（秒）。例として1500秒＝25分としています。
    """
    global conversation_active, last_speech_time, is_function_executing
    last_logged_min = 0  # 最後にログ出力した経過分数を記録
    while True:
        await asyncio.sleep(30)
        # is_function_executing = check_flask_flag()
        print(f"[is_function_executing] {is_function_executing}")

        # print(conversation_active)
        elapsed = time.time() - session_start_time
        current_min = int(elapsed // 60)
        if current_min > last_logged_min:
            print(f"セッション開始から {current_min} 分経過しました。")
            last_logged_min = current_min

        # 60秒以上発話がなければ会話中フラグを落とす
        if time.time() - last_speech_time > 10:
            conversation_active = False

        # 25分経過して、かつ「会話中」でも「関数実行中」でもなければ再接続
        if elapsed > threshold:
            if not conversation_active and not is_function_executing:
                print("セッション継続時間が閾値を超え、アイドル状態のため再接続します。")
                await websocket.close()
            else:
                print("セッション継続時間が閾値を超えましたが、会話中または関数実行中のため再接続待機中...")
        else:
            if not conversation_active and not is_function_executing:
                # 最初に発話するようにレスポンスの作成を要求
                test_request = {
                    "type": "response.create",
                    "response": {
                        "instructions": "日本語でフレンドリーに挨拶してください",
                    },
                }
                await websocket.send(json.dumps(test_request))


# マイクからの音声を取得し、WebSocketで送信しながらサーバーからの音声応答を再生する非同期関数
async def stream_audio_and_receive_response():
    # WebSocketに接続
    try:
        async with websockets.connect(
            WS_URL, extra_headers=HEADERS, ping_interval=5, ping_timeout=5
        ) as websocket:
            print("WebSocketに接続しました。")

            # # タイムアウト監視タスクを開始
            # inactivity_task = asyncio.create_task(check_for_inactivity(websocket))

            # 接続時刻を記録
            session_start_time = time.time()

            # セッション再接続用タスクを開始（会話がアイドル状態のときのみ切断）
            session_checker_task = asyncio.create_task(
                session_lifetime_checker(websocket, session_start_time))

            update_request = {
                "type": "session.update",
                "session": {
                    "modalities": ["audio", "text"],
                    "instructions": prompt_robot,
                    "voice": "shimmer",
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.8,
                    },
                    "input_audio_transcription": {
                        "model": "gpt-4o-mini-transcribe",
                        "language": "ja"
                    },
                    "tools": [
                        {
                            "type": "function",
                            "name": "get_weather_info",
                            "description": "指定された都市の現在の天気情報を取得する",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "city_name": {
                                        "type": "string",
                                        "description": "天気を知りたい都市の名前。都市名は英語にしてください",
                                    },
                                },
                                "required": ["city_name"],
                            },
                        },
                        {
                            "type": "function",
                            "name": "time_search",
                            "description": "現在の時間を返します",
                        },
                    ],
                    "tool_choice": "auto",
                },
            }
            await websocket.send(json.dumps(update_request))

            # 最初に発話するようにレスポンスの作成を要求
            init_request = {
                "type": "response.create",
                "response": {
                    "instructions": "日本語でフレンドリーに挨拶します",
                },
            }
            await websocket.send(json.dumps(init_request))

            # PyAudioの設定
            INPUT_CHUNK = 2400
            OUTPUT_CHUNK = 2400
            FORMAT = pyaudio.paInt16
            CHANNELS = 1
            INPUT_RATE = 24000
            OUTPUT_RATE = 24000

            # PyAudioインスタンス
            p = pyaudio.PyAudio()

            # マイクストリームの初期化
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=INPUT_RATE,
                input=True,
                frames_per_buffer=INPUT_CHUNK,
            )

            # サーバーからの応答音声を再生するためのストリームを初期化
            output_stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=OUTPUT_RATE,
                output=True,
                frames_per_buffer=OUTPUT_CHUNK,
            )

            # マイクの音声読み取りをスレッドで開始
            threading.Thread(
                target=read_audio_to_queue, args=(
                    stream, INPUT_CHUNK), daemon=True
            ).start()

            # サーバーからの音声再生をスレッドで開始
            threading.Thread(
                target=play_audio_from_queue, args=(
                    output_stream,), daemon=True
            ).start()

            # 再接続トリガーを監視するタスク
            async def monitor_restart():
                while True:
                    if should_restart.is_set():
                        print("[再接続監視] マイクエラーを検知。WebSocketを閉じます...")
                        await websocket.close()
                        return
                    await asyncio.sleep(1)

            try:
                # 音声送信タスクと音声受信タスクを非同期で並行実行
                send_task = asyncio.create_task(
                    send_audio_from_queue(websocket))
                receive_task = asyncio.create_task(
                    receive_audio_to_queue(websocket))
                restart_task = asyncio.create_task(monitor_restart())
                # タスクが終了するまで待機
                # await asyncio.gather(send_task, receive_task, inactivity_task)
                await asyncio.gather(send_task, receive_task, session_checker_task, restart_task)
            #     tasks = [send_task, receive_task,
            #              restart_task, session_checker_task]
            #     # どれか一つでも落ちたら他を止める
            #     done, pending = await asyncio.wait(
            #         tasks, return_when=asyncio.FIRST_EXCEPTION
            #     )
            #     # 残りのタスクをキャンセル
            #     for task in pending:
            #         print(task)
            #         task.cancel()
            #     await asyncio.gather(*pending, return_exceptions=True)

            # except ConnectionError as e:
            #     print(f"[再接続のため中断] {e}")
            except KeyboardInterrupt:
                print("終了します...")
            finally:
                if stream.is_active():
                    stream.stop_stream()
                stream.close()
                output_stream.stop_stream()
                output_stream.close()
                p.terminate()
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"[WebSocket切断エラー] {e}")
        # should_restart.set()
        await websocket.close()

    except Exception as e:
        print(f"[stream_audio_and_receive_responseで例外] {e}")
        # should_restart.set()
        await websocket.close()


# サーバーに音声を送信
def send_message_to_websocket(message):
    try:
        send_response = requests.post(
            "https://expo-v10-reception.onrender.com/send_message", json={"message": message})
    except Exception as e:
        print(f"websocket 送信エラー: {e}")


# 外側のループで再接続を実現。セッションが終了したら、自動的に再接続します。
async def main_loop():
    while True:
        # print(should_restart)
        print("should_restartの状態:", should_restart.is_set())

        try:
            should_restart.clear()
            time.sleep(0.5)
            await stream_audio_and_receive_response()
        except Exception as e:
            print(f"セッション中に例外発生: {e}")
            should_restart.clear()
        print("セッションを再接続します...")
        await asyncio.sleep(3)


# def main():
#     asyncio.run(stream_audio_and_receive_response())


if __name__ == "__main__":
    # main()
    # threading.Thread(target=update_flag_periodically, daemon=True).start()
    asyncio.run(main_loop())
    # asyncio.run(stream_audio_and_receive_response())
