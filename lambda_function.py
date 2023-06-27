import json
import os
from dynamodb_handler import DynamoDBHandler
from openai_handler import OpenAIHandler
from line_handler import LineHandler

# AWS Lambda functionの環境変数から必要な情報を取得します
USER_TABLE_NAME = os.environ['USER_TABLE_NAME']
LOG_TABLE_NAME = os.environ['LOG_TABLE_NAME']
CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']
OPENAI_API_KEY = os.environ['OPENAI_API_KEY']

def lambda_handler(event, context):
    # eventのbodyをJSONとして読み込みます
    body = json.loads(event['body'])

    # LINEからのリクエストのトークンとユーザーIDを取得します
    reply_token = body['events'][0]['replyToken']
    user_id = body['events'][0]['source']['userId']
    
    # 各ハンドラを初期化します
    dynamodb_handler = DynamoDBHandler(USER_TABLE_NAME, LOG_TABLE_NAME)
    openai_handler = OpenAIHandler(OPENAI_API_KEY,dynamodb_handler) 
    line_handler = LineHandler(dynamodb_handler, openai_handler)

    # イベントがメッセージタイプでない、またはメッセージがテキストタイプでない場合、エラーメッセージを設定します
    if not body['events'][0]['type'] == 'message':
        error_message = "Error: Event is not a message type."
    elif not body['events'][0]['message']['type'] == 'text':
        error_message = "Error: Message is not a text type."
    else:
        # メッセージを取得します
        user_message = body['events'][0]['message']['text']
        error_message = None

    # ユーザーメッセージを処理します
    handle_user_message(user_message, reply_token, user_id, error_message, dynamodb_handler, openai_handler, line_handler)

    # レスポンスを返します
    return {'statusCode': 200, 'body': json.dumps('Success!')}


def handle_user_message(user_message, reply_token, user_id, error_message, dynamodb_handler, openai_handler, line_handler):
    DEFAULT_MODE_CODE = 0
    # エラーメッセージがある場合、それを返します
    if error_message:
        line_handler.reply_message(reply_token, error_message,DEFAULT_MODE_CODE)
        return

    # 現在のモードコードを取得します
    mode_code = dynamodb_handler.get_mode_code(user_id)

    # ユーザーメッセージを処理し、新たなプロンプトとモードコードを取得します
    prompt, new_mode_code, ai_response = line_handler.process_user_message(user_message, reply_token, user_id)

    # 新しいモードコードがある場合、それを更新します
    if new_mode_code is not None:
        mode_code = new_mode_code
        dynamodb_handler.update_mode_code(user_id, mode_code)

    # ログを保存します
    dynamodb_handler.save_log(user_id, user_message, ai_response, mode_code)

    # クイックリプライ項目を生成します
    quick_reply_items = line_handler.generate_quick_reply_items(mode_code)
