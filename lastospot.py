#!/usr/bin/env python3


# Copyright © 2018 Jordi Loyzaga <jordi@loyzaga.net>

# This work is free. You can redistribute it and/or modify it under the
# terms of the Do What The Fuck You Want To Public License, Version 2,
# as published by Sam Hocevar. See http://www.wtfpl.net/ for more details.

from base64 import b64encode
from json import dumps
from os import environ
from time import sleep
from urllib.parse import urlparse, parse_qs
from uuid import uuid4
from webbrowser import open as wsopen

import http.server
import requests
import socketserver

try:
    SPOT_ID = environ["SPOT_ID"]
    SPOT_SECRET = environ["SPOT_SECRET"]
    LAST_KEY = environ["LAST_KEY"]
    LAST_USER = environ["LAST_USER"]

except KeyError:
    print("Missing env parameter.")
    exit(1)


SPOT_AUTH = "https://accounts.spotify.com"
SPOT_ROOT = "https://api.spotify.com/v1"
LAST_ROOT = "http://ws.audioscrobbler.com/2.0"


TEMPLATE = """
<html>
    <head>
        <title>{status}</title>
    </head>
    <body>
        <p>{status}</p>
        <p>You can close this window now.</p>
    <script>
        window.open('', '_self', ''); window.close();
    </script
    </body>
</html>
"""


# [spotify logic]
class SpotifyCallbakHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        if self.server.logging:
            http.server.SimpleHTTPRequestHandler.log_message(self, format, *args)

    def do_GET(self):
        global DATA
        DATA = parse_qs(urlparse(self.path).query)
        status = b'User succesfully authenticated'

        if "error" in DATA:
            status = b'There was a problem authenticating the user.'
            DATA = "error"

        self.send_response(200)  # OK
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        # Display the POST variables.
        msg = TEMPLATE.format(status=status)
        self.status = msg.encode()
        self.wfile.write(self.status)


class SpotifyServer(socketserver.TCPServer):
    allow_reuse_address = True
    logging = False


def auth_spot(server):
    url = SPOT_AUTH + "/authorize"
    payload = {
        "client_id": SPOT_ID,
        "response_type": "code",
        "redirect_uri": "http://localhost:9292",
        "state": uuid4().hex,
        "scope": "playlist-modify-public playlist-modify-private user-read-private",
    }

    s = requests.Session()
    r = requests.Request("GET", url, params=payload).prepare()
    wsopen(r.url)

    server.handle_request()
    return


def get_spot_token(code):
    url = SPOT_AUTH + "/api/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": "http://localhost:9292"
    }

    b64auth = '{0}:{1}'.format(SPOT_ID, SPOT_SECRET).encode()
    b64auth = b64encode(b64auth).decode()
    headers = {"Authorization": "Basic " + b64auth}

    r = requests.post(url, data=payload, headers=headers)
    r = r.json()
    return r['access_token']


def get_user(token):
    url = SPOT_ROOT + "/me"
    headers = {"Authorization": "Bearer " + token}

    r = requests.get(url, headers=headers)
    r = r.json()
    return r["id"]


def init_spot(server):
    auth_spot(server)

    if DATA == "error":
        print("The app was denied permission, please try again.")
        exit(1)
    else:
        print("\n- App granted permissions.")

    code = DATA["code"]
    token = get_spot_token(code)
    user = get_user(token)
    print("\n- Authenticated as '{0}'.".format(user))
    return token, user


def search_uris(token, tracks):
    url = SPOT_ROOT + "/search"

    headers = {
        "Authorization": "Bearer " + token,
        "market": "from_token"
    }

    params = {
        "market": "from_token",
        "type": "track",
        "limit": "1"
    }

    uris = []
    for track in tracks:
        params["q"] = track["name"] + " " + track["artist"]
        r = requests.get(url, params=params, headers=headers)
        status = r.status_code
        r = r.json()

        if len(r["tracks"]["items"]) != 0:
            uri = r["tracks"]["items"][0]["uri"]
            uris.append(uri)
            print("\t{0} --- {1}: {2}".format(status, track["name"], uri))

        else:
            print("\n\t{0} --- {1}: {2}\n".format("404", track["name"], "not found"))
        sleep(.2)

    return uris


def get_playlist(token, user):
    print("\n- Checking for  previous playslist...")
    url = SPOT_ROOT + "/users/{0}/playlists".format(user)

    headers = {
        "Authorization": "Bearer " + token,
        "market": "from_token"
    }

    params = {
        "limit": "50"
    }

    r = requests.get(url, params=params, headers=headers)
    r = r.json()
    playlists = r["items"]

    uri = None
    for pl in playlists:
        if pl["name"] == "top scrobbles for last moth":
            print("\n- Previous playlist found.")
            uri = pl["uri"]
            print("\n- This will empty your previous playlist.")
            ch = input("\n- Do you want to continue? [N/y]")
            if ch not in ['Y', 'y']:
                print("\n- Exiting...")
                exit(0)
            clear_playlist(token, user, uri)
            break

    if uri is None:
        print("\n- No previous playlist found.")
        print("\n- Creating new playslit...")
        uri = create_playlist(token, user)
    return uri


def create_playlist(token, user):
    url = SPOT_ROOT + "/users/{0}/playlists".format(user)
    headers = {
        "Authorization": "Bearer " + token,
        "market": "from_token"
    }

    payload = {
        "name": "top scrobbles for last moth",
        "description": "Your top lastfm scrobbles for the last month (autogenerated)."
    }

    payload = dumps(payload)

    r = requests.post(url, data=payload, headers=headers)
    uri = r.json()['uri']
    return uri


def clear_playlist(token, user, uri):
    pid = uri.split(":")[-1]
    url = SPOT_ROOT + "/users/{0}/playlists/{1}/tracks".format(user, pid)

    headers = {
        "Authorization": "Bearer " + token,
    }

    params = {
        "fields": "items(track(uri))"
    }

    r = requests.get(url, params=params, headers=headers)
    tracks = r.json()['items']

    uris = [track['track'] for track in tracks]

    data = {
        "tracks": uris
    }

    data = dumps(data)

    print("\n- Clearing previous playlist...")
    r = requests.delete(url, data=data, headers=headers)
    print("\n- Previous playlist cleared.")
    return


def add_tracks(token, user, uri, tracks):
    pid = uri.split(":")[-1]
    url = SPOT_ROOT + "/users/{0}/playlists/{1}/tracks".format(user, pid)

    headers = {
        "Authorization": "Bearer " + token,
    }

    payload = {
        "uris": tracks
    }

    payload = dumps(payload)
    r = requests.post(url, data=payload, headers=headers)
    print("\n- Playlist updated.")
    return

# [lastfm logic]


def get_chart():
    params = {"period": "1month",
              "limit": "30"}

    params = ["&{0}={1}".format(k, v) for k, v in params.items()]
    params = "".join(params)

    url = LAST_ROOT + "/?method=user.gettoptracks&user={0}&api_key={1}{2}&format=json".format(LAST_USER, LAST_KEY, params)
    r = requests.get(url)
    return r.json()


def get_tracks():
    chart = get_chart()
    chart = chart["toptracks"]["track"]
    tracks = []
    for track in chart:
        rank = track["@attr"]["rank"]
        name = track["name"]
        artist = track["artist"]["name"]

        tracks.append({"rank": rank, "name": name, "artist": artist})

    return tracks


def print_tracks(tracks):
    for track in tracks:
        print("\t{rank}.- {name} - {artist}".format(**track))

# [main thing]


def main():
    Handler = SpotifyCallbakHandler
    server = SpotifyServer(('localhost', 9292), Handler)

    token, user = init_spot(server)

    print("\n- Getting tracks from previous month...")
    tracks = get_tracks()

    print("\n- Tracks to be searched:\n")
    print_tracks(tracks)

    print("\n- Searching Spotify URIs...\n")
    uris = search_uris(token, tracks)
    print("\n- '{0}' of '{1}' tracks found on Spotify.".format(len(uris), len(tracks)))

    p_uri = get_playlist(token, user)
    print("\n- Adding '{0}' in-order tracks to new playslit.".format(len(uris)))
    add_tracks(token, user, p_uri, uris)
    exit(9)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n- Exiting...")
        exit(0)
