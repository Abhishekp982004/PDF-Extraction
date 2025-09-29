# modal_app.py
from modal import App, asgi_app
from main import app as fastapi_app

# Create a Modal App
modal_app = App("pdf-playground-backend")

# Define the web endpoint
@modal_app.function()
@asgi_app()
def web():
    return fastapi_app