# Ingredient dietary tags CRUD (Flask shell)

```
flask shell
>>> from services.db import db
>>> from services.models import Ingredient
>>> oats = Ingredient(name="Oats")
>>> oats.set_dietary_tags(["Vegan", "Gluten-Free"])
>>> db.session.add(oats)
>>> db.session.commit()

>>> oats = Ingredient.query.filter_by(name="Oats").first()
>>> [tag.name for tag in oats.dietary_tags]
['gluten-free', 'vegan']

>>> oats.add_dietary_tag("dairy-free")
>>> oats.set_dietary_tags(["vegan"])  # replace list
>>> db.session.commit()
>>> [tag.name for tag in oats.dietary_tags]
['vegan']

>>> oats.remove_dietary_tag("vegan")
>>> db.session.commit()
>>> [tag.name for tag in oats.dietary_tags]
[]

>>> db.session.delete(oats)
>>> db.session.commit()
```
