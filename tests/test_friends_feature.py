from sqlalchemy.pool import StaticPool

from app import create_app
from services.db import db
from services.friendships import FriendshipError
from services.models import BlogPost, Friendship, Recipe, User


def _make_app():
    return create_app(
        config_overrides={
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            },
        },
        seed_demo=False,
    )


def _login(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def _create_user(username: str) -> User:
    user = User(username=username, password_hash="placeholder")
    db.session.add(user)
    db.session.flush()
    return user


def test_friendship_helpers_use_canonical_storage_and_support_add_remove():
    app = _make_app()
    with app.app_context():
        user_a = _create_user("chef_a")
        user_b = _create_user("chef_b")
        db.session.commit()

        user_b.add_friend(user_a)
        db.session.commit()

        friendship = Friendship.query.one()
        assert (friendship.user_id, friendship.friend_id) == tuple(sorted((user_a.id, user_b.id)))
        assert user_a.is_friends_with(user_b)
        assert user_b.is_friends_with(user_a)
        assert [friend.username for friend in user_a.get_friends()] == ["chef_b"]
        assert user_a.friend_count() == 1

        try:
            user_a.add_friend(user_a)
            raise AssertionError("Expected self-friending to fail")
        except FriendshipError:
            pass

        try:
            user_a.add_friend(user_b)
            raise AssertionError("Expected duplicate friendship to fail")
        except FriendshipError:
            pass

        assert user_a.remove_friend(user_b) is True
        db.session.commit()
        assert Friendship.query.count() == 0
        assert user_a.remove_friend(user_b) is False

        db.session.remove()
        db.drop_all()


def test_add_remove_friend_routes_and_friends_page_require_login():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        _create_user("chef_target")
        db.session.commit()

    add_response = client.post("/friends/add/chef_target", follow_redirects=False)
    remove_response = client.post("/friends/remove/chef_target", follow_redirects=False)
    page_response = client.get("/friends", follow_redirects=False)

    assert add_response.status_code in (302, 401)
    assert remove_response.status_code in (302, 401)
    assert page_response.status_code in (302, 401)

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_add_friend_success_duplicate_and_self_are_handled_safely():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        viewer = _create_user("viewer")
        target = _create_user("target")
        db.session.commit()

    _login(client, viewer.id)

    success = client.post("/friends/add/target", follow_redirects=False)
    duplicate = client.post("/friends/add/target", follow_redirects=True)
    self_response = client.post("/friends/add/viewer", follow_redirects=True)

    assert success.status_code == 302
    assert duplicate.status_code == 200
    assert "already friends" in duplicate.data.decode("utf-8").lower()
    assert self_response.status_code == 200
    assert "cannot add yourself" in self_response.data.decode("utf-8").lower()

    with app.app_context():
        friendships = Friendship.query.all()
        assert len(friendships) == 1
        assert (friendships[0].user_id, friendships[0].friend_id) == tuple(sorted((viewer.id, target.id)))
        db.session.remove()
        db.drop_all()


def test_remove_friend_success_and_missing_friendship_are_safe():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        viewer = _create_user("viewer")
        target = _create_user("target")
        viewer.add_friend(target)
        db.session.commit()

    _login(client, viewer.id)
    removed = client.post("/friends/remove/target", follow_redirects=True)
    missing = client.post("/friends/remove/target", follow_redirects=True)

    assert removed.status_code == 200
    assert "removed target from your friends" in removed.data.decode("utf-8").lower()
    assert missing.status_code == 200
    assert "were not friends" in missing.data.decode("utf-8").lower()

    with app.app_context():
        assert Friendship.query.count() == 0
        db.session.remove()
        db.drop_all()


def test_friends_page_renders_expected_content():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        viewer = _create_user("viewer")
        friend = _create_user("friend_user")
        viewer.add_friend(friend)
        db.session.commit()

    _login(client, viewer.id)
    response = client.get("/friends")
    body = response.data.decode("utf-8")

    assert response.status_code == 200
    assert "My Friends" in body
    assert "friend_user" in body
    assert 'href="/profile/friend_user"' in body
    assert "Remove Friend" in body

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_profile_blog_recipe_and_header_show_friend_controls_and_links():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        viewer = _create_user("viewer")
        author = _create_user("author")
        friend = _create_user("friend_author")
        viewer.add_friend(friend)
        db.session.flush()

        blog_post = BlogPost(
            user_id=author.id,
            title="Author Blog",
            summary="Summary",
            content="Content",
        )
        friend_blog_post = BlogPost(
            user_id=friend.id,
            title="Friend Blog",
            summary="Summary",
            content="Content",
        )
        recipe = Recipe(
            title="Author Recipe",
            author_id=author.id,
            instructions="Cook it.",
            ingredients="Eggs",
        )
        friend_recipe = Recipe(
            title="Friend Recipe",
            author_id=friend.id,
            instructions="Cook it.",
            ingredients="Milk",
        )
        db.session.add_all([blog_post, friend_blog_post, recipe, friend_recipe])
        db.session.commit()

    _login(client, viewer.id)

    header_response = client.get("/")
    header_body = header_response.data.decode("utf-8")
    assert header_response.status_code == 200
    assert 'href="/friends"' in header_body

    profile_response = client.get("/profile/author")
    profile_body = profile_response.data.decode("utf-8")
    assert profile_response.status_code == 200
    assert "Friends" in profile_body
    assert "Add Friend" in profile_body

    blog_list = client.get("/blog")
    blog_list_body = blog_list.data.decode("utf-8")
    assert blog_list.status_code == 200
    assert 'href="/profile/author"' in blog_list_body
    assert 'href="/profile/friend_author"' in blog_list_body
    assert "Add Friend" in blog_list_body
    assert "Remove Friend" in blog_list_body

    blog_detail = client.get(f"/blog/{blog_post.slug}")
    blog_detail_body = blog_detail.data.decode("utf-8")
    assert blog_detail.status_code == 200
    assert 'href="/profile/author"' in blog_detail_body
    assert "Add Friend" in blog_detail_body

    recipes_page = client.get("/recipes")
    recipes_body = recipes_page.data.decode("utf-8")
    assert recipes_page.status_code == 200
    assert 'href="/profile/author"' in recipes_body or 'href="/profile/friend_author"' in recipes_body
    assert "Add Friend" in recipes_body or "Remove Friend" in recipes_body

    recipe_detail = client.get(f"/recipes/{recipe.id}-{recipe.slug}")
    recipe_detail_body = recipe_detail.data.decode("utf-8")
    assert recipe_detail.status_code == 200
    assert 'href="/profile/author"' in recipe_detail_body
    assert "Add Friend" in recipe_detail_body

    logged_out_client = app.test_client()
    logged_out_header = logged_out_client.get("/")
    assert 'href="/friends"' not in logged_out_header.data.decode("utf-8")

    with app.app_context():
        db.session.remove()
        db.drop_all()
