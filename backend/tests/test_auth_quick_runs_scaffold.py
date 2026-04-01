def test_auth_login_creates_distinct_quick_runs_project_per_user(client, monkeypatch):
    import config
    import dependencies
    from repositories.sqlite import SqliteUserRepository

    monkeypatch.setenv("WORKFLOWUI_AUTH_ENABLED", "true")
    config._AUTH_CONFIG = None
    dependencies._user_repo = SqliteUserRepository(dependencies._db_path)

    admin_login = client.post("/auth/login", json={"username": "admin", "password": "admin"})
    assert admin_login.status_code == 200
    admin_user = admin_login.json()["user"]
    admin_quick_id = admin_user.get("quick_runs_project_id")
    assert isinstance(admin_quick_id, str) and admin_quick_id

    create_user = client.post(
        "/admin/users",
        json={
            "username": "alice",
            "password": "alice",
            "role": "user",
            "allow_all_apps": False,
        },
    )
    assert create_user.status_code == 200

    project_repo = dependencies.get_db()[4]
    admin_quick = project_repo.get_project(admin_quick_id)
    assert admin_quick is not None
    assert admin_quick.owner_user_id == admin_user["id"]

    cfg_admin = client.get("/config")
    assert cfg_admin.status_code == 200
    assert cfg_admin.json().get("quick_runs_project_id") == admin_quick_id

    logout = client.post("/auth/logout")
    assert logout.status_code == 200

    user_login = client.post("/auth/login", json={"username": "alice", "password": "alice"})
    assert user_login.status_code == 200
    user_data = user_login.json()["user"]
    user_quick_id = user_data.get("quick_runs_project_id")
    assert isinstance(user_quick_id, str) and user_quick_id
    assert user_quick_id != admin_quick_id

    user_quick = project_repo.get_project(user_quick_id)
    assert user_quick is not None
    assert user_quick.owner_user_id == user_data["id"]

    cfg_user = client.get("/config")
    assert cfg_user.status_code == 200
    assert cfg_user.json().get("quick_runs_project_id") == user_quick_id
