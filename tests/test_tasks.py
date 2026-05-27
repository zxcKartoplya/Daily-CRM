from datetime import date


TODAY = date.today().isoformat()


class TestListTasks:
    def test_admin_can_list_tasks(self, client, admin_headers, employee_user):
        response = client.get("/api/admin/tasks", headers=admin_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_employee_cannot_list_tasks(self, client, employee_headers):
        response = client.get("/api/admin/tasks", headers=employee_headers)
        assert response.status_code == 403

    def test_unauthenticated_cannot_list_tasks(self, client):
        response = client.get("/api/admin/tasks")
        assert response.status_code == 401

    def test_filter_tasks_by_user_id(self, client, admin_headers, employee_user):
        client.post("/api/admin/tasks", headers=admin_headers, json={
            "user_id": employee_user.id,
            "date": TODAY,
            "description": "Task for filter test",
        })
        response = client.get(f"/api/admin/tasks?user_id={employee_user.id}", headers=admin_headers)
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) == 1
        assert tasks[0]["user_id"] == employee_user.id


class TestCreateTask:
    def test_admin_creates_task(self, client, admin_headers, employee_user):
        response = client.post("/api/admin/tasks", headers=admin_headers, json={
            "user_id": employee_user.id,
            "date": TODAY,
            "description": "Write unit tests",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["description"] == "Write unit tests"
        assert data["user_id"] == employee_user.id
        assert "id" in data

    def test_create_task_for_nonexistent_user_returns_404(self, client, admin_headers):
        response = client.post("/api/admin/tasks", headers=admin_headers, json={
            "user_id": 99999,
            "date": TODAY,
            "description": "Should fail",
        })
        assert response.status_code == 404

    def test_employee_cannot_create_task(self, client, employee_headers, employee_user):
        response = client.post("/api/admin/tasks", headers=employee_headers, json={
            "user_id": employee_user.id,
            "date": TODAY,
            "description": "Not allowed",
        })
        assert response.status_code == 403


class TestGetTask:
    def test_get_existing_task(self, client, admin_headers, employee_user):
        created = client.post("/api/admin/tasks", headers=admin_headers, json={
            "user_id": employee_user.id,
            "date": TODAY,
            "description": "Get me",
        }).json()

        response = client.get(f"/api/admin/tasks/{created['id']}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["description"] == "Get me"

    def test_get_nonexistent_task_returns_404(self, client, admin_headers):
        response = client.get("/api/admin/tasks/99999", headers=admin_headers)
        assert response.status_code == 404


class TestUpdateTask:
    def test_admin_updates_task(self, client, admin_headers, employee_user):
        created = client.post("/api/admin/tasks", headers=admin_headers, json={
            "user_id": employee_user.id,
            "date": TODAY,
            "description": "Original",
        }).json()

        response = client.put(f"/api/admin/tasks/{created['id']}", headers=admin_headers, json={
            "user_id": employee_user.id,
            "date": TODAY,
            "description": "Updated",
        })
        assert response.status_code == 200
        assert response.json()["description"] == "Updated"

    def test_update_nonexistent_task_returns_404(self, client, admin_headers, employee_user):
        response = client.put("/api/admin/tasks/99999", headers=admin_headers, json={
            "user_id": employee_user.id,
            "date": TODAY,
            "description": "Ghost",
        })
        assert response.status_code == 404


class TestDeleteTask:
    def test_admin_deletes_task(self, client, admin_headers, employee_user):
        created = client.post("/api/admin/tasks", headers=admin_headers, json={
            "user_id": employee_user.id,
            "date": TODAY,
            "description": "To be deleted",
        }).json()

        response = client.delete(f"/api/admin/tasks/{created['id']}", headers=admin_headers)
        assert response.status_code == 204

        get_response = client.get(f"/api/admin/tasks/{created['id']}", headers=admin_headers)
        assert get_response.status_code == 404

    def test_delete_nonexistent_task_returns_404(self, client, admin_headers):
        response = client.delete("/api/admin/tasks/99999", headers=admin_headers)
        assert response.status_code == 404
