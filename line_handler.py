from linebot import LineBotApi
from linebot.models import TextSendMessage, QuickReply, QuickReplyButton, MessageAction
import os

# LINE Botのアクセストークンを環境変数から取得します
CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']
# LINE Bot APIのインスタンスを作成します
LINE_BOT_API = LineBotApi(CHANNEL_ACCESS_TOKEN)
# LINE Botを制御するためのクラス
class LineHandler:
    # コンストラクタでLINE Bot APIと他のハンドラを初期化します
    def __init__(self, dynamodb_handler, openai_handler):
        self.line_bot_api = LINE_BOT_API
        self.dynamodb_handler = dynamodb_handler
        self.openai_handler = openai_handler
        
        # モードごとのメッセージを辞書で定義
        self.mode_messages = {
            0: "モードを終了しました。",
            1: "Alright,I'm ready to help you with your. English conversation practice!\n Please let me know the topic you'd like to talk about.\n\n話したいトピックを英語で送ってください！フリートークを完了したい場合は下の「完了」ボタンを押してください。「完了」が押されるとこれまでの会話を踏まえてのフィードバックが行われます。フリートーク中に質問が分からない場合は下の「分からない」ボタンを押してください。\n\n「完了」を押した後に会話を通してのフィードバックが送信されます。※フィードバックが生成されるのには時間が掛かります。",
            2: "添削して欲しい英文を送ってください。※添削には時間が掛かります。",
            3: "練習したい発表原稿を送ってください！この原稿を元に想定される質問を考えます。質問に答えると次の質問をします。\n\n練習を完了したい場合は下の「完了」ボタンを押してください。発表中の質問で分からない質問は下の「分からない」ボタンを押してください。\n\n「完了」を押した後に発表練習を通してのフィードバックが送信されます。※フィードバックが生成されるのには時間が掛かります。",
            4: "習いたい講義内容を以下から選択してください！講義が始まります。講義生成には時間が掛かります。",
        }

    # LINE Bot APIを使ってメッセージを返信します
    def reply_message(self, reply_token, ai_response, mode_code):
         # 返信メッセージに含めるためのクイックリプライアイテムを生成します
        quick_reply_items = self.generate_quick_reply_items(mode_code)
        try:
            # 返信メッセージを送信します
            self.line_bot_api.reply_message(
                reply_token,
                TextSendMessage(
                    text=ai_response,
                    quick_reply=QuickReply(items=quick_reply_items)
                ))
        except Exception as e:
            print(f"Error while replying to message: {e}")

    

    # ユーザーからのメッセージを処理します
    def process_user_message(self,user_message, reply_token, user_id):
        # DynamoDBからユーザーのモードコードを取得します
        old_mode_code = self.dynamodb_handler.get_mode_code(user_id)
        mode_code = old_mode_code
        prompt = None  # OpenAI APIに送信するプロンプトを初期化します
        
        # 終了メッセージの場合はAPIを通さずにレスポンスを返します。
        if user_message == "【英文添削:完了】" or user_message == "【会話フレーズ講義:完了】":
            mode_code = 0
            self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
            ai_response = self.mode_messages[0]
            self.reply_message(reply_token, ai_response, mode_code)
            return None, mode_code, ai_response  # これ以降の処理をスキップします

        elif user_message == "【フリートーク:完了】":
            mode_code = 0
            self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
            prompt = '''#これまでの私の英文から私へのフィードバックをしてください。また、以下の要件を守ってください。
    
              # フィードバックの作り方
              ・適切なタイミングで改行して、読みやすさを確保してください。
              
              # あなたのルール
              ・日本語で私にフィードバックしてください。
              ・これまでの会話を踏まえて、私のよかった点と私の改善した方がよい点をこれまでの英語の文章を取り上げながら具体的にフィードバックしてください。
              
              # フォーマット
              今回の会話を通してのあなたへのフィードバックを行います。
              
              よかった点
              
              
              
              改善するべき点
              
              
              

              以上になります！ありがとうございました！
              '''
        elif user_message == "I don't know.":
            prompt = "同じ話題で別の質問を英語でしてください。"

        elif user_message == "【発表練習:完了】":
            mode_code = 0
            self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
            prompt = '''#聞き手としてこれまでの会話から私へのフィードバックをしてください。また、以下の要件を守ってください。

              # フィードバックの作り方
              ・適切なタイミングで改行して、読みやすさを確保してください。
              
              # あなたのルール
              ・日本語でフィードバックしてください。
              ・これまでの会話を踏まえて、発表の内容として私のよかった点と改善した方がよい点をこれまでの英語の文章を取り上げながら、具体的にフィードバックしてください。
        
              # フォーマット
              今回の会話を通してのあなたへのフィードバックを行います。
              
              よかった点
              
              
              
              改善するべき点
              
              
              
              
              以上になります！ありがとうございました！
              '''
        elif user_message == "【発表練習:分からない】":
            # mode_code remains the same
            prompt = "同じ話題で別の質問を英語でしてください。"
            
        elif user_message.startswith("【モード:"):
            if "フリートーク" in user_message:
                mode_code = 1
                self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
                prompt = '''#あなたは英会話講師です。これから私が送る話したいトピックについて英語で話してください。
                
                #あなたのルール
                ・英文は数行の文章を送ってください。
                ・毎回１個だけ質問をしてください。
                ・丁寧で文法的に正しい英語を使ってください。
                ・絵文字をたくさん使用して会話を続けてください。
                ・適切なタイミングで改行して、読みやすさを確保してください。
                
                '''
                        
            elif "英文添削" in user_message:
                mode_code = 2
                self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
                prompt = "#あなたは英文添削のプロです。私が送る英文を、文法的に丁寧で正しい英語に修正してください。"
                      
            elif "発表練習" in user_message:
                mode_code = 3
                self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
                prompt = '''#あなたは就職活動支援のプロです。これから私が練習したい英文を送るので、その英文から面接官が質問してくるであろう質問をしてください。\n\n#あなたのルール\n・あなたが文章を送る時は、１つだけ英語で質問をしてください。\n・質問は合計で3回してください。\n\n#質問形式の例\n私：I am interested in soccer.\nあなた：Q1:How did you become interested in soccer?\n私：I went to see a game with my father.\nあなた：Q2:What did you find interesting about soccer?'''
                

            elif "会話フレーズ講義" in user_message:
                mode_code = 4
                self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
                ai_response = self.mode_messages[4]
                self.reply_message(reply_token, ai_response, mode_code)
                return None, mode_code, ai_response

            elif "日常生活" in user_message:
                mode_code = 5
                self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
                prompt = '''#あなたは英会話の講師です。これから日常生活について、英会話でよく使われるフレーズをランダムで１つ題材にして講義を行なってください。講義ではフレーズの説明や例をあげてください。練習ではシナリオを作成して、会話練習してください。

                            ＃講義フォーマット
                            【講義内容】
                            
                            
                            
                            【フレーズ】
                            
                            
                            【例文】
                            
                            
                            【練習】
                            
                            
                            
                            上記のシナリオのように、メッセージを送って練習してみましょう！
                '''

            elif "気持ち" in user_message:
                mode_code = 6
                self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
                prompt = '''#あなたは英会話の講師です。これから気持ちについて、英会話でよく使われるフレーズをランダムで１つ題材にして講義を行なってください。講義ではフレーズの説明や例をあげてください。練習ではシナリオを作成して、会話練習してください。

                            ＃講義フォーマット
                            【講義内容】
                            
                            
                            
                            【フレーズ】
                            
                            
                            【例文】
                            
                            
                            【練習】
                            
                            
                            
                            上記のシナリオのように、メッセージを送って練習してみましょう！
                '''


            elif "天気" in user_message:
                mode_code = 7
                self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
                prompt = '''#あなたは英会話の講師です。これから天気について、英会話でよく使われるフレーズをランダムで１つ題材にして講義を行なってください。講義ではフレーズの説明や例をあげてください。練習ではシナリオを作成して、会話練習してください。

                            ＃講義フォーマット
                            【講義内容】
                            
                            
                            
                            【フレーズ】
                            
                            
                            【例文】
                            
                            
                            【練習】
                            
                            
                            
                            上記のシナリオのように、メッセージを送って練習してみましょう！
                '''


            elif "観光" in user_message:
                mode_code = 8
                self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
                prompt = '''#あなたは英会話の講師です。これから観光について、英会話でよく使われるフレーズをランダムで１つ題材にして講義を行なってください。講義ではフレーズの説明や例をあげてください。練習ではシナリオを作成して、会話練習してください。

                            ＃講義フォーマット
                            【講義内容】
                            
                            
                            
                            【フレーズ】
                            
                            
                            【例文】
                            
                            
                            【練習】
                            
                            
                            
                            上記のシナリオのように、メッセージを送って練習してみましょう！
                '''


            elif "レストラン" in user_message:
                mode_code = 9
                self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
                prompt = '''#あなたは英会話の講師です。これからレストランについて、英会話でよく使われるフレーズをランダムで１つ題材にして講義を行なってください。講義ではフレーズの説明や例をあげてください。練習ではシナリオを作成して、会話練習してください。

                            ＃講義フォーマット
                            【講義内容】
                            
                            
                            
                            【フレーズ】
                            
                            
                            【例文】
                            
                            
                            【練習】
                            
                            
                            
                            上記のシナリオのように、メッセージを送って練習してみましょう！
                '''


            elif "ショッピング" in user_message:
                mode_code = 10
                self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
                prompt = '''#あなたは英会話の講師です。これからショッピングについて、英会話でよく使われるフレーズをランダムで１つ題材にして講義を行なってください。講義ではフレーズの説明や例をあげてください。練習ではシナリオを作成して、会話練習してください。

                            ＃講義フォーマット
                            【講義内容】
                            
                            
                            
                            【フレーズ】
                            
                            
                            【例文】
                            
                            
                            【練習】
                            
                            
                            
                            上記のシナリオのように、メッセージを送って練習してみましょう！
                '''


            elif "学校" in user_message:
                mode_code = 11
                self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
                prompt = '''#あなたは英会話の講師です。これから学校について、英会話でよく使われるフレーズをランダムで１つ題材にして講義を行なってください。講義ではフレーズの説明や例をあげてください。練習ではシナリオを作成して、会話練習してください。

                            ＃講義フォーマット
                            【講義内容】
                            
                            
                            
                            【フレーズ】
                            
                            
                            【例文】
                            
                            
                            【練習】
                            
                            
                            
                            上記のシナリオのように、メッセージを送って練習してみましょう！
                '''


            elif "スポーツ" in user_message:
                mode_code = 12
                self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
                prompt = '''#あなたは英会話の講師です。これからスポーツについて、英会話でよく使われるフレーズをランダムで１つ題材にして講義を行なってください。講義ではフレーズの説明や例をあげてください。練習ではシナリオを作成して、会話練習してください。

                            ＃講義フォーマット
                            【講義内容】
                            
                            
                            
                            【フレーズ】
                            
                            
                            【例文】
                            
                            
                            【練習】
                            
                            
                            
                            上記のシナリオのように、メッセージを送って練習してみましょう！
                '''


            elif "恋愛" in user_message:
                mode_code = 13
                self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
                prompt = '''#あなたは英会話の講師です。これから恋愛について、英会話でよく使われるフレーズをランダムで１つ題材にして講義を行なってください。講義ではフレーズの説明や例をあげてください。練習ではシナリオを作成して、会話練習してください。

                            ＃講義フォーマット
                            【講義内容】
                            
                            
                            
                            【フレーズ】
                            
                            
                            【例文】
                            
                            
                            【練習】
                            
                            
                            
                            上記のシナリオのように、メッセージを送って練習してみましょう！
                '''


            elif "ビジネス" in user_message:
                mode_code = 14
                self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
                prompt = '''#あなたは英会話の講師です。これからビジネスについて、英会話でよく使われるフレーズをランダムで１つ題材にして講義を行なってください。講義ではフレーズの説明や例をあげてください。練習ではシナリオを作成して、会話練習してください。

                            ＃講義フォーマット
                            【講義内容】
                            
                            
                            
                            【フレーズ】
                            
                            
                            【例文】
                            
                            
                            【練習】
                            
                            
                            
                            上記のシナリオのように、メッセージを送って練習してみましょう！
                '''


            elif "電話" in user_message:
                mode_code = 15
                self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
                prompt = '''#あなたは英会話の講師です。これから電話について、英会話でよく使われるフレーズをランダムで１つ題材にして講義を行なってください。講義ではフレーズの説明や例をあげてください。練習ではシナリオを作成して、会話練習してください。

                            ＃講義フォーマット
                            【講義内容】
                            
                            
                            
                            【フレーズ】
                            
                            
                            【例文】
                            
                            
                            【練習】
                            
                            
                            
                            上記のシナリオのように、メッセージを送って練習してみましょう！
                '''


            elif "会議" in user_message:
                mode_code = 16
                self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)
                prompt = '''#あなたは英会話の講師です。これから会議について、英会話でよく使われるフレーズをランダムで１つ題材にして講義を行なってください。講義ではフレーズの説明や例をあげてください。練習ではシナリオを作成して、会話練習してください。

                            ＃講義フォーマット
                            【講義内容】
                            
                            
                            
                            【フレーズ】
                            
                            
                            【例文】
                            
                            
                            【練習】
                            
                            
                            
                            上記のシナリオのように、メッセージを送って練習してみましょう！
                '''

            if mode_code != old_mode_code and 0 <= mode_code <= 4:
                ai_response = self.mode_messages[mode_code]
                self.reply_message(reply_token, ai_response, mode_code)
                # Update the user mode_code in DynamoDB
                self.dynamodb_handler.update_mode_code(user_id, mode_code)
                return None, mode_code, ai_response  
                

        else:
            prompt = f'ユーザー：{user_message}\nAI：'
            self.dynamodb_handler.update_user_usage(user_id, 0, mode_code)

        # プロンプトとユーザーの会話履歴を使ってOpenAIからAIのレスポンスを取得します
        conversation_history = self.dynamodb_handler.get_conversation_history(user_id)
        ai_response = self.openai_handler.get_ai_response(prompt, user_id, conversation_history,mode_code)
        # 取得したAIのレスポンスをユーザーに返信します
        self.reply_message(reply_token, ai_response, mode_code)
        return prompt, mode_code, ai_response

        
    # クイックリプライアイテムを生成します
    def generate_quick_reply_items(self, mode_code):
        if mode_code == 1:
            quick_reply_items = [
                QuickReplyButton(action=MessageAction(label="完了", text="【フリートーク:完了】")),
                QuickReplyButton(action=MessageAction(label="分からない", text="I don't know."))
            ]
        elif mode_code == 2:
            quick_reply_items = [
                QuickReplyButton(action=MessageAction(label="完了", text="【英文添削:完了】"))
            ]
        elif mode_code == 3:
            quick_reply_items = [
                QuickReplyButton(action=MessageAction(label="完了", text="【発表練習:完了】")),
                QuickReplyButton(action=MessageAction(label="分からない", text="I don't know."))
            ]
        elif mode_code == 4:
            quick_reply_items = [
                QuickReplyButton(action=MessageAction(label="日常生活", text="【モード:日常生活】")),
                QuickReplyButton(action=MessageAction(label="気持ち", text="【モード:気持ち】")),
                QuickReplyButton(action=MessageAction(label="天気", text="【モード:天気】")),
                QuickReplyButton(action=MessageAction(label="観光", text="【モード:観光】")),
                QuickReplyButton(action=MessageAction(label="レストラン", text="【モード:レストラン】")),
                QuickReplyButton(action=MessageAction(label="ショッピング", text="【モード:ショッピング】")),
                QuickReplyButton(action=MessageAction(label="学校", text="【モード:学校】")),
                QuickReplyButton(action=MessageAction(label="スポーツ", text="【モード:スポーツ】")),
                QuickReplyButton(action=MessageAction(label="恋愛", text="【モード:恋愛】")),
                QuickReplyButton(action=MessageAction(label="ビジネス", text="【モード:ビジネス】")),
                QuickReplyButton(action=MessageAction(label="電話", text="【モード:電話】")),
                QuickReplyButton(action=MessageAction(label="会議", text="【モード:会議】"))
            ]
        elif mode_code in range(5, 17):
            quick_reply_items = [
                QuickReplyButton(action=MessageAction(label="完了", text="【会話フレーズ講義:完了】"))
            ]
        else:
            quick_reply_items = [
                QuickReplyButton(action=MessageAction(label="フリートーク", text="【モード:フリートーク】")),
                QuickReplyButton(action=MessageAction(label="英文添削", text="【モード:英文添削】")),
                QuickReplyButton(action=MessageAction(label="発表練習", text="【モード:発表練習】")),
                QuickReplyButton(action=MessageAction(label="会話フレーズ講義", text="【モード:会話フレーズ講義】"))
            ]
        return quick_reply_items