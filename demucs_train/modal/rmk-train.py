import modal
import os
from modal import Stub



# Define the Modal Stub
stub = Stub("remuse-kit-interface-debug",
            image=modal.Image.debian_slim()
          .apt_install("ffmpeg", "soundstretch")  # Any other system dependencies Demucs might need
          .pip_install("torch", "demucs"))

stub.volume = modal.Volume.from_name("remuse-kit-volume")





@stub.function(volumes={"/rmk-train": modal.Volume.from_name("remuse-kit-train-test")})
def some_func():
    os.listdir("/rmk-train")