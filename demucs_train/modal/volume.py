import modal
import os
from modal import Stub



# Define the Modal Stub
stub = Stub("remuse-kit-interface-debug")

stub.volume = modal.Volume.from_name("remuse-kit-volume")





@stub.function(volumes={"/rmk-train": modal.Volume.from_name("remuse-kit-train-test")})
def some_func():
    os.listdir("/rmk-train")