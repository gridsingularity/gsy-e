from threading import Thread

from flask import Flask, render_template


def runweb(area):
    app = Flask(__name__)
    app.jinja_env.globals.update(id=id)

    @app.route("/")
    def index():
        return render_template("index.html", root_area=area)

    t = Thread(target=lambda: app.run(debug=True, use_reloader=False))
    t.setDaemon(True)
    t.start()
    return t
