# LastoSpot

Add your top 30 last.fm scrobbles from last month into a Spotify playlist.


### Requirements

Requires [requests](https://github.com/requests/requests).

`pip install requests`


You need to create:
* a last.fm API account [here](https://www.last.fm/api/account/create).
* a Spotify API account [here](https://beta.developer.spotify.com/dashboard/applications).

Then you need to fill in these bad boys like so:

```
export SPOT_ID='ID HERE'
export SPOT_SECRET='SECRET HERE'
export LAST_KEY="KEY HERE"
export LAST_USER="USER HERE"
```
## Usage
Finally just run the thing:

`./lastospot.py`

It'll annoy you a couple of times and then it will do it's thing.

## Caveats

Comical error handling.

No comments, no docs, you get nothing.

I just realized that the Spotify API provides listening history or whatever now, but I'm a stubborn idiot.

Use it, steal it, submit PRs, issues, whatever I don't care.