import requests, json
from urllib3.exceptions import InsecureRequestWarning
import time

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


class Http:
    POST = "post"
    GET = "get"
    PUT = "put"
    DELETE = "delete"

    def __init__(self, address):
        self.address = address
        self.TOKEN = None

    def login_signup(self, method, username, password):
        data = {"username": username, "password": password}
        r = self.send(Http.POST, method, data=data)
        if r.status_code == 200:
            if method == "login":
                self.TOKEN = r.json()["Token"]
            return True
        else:
            return False

    def login(self, username, password):
        return self.login_signup("login", username, password)

    def register(self, username, password):
        return self.login_signup("register", username, password)

    def del_user(self):
        path = "delete_user"
        r = self.auth_send(Http.DELETE, path)
        if r.status_code != 200:
            return False
        return True

    def logout(self):
        path = "logout"
        r = self.auth_send(Http.POST, path)
        if r.status_code != 200:
            return False
        return True

    def mply_details(self, pos=None):
        path = "details"
        if pos:
            path += "/" + str(pos)
        r = self.monopoly_send(Http.GET, path)
        if r.status_code == 404:
            return -1
        elif r.status_code != 200:
            return False
        else:
            return r.json()

    def monopoly_send(self, method, path, data=None):
        path = "monopoly/" + path
        r = self.auth_send(method, path, data)
        return r

    def auth_send(self, method, path, data=None):
        if not self.TOKEN:
            return Response(400, "Please Login")

        headers = {"Authorization": "Bearer " + self.TOKEN}
        r = self.send(method, path, data, headers=headers)
        return r

    def send(self, method, path, data=None, headers={}):
        url = self.address + "/" + path
        r = None

        if method == "post":
            r = requests.post(url, json=data, headers=headers, verify=False)
        elif method == "put":
            r = requests.put(url, json=data, headers=headers, verify=False)
        elif method == "get":
            r = requests.get(url, headers=headers, verify=False)
        elif method == "delete":
            r = requests.delete(url, headers=headers, verify=False)
        else:
            return "INVALID REQUEST"
        return r


class Response:
    def __init__(self, code, body):
        self.status_code = code


if __name__ == "__main__":
    app = Http("https://localhost:5000")
    print(app.register("test", "test"))
    print(app.login("test", "test"))
    print(app.mply_details(1))
    print(app.logout())