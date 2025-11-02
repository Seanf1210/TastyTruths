from flask import Flask, render_template
from services.db import db
from services.models import Recipe

app = Flask(__name__, instance_relative_config=True)
# ... DB init here ...

@app.context_processor
def inject_now():
    from datetime import datetime
    return {"now": datetime.utcnow}

@app.get("/recipes")
def list_recipes():
    rows = Recipe.query.order_by(Recipe.created_at.desc()).all()
    return render_template("recipes/list.html", recipes=rows)

@app.get("/recipes/<id_slug>")
def recipe_detail(id_slug):
    rid, _, _ = id_slug.partition("-")
    recipe = db.session.get(Recipe, int(rid))
    if not recipe:
        return "Not found", 404
    return render_template("recipes/detail.html", recipe=recipe)

@app.get("/posts")
def list_posts():
    return render_template("base.html")  # stub; make a posts/list.html later

if __name__ == "__main__":
    app.run(debug=True)
