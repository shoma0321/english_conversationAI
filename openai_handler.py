import openai
import requests

# OpenAI APIを管理するクラス
class OpenAIHandler:
    # コンストラクタでAPIキーを初期化します
    def __init__(self, api_key,dynamodb_handler):
        self.api_key = api_key
        self.dynamodb_handler = dynamodb_handler
        openai.api_key = self.api_key

    # OpenAI APIを使ってAIのレスポンスを取得します
    def get_ai_response(self, prompt, user_id, conversation_history, mode_code):
        try:
            self.dynamodb_handler.update_user_usage(user_id, 1, mode_code)
        except Exception as e:
            return str(e)
        # リクエストデータを作成します。会話履歴とユーザーからのプロンプトを含めます
        data = {
            "model": "gpt-4",
            "messages": [{"role": "system", "content": "あなたは英会話をサポートするアシスタントです。"}]
            + conversation_history
            + [{"role": "user", "content": prompt}],
            "max_tokens": 3000,
            "temperature":0.0,
            "frequency_penalty": 0,
            "presence_penalty": 0
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        # POSTリクエストを送信し、AIからのレスポンスを取得します
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
        
        # レスポンスのステータスコードが200以外の場合はエラーをスローします
        if response.status_code != 200:
            raise Exception(f"Failed to get a response from OpenAI: {response.text}")

        # レスポンスデータからAIのメッセージを取り出し、前後の空白を削除します
        response_data = response.json()
        return response_data['choices'][0]['message']['content'].strip()
