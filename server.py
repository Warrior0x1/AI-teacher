from flask_socketio import SocketIO  # 确保从 flask_socketio 导入 SocketIO
from flask import Flask, request
from flask_cors import CORS
from flask_socketio import disconnect
from article_helper import  llm_thread
from waitress import serve
import logging
from langchain.embeddings.openai import OpenAIEmbeddings



embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
app = Flask(__name__)
# 创建 SocketIO 实例
socketio = SocketIO()
# 将 SocketIO 实例与 Flask 应用关联，并设置跨域请求的来源
socketio.init_app(app, cors_allowed_origins='*')


app.config['TIMEOUT_NONE'] = True
app.debug = 0
CORS(app)

@app.route('/', methods=['GET', 'POST'])
def hello_world():
    return 'Hello, World!'

# 处理 WebSocket 连接事件
@socketio.on('connect', namespace='/support')
def connected_msg():
    # 打印提示信息
    print('client connected.')

# 处理 WebSocket 断开连接事件
@socketio.on('disconnect', namespace='/support')
def disconnect_msg():
    disconnect(request.sid, namespace='/support')
    # 打印提示信息
    print('client disconnected.')


# 处理来自客户端的特定事件（my_event）
@socketio.on('ai-support', namespace='/support')
def handle_support_article(data):
    function_name = data["function"]

    if(function_name == "article"):

        collection_name = "enocmics_book"

    elif(function_name == "question"):

        collection_name = "economics_questions"

    llm_thread(data, collection_name)




def run_flask_app():
    logger = logging.getLogger('waitress')  # Get Waitress logger
    logger.setLevel(logging.INFO)  # Set logging level
    serve(app, host='0.0.0.0', port=5002, clear_untrusted_proxy_headers=False, threads=100)


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5002, debug=True,allow_unsafe_werkzeug=True)
