import boto3
import datetime
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')

# DynamoDBに関連する処理を管理するクラス
class DynamoDBHandler:
    # コンストラクタで各テーブルの名前を初期化し、対応するテーブルオブジェクトを取得します
    def __init__(self, user_table_name, log_table_name):
        self.user_table_name = user_table_name
        self.log_table_name = log_table_name
        self.user_table = dynamodb.Table(self.user_table_name)
        self.log_table = dynamodb.Table(self.log_table_name)

    # ユーザーの使用情報を更新します。新しいユーザーであれば新たに項目を作成し、すでに存在するユーザーであれば情報を更新します
    def update_user_usage(self, user_id, api_count, mode_code):
        # Determine the date considering the reset at 4:00 AM (Japan time)
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
        if now.hour < 4:
            now = now - datetime.timedelta(days=1)
        today = now.strftime("%Y-%m-%d")

        user = self.user_table.get_item(Key={'line_user_id': user_id})

        if 'Item' not in user or user['Item']['last_used_date'] != today:
            if api_count > 6:
                raise Exception("利用制限に達しました。明日の午前4時にリセットされます。")
            self.user_table.put_item(
                Item={
                    'line_user_id': user_id,
                    'api_count_total': api_count,
                    'mode_code': mode_code,
                    'last_used_date': today
                }
            )
        else:
            updated_api_count = user['Item']['api_count_total'] + api_count
            if updated_api_count > 6:
                raise Exception("利用制限に達しました。明日の午前4時にリセットされます。")
            self.user_table.update_item(
                Key={'line_user_id': user_id},
                UpdateExpression="SET api_count_total = api_count_total + :val, mode_code = :mode, last_used_date = :date",
                ExpressionAttributeValues={
                    ':val': api_count,
                    ':mode': mode_code,
                    ':date': today
                }
            )

    # ユーザーのモードコードを更新します
    def update_mode_code(self, user_id, mode_code):
        today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")
        user = self.user_table.get_item(Key={'line_user_id': user_id})

        if 'Item' in user:
            self.user_table.update_item(
                Key={'line_user_id': user_id},
                UpdateExpression="SET mode_code = :mode",
                ExpressionAttributeValues={
                    ':mode': mode_code,
                }
            )
        else:
            self.user_table.put_item(
                Item={
                    'line_user_id': user_id,
                    'api_count_total': 0,
                    'mode_code': mode_code,
                    'last_used_date': today
                }
            )

    # ユーザーのモードコードを取得します
    def get_mode_code(self, user_id):
        today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")
        user = self.user_table.get_item(Key={'line_user_id': user_id})
        if 'Item' in user:
            return user['Item']['mode_code']
        else:
            return 0

    # ユーザーのメッセージとAIのレスポンスをログテーブルに保存します
    def save_log(self, user_id, user_message, ai_response, mode_code):
        timestamp = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime('%Y-%m-%d %H:%M:%S')

        self.log_table.put_item(Item={
            'line_user_id': user_id,
            'user_message': user_message,
            'ai_response': ai_response,
            'mode_code': mode_code,
            'created_at': timestamp,
        })

    # ユーザーの会話履歴を取得します
    def get_conversation_history(self, user_id):
        response = self.log_table.query(
            KeyConditionExpression=Key('line_user_id').eq(user_id),
            Limit=6,
            ScanIndexForward=False
        )

        conversation_history = []
        items = response['Items'][::-1]  # Reverse the list to get the latest 20 items

        for item in items:
            conversation_history.append({"role": "user", "content": item['user_message']})
            conversation_history.append({"role": "assistant", "content": item['ai_response']})
        
        return conversation_history
