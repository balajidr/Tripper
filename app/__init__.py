from flask import Flask
from flask_session import Session

app = Flask(__name__)
sess = Session()
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = 'redsfsfsfsfis'
sess.init_app(app)

from app import views