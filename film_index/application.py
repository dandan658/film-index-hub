"""The only Flask application in Film Index."""
from flask import Flask

app = Flask('film_index', static_folder=None)

