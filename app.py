from flask import Flask, render_template

from database import active_events, initialize_database


app = Flask(__name__)
initialize_database()


@app.route("/")
def home():
    return render_template("index.html", events=active_events())
