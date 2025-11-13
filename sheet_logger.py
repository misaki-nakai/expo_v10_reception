import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import socket

# ===== ここを環境に合わせて設定 =====
SERVICE_ACCOUNT_FILE = 'ivory-granite-425400-c2-4bb24817eaae.json'  # サービスアカウントJSONのパス
SPREADSHEET_ID = '1TCZet_HGtXbBoO_sGoHZ_J1v2mHKvmQBNoq2ZA27iXM'      # スプレッドシートID
# 書き込みたいシート名
SHEET_NAME = 'logs'


def get_credentials():
    """
    サービスアカウントのJSONキーから認証情報(Credentials)を生成
    """
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=scopes
    )
    return creds


def append_to_sheet(values):
    """
    指定した values (2次元配列) をスプレッドシートの末尾に追記する共通関数
    """
    try:
        creds = get_credentials()
        service = build('sheets', 'v4', credentials=creds)

        body = {
            'values': values
        }
        range_name = f'{SHEET_NAME}!A1'  # append時の開始セル(どこでもOK)

        response = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=range_name,
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()

        return response
    except (HttpError, socket.gaierror, socket.timeout) as e:
        print(f"[ERROR] Google Sheets 書き込み失敗: {e}")
        return None

    except Exception as e:
        print(f"[UNEXPECTED ERROR] {e}")
        return None


def log_user_message_to_sheet(user_message):
    """
    ユーザー発話をスプレッドシートに記録
    カラム例: [Timestamp, role, SystemEvent, Message, FunctionCall, FunctionArguments, FunctionResult]
    """
    timestamp = datetime.datetime.now().isoformat()
    row = [timestamp, "user", "-", user_message, "-", "-", "-"]
    return append_to_sheet([row])


def log_robot_message_to_sheet(response_text):
    """
    ロボットの応答をスプレッドシートに記録
    カラム例: [Timestamp, role, SystemEvent, Message, FunctionCall, FunctionArguments, FunctionResult]
    """
    timestamp = datetime.datetime.now().isoformat()
    row = [timestamp, "assistant", "-", response_text, "", "", ""]
    return append_to_sheet([row])


def log_robot_function_to_sheet(function_call, function_arguments, function_result):
    """
    ロボットの応答をスプレッドシートに記録
    カラム例: [Timestamp, role, SystemEvent, Message, FunctionCall, FunctionArguments, FunctionResult]
    """
    timestamp = datetime.datetime.now().isoformat()
    row = [timestamp, "assistant", "function_calling", "-",
           function_call, function_arguments, function_result]
    return append_to_sheet([row])


def log_system_event_to_sheet(event_message):
    """
    システムイベント（起動・終了・エラー等）をスプレッドシートに記録
    カラム例: [Timestamp, role, SystemEvent, Message, FunctionCall, FunctionArguments, FunctionResult]
    """
    timestamp = datetime.datetime.now().isoformat()
    row = [timestamp, "system", event_message, "-", "-", "-", "-"]
    return append_to_sheet([row])


def log_error_event_to_sheet(event_message):
    """
    エラーイベント（起動・終了・エラー等）をスプレッドシートに記録
    カラム例: [Timestamp, role, SystemEvent, Message, FunctionCall, FunctionArguments, FunctionResult]
    """
    timestamp = datetime.datetime.now().isoformat()
    row = [timestamp, "error", event_message, "-", "-", "-", "-"]
    return append_to_sheet([row])


def log_security_event_to_sheet(event_message):
    """
    エラーイベント（起動・終了・エラー等）をスプレッドシートに記録
    カラム例: [Timestamp, role, SystemEvent, Message, FunctionCall, FunctionArguments, FunctionResult]
    """
    timestamp = datetime.datetime.now().isoformat()
    row = [timestamp, "security", event_message, "-", "-", "-", "-"]
    return append_to_sheet([row])
