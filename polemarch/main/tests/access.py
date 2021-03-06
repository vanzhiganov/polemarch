import json
from datetime import timedelta
from django.utils.timezone import now
from ..models import Inventory, History, Project
from .inventory import _ApiGHBaseTestCase


class ApiAccessTestCase(_ApiGHBaseTestCase):
    def _ensure_rights(self, url, data, list_urls, single_url,
                       get_code, set_code, error_code, count):
        self.assertEqual(self.get_result("get", url)["count"], count)
        self.get_result("get", single_url, get_code)

        # and with his satellites
        for list_url in list_urls:
            gr_lists_url = single_url + list_url + "/"
            # passing -1 as id of element, because we just want to check that
            # it actually trying to do specified action without any access
            # violation errors
            self.get_result("post", gr_lists_url, error_code,
                            data=json.dumps([-1]))
            self.get_result("put", gr_lists_url, error_code,
                            data=json.dumps([-1]))
            self.get_result("delete", gr_lists_url, error_code,
                            data=json.dumps([-1]))

        self.get_result("delete", single_url, set_code)

    def _ensure_no_rights(self, url, data, list_urls, single_url):
        self._ensure_rights(url, data, list_urls, single_url, 404, 404, 404, 0)

    def _ensure_have_rights(self, url, data, list_urls, single_url):
        self._ensure_rights(url, data, list_urls, single_url, 200, 204, 200, 1)
        # recreate object because we also test above, that we have delete right
        id, single_url = self._create_subject(url, data)
        return id, single_url

    def _create_subject(self, url, data):
        id = self.mass_create(url, [data], *data.keys())[0]
        single_url = url + "{}/".format(id)
        return id, single_url

    def _test_access_rights(self, url, data, list_urls=[]):
        self.change_identity()
        nonprivileged_user1 = self.user
        id, single_url = self._create_subject(url, data)
        # owner have all rights
        id, single_url = self._ensure_have_rights(url, data, list_urls,
                                                  single_url)
        # another user can't do anything with this object
        self.change_identity()
        nonprivileged_user2 = self.user
        self._ensure_no_rights(url, data, list_urls, single_url)
        # we can add rights for user
        self.user = nonprivileged_user1
        self.get_result("post", single_url + "permissions/", 200,
                        data=json.dumps([nonprivileged_user2.id]))
        perms = self.get_result("get", single_url + "permissions/", 200)
        self.assertIn(nonprivileged_user2.id, perms)

        self.user = nonprivileged_user2
        id, single_url = self._ensure_have_rights(url, data, list_urls,
                                                  single_url)
        # we can remove rights for user
        self.get_result("post", single_url + "permissions/", 200,
                        data=json.dumps([nonprivileged_user1.id]))
        self.get_result("delete", single_url + "permissions/", 200,
                        data=json.dumps([nonprivileged_user1.id]))
        self.user = nonprivileged_user1
        self._ensure_no_rights(url, data, list_urls, single_url)
        # superuser can do anything
        self.change_identity(is_super_user=True)
        id, single_url = self._ensure_have_rights(url, data, list_urls,
                                                  single_url)
        self.get_result("delete", single_url, 204)

    def test_hosts_access_rights(self):
        self._test_access_rights("/api/v1/hosts/",
                                 dict(name="127.0.1.1",
                                      type="HOST",
                                      vars={}))

    def test_groups_access_rights(self):
        self._test_access_rights("/api/v1/groups/",
                                 dict(name="one", vars={}),
                                 ["hosts"])
        self._test_access_rights("/api/v1/groups/",
                                 dict(name="one", vars={}, children=True),
                                 ["groups"])

    def test_inventories_access_rights(self):
        self._test_access_rights("/api/v1/inventories/",
                                 dict(name="Inv1", vars={}),
                                 ["hosts", "groups"])

    def test_projects_access_rights(self):
        self._test_access_rights("/api/v1/projects/",
                                 dict(name="Prj3",
                                      repository="git@ex.us:dir/rep3.git",
                                      vars=dict(repo_type="TEST")),
                                 ["inventories"])

    def test_periodic_tasks_access_rights(self):
        self.change_identity()
        data = [dict(name="Prj1", repository="git@ex.us:dir/rep3.git",
                     vars=dict(repo_type="TEST"))]
        project_id = self.mass_create("/api/v1/projects/", data,
                                      "name", "repository")[0]
        perm_url = "/api/v1/projects/" + str(project_id) + "/permissions/"

        url = "/api/v1/periodic-tasks/"
        inventory = Inventory.objects.create()
        data = dict(mode="p1.yml",
                    schedule="10",
                    type="INTERVAL",
                    project=project_id,
                    inventory=inventory.id)

        nonprivileged_user1 = self.user
        id, single_url = self._create_subject(url, data)
        # owner have all rights
        id, single_url = self._ensure_have_rights(url, data, [], single_url)
        # another user can't do anything with this object
        self.change_identity()
        nonprivileged_user2 = self.user
        self._ensure_no_rights(url, data, [], single_url)
        # we can add rights for user
        self.user = nonprivileged_user1
        self.change_identity(is_super_user=True)
        self.get_result("post", perm_url, 200,
                        data=json.dumps([nonprivileged_user2.id]))
        self.user = nonprivileged_user2
        id, single_url = self._ensure_have_rights(url, data, [],
                                                  single_url)
        # we can remove rights for user
        self.get_result("post", perm_url, 200,
                        data=json.dumps([nonprivileged_user1.id]))
        self.get_result("delete", perm_url, 200,
                        data=json.dumps([nonprivileged_user1.id]))
        self.user = nonprivileged_user1
        self._ensure_no_rights(url, data, [], single_url)
        # superuser can do anything
        self.change_identity(is_super_user=True)
        id, single_url = self._ensure_have_rights(url, data, [],
                                                  single_url)
        # cleanup
        self.get_result("delete", single_url)
        self.get_result("delete", "/api/v1/projects/{}/".format(project_id))
        inventory.delete()

    def test_history_access_rights(self):
        def_url = "/api/v1/history/"
        self.change_identity()
        nonprivileged_user1 = self.user
        data = [dict(name="Prj1", repository="git@ex.us:dir/rep3.git",
                     vars=dict(repo_type="TEST"))]
        project_id = self.mass_create("/api/v1/projects/", data,
                                      "name", "repository")[0]
        inventory = Inventory.objects.create()
        history_kwargs = dict(project=Project.objects.get(pk=project_id),
                              mode="setup", kind="MODULE",
                              raw_inventory="inventory", raw_stdout="text",
                              inventory=inventory, status="OK",
                              start_time=now() - timedelta(hours=15),
                              stop_time=now() - timedelta(hours=14))
        history = History.objects.create(**history_kwargs)
        result = self.get_result("get", def_url+"{}/".format(history.id))
        self.assertEqual(result['id'], history.pk)
        self.change_identity()
        nonprivileged_user2 = self.user
        self.get_result("get", def_url+"{}/".format(history.id), 404)
        self.user = nonprivileged_user1
        perm_url = "/api/v1/projects/" + str(project_id) + "/permissions/"
        self.get_result("post", perm_url, 200,
                        data=json.dumps([nonprivileged_user2.id]))
        self.user = nonprivileged_user2
        result = self.get_result("get", def_url+"{}/".format(history.id))
        self.assertEqual(result['id'], history.pk)
        self.user = nonprivileged_user1
        result = self.get_result("get", def_url+"{}/".format(history.id))
        self.assertEqual(result['id'], history.pk)

    def test_template_access_rights(self):
        def_url = "/api/v1/templates/"
        self.change_identity()
        nonprivileged_user1 = self.user
        data = [dict(name="Prj1", repository="git@ex.us:dir/rep3.git",
                     vars=dict(repo_type="TEST"))]
        project_id = self.mass_create("/api/v1/projects/", data,
                                      "name", "repository")[0]
        inv = self.get_result("post", "/api/v1/inventories/", 201,
                              data=dict(name="test_inv_tmplt_access"))
        def_kwargs = json.dumps(dict(
            name="test_tmplt",
            kind="Task",
            data=dict(
                playbook="test.yml",
                project=project_id,
                inventory=inv['id'],
                vars=dict(
                    connection="paramiko",
                    tags="update",
                )
            )
        ))
        result = self.get_result("post", def_url, 201, data=def_kwargs)
        tmplt_id = result['id']
        result = self.get_result("get", def_url + "{}/".format(tmplt_id))
        self.assertEqual(result['id'], tmplt_id)
        self.change_identity()
        nonprivileged_user2 = self.user
        self.get_result("get", def_url + "{}/".format(tmplt_id), 404)
        self.user = nonprivileged_user1
        perm_data = json.dumps([nonprivileged_user2.id])
        perm_url = "/api/v1/projects/" + str(project_id) + "/permissions/"
        self.get_result("post", perm_url, 200, data=perm_data)
        perm_url = "/api/v1/inventories/" + str(inv['id']) + "/permissions/"
        self.get_result("post", perm_url, 200, data=perm_data)
        self.user = nonprivileged_user2
        result = self.get_result("get", def_url + "{}/".format(tmplt_id))
        self.assertEqual(result['id'], tmplt_id)
        self.user = nonprivileged_user1
        result = self.get_result("get", def_url + "{}/".format(tmplt_id))
        self.assertEqual(result['id'], tmplt_id)
