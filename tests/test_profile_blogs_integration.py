from sqlalchemy.pool import StaticPool

from app import create_app
from services.db import db
from services.models import BlogPost, User


def _make_app(seed_demo: bool = False):
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
        seed_demo=seed_demo,
    )


def test_model_author_relationship_persists():
    app = _make_app(seed_demo=False)
    with app.app_context():
        author = User(username="author_user", password_hash="placeholder")
        db.session.add(author)
        db.session.flush()
        post = BlogPost(
            user_id=author.id,
            title="Author Post",
            summary="Summary",
            content="Content",
        )
        db.session.add(post)
        db.session.commit()

        saved = BlogPost.query.filter_by(title="Author Post").first()
        assert saved is not None
        assert saved.author is not None
        assert saved.author.username == "author_user"
        assert any(p.id == saved.id for p in author.blog_posts)

        db.session.remove()
        db.drop_all()


def test_seed_blogs_are_assigned_to_seed_user():
    app = _make_app(seed_demo=True)
    with app.app_context():
        demo_user = User.query.filter_by(username="demo_user").first()
        posts = BlogPost.query.all()

        assert demo_user is not None
        assert posts
        assert all(post.user_id is not None for post in posts)
        assert all(post.user_id == demo_user.id for post in posts)

        db.session.remove()
        db.drop_all()


def test_blog_pages_link_to_author_profile():
    app = _make_app(seed_demo=False)
    client = app.test_client()
    with app.app_context():
        author = User(username="blogger", password_hash="placeholder")
        db.session.add(author)
        db.session.flush()
        post = BlogPost(
            user_id=author.id,
            title="Linked Post",
            summary="Linked summary",
            content="Linked content",
        )
        db.session.add(post)
        db.session.commit()
        slug = post.slug

    blog_list_response = client.get("/blog")
    blog_detail_response = client.get(f"/blog/{slug}")
    list_body = blog_list_response.data.decode("utf-8")
    detail_body = blog_detail_response.data.decode("utf-8")

    assert blog_list_response.status_code == 200
    assert blog_detail_response.status_code == 200
    assert 'href="/profile/blogger"' in list_body
    assert 'href="/profile/blogger"' in detail_body

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_profile_shows_recent_blogs_for_user():
    app = _make_app(seed_demo=False)
    client = app.test_client()
    with app.app_context():
        user_a = User(username="chef_a", password_hash="placeholder")
        user_b = User(username="chef_b", password_hash="placeholder")
        db.session.add_all([user_a, user_b])
        db.session.flush()
        db.session.add_all(
            [
                BlogPost(
                    user_id=user_a.id,
                    title="A1",
                    summary="A1 summary",
                    content="A1 content",
                ),
                BlogPost(
                    user_id=user_a.id,
                    title="A2",
                    summary="A2 summary",
                    content="A2 content",
                ),
                BlogPost(
                    user_id=user_b.id,
                    title="B1",
                    summary="B1 summary",
                    content="B1 content",
                ),
            ]
        )
        db.session.commit()

    response = client.get("/profile/chef_a")
    body = response.data.decode("utf-8")

    assert response.status_code == 200
    assert "Blogs" in body
    assert "A1" in body
    assert "A2" in body
    assert "B1" not in body
    assert 'href="/profile/chef_a/blogs"' in body

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_profile_blogs_route_filters_and_handles_missing_user():
    app = _make_app(seed_demo=False)
    client = app.test_client()
    with app.app_context():
        user_a = User(username="writer_a", password_hash="placeholder")
        user_b = User(username="writer_b", password_hash="placeholder")
        db.session.add_all([user_a, user_b])
        db.session.flush()
        db.session.add_all(
            [
                BlogPost(
                    user_id=user_a.id,
                    title="Writer A Post",
                    summary="Writer A summary",
                    content="Writer A content",
                ),
                BlogPost(
                    user_id=user_b.id,
                    title="Writer B Post",
                    summary="Writer B summary",
                    content="Writer B content",
                ),
            ]
        )
        db.session.commit()

    ok_response = client.get("/profile/writer_a/blogs")
    ok_body = ok_response.data.decode("utf-8")
    missing_response = client.get("/profile/no_such_user/blogs")

    assert ok_response.status_code == 200
    assert "Writer A Post" in ok_body
    assert "Writer B Post" not in ok_body
    assert missing_response.status_code == 404

    with app.app_context():
        db.session.remove()
        db.drop_all()
