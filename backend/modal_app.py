# backend/modal_app.py
import os
from modal import App, Image, Mount, asgi_app

# This tells Modal to mount all the files in our local `backend` directory
# to a directory called `/app` inside the container.
mount = Mount.from_local_dir(".", remote_path="/app")

# Define a container image and install our dependencies from requirements.txt
# We specify the working directory to be the `/app` folder we just mounted.
image = Image.debian_slim().pip_install_from_requirements(
    "requirements.txt"
).workdir("/app")

# Create a Modal App, and specify that we want to use our new image
modal_app = App("pdf-playground-backend", image=image)

# Import the FastAPI app object from main.py
# This now works because main.py is in our working directory
from main import app as fastapi_app

# Define the web endpoint, and attach our mount
@modal_app.function(mounts=[mount])
@asgi_app()
def web():
    return fastapi_app