#!flask/bin/python
from app import app, sess

app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = 'reds209ndsldssdsljdsldsdsljdsldksdksdsdfsfsfsfis'
sess.init_app(app)

if __name__ == "__main__":
    app.run(debug=True, threaded=True)
