import modal
from modal import Stub, Image, forward

import subprocess as sp
import sys
import io
import select

import shutil

import os

from typing import IO, Dict, Tuple, Optional


image_rmk_train = (
    Image.debian_slim()
    .apt_install("git", "soundstretch", "ffmpeg")
    .pip_install("pygit2==1.12.2")
    .run_commands(
        "git clone --branch 5 https://github.com/BlitzNCS/Demucs2.git",
        #"git clone https://github.com/BlitzNCS/Demucs2.git",
        #"ls -R",
        "pip install -r Demucs2/requirements.txt",
        "pip install -e Demucs2/",
    )
)

# Define the Modal Stub
stub = Stub("rmk-tiny-test-train", image=image_rmk_train)

output_vol = modal.Volume.from_name("remuse-kit-train-test")

dset_vol = modal.Volume.from_name("rmk-tiny-test-dset")



@stub.function(mounts=[modal.Mount.from_local_dir("C:\\Demucs2\\conf", remote_path="/copy_path/conf"), modal.Mount.from_local_dir("C:\\Demucs2\\demucs", remote_path="/copy_path/demucs")], gpu = "any", volumes={"/outputs": output_vol, "/rmk-tiny-test-dset": dset_vol})
def commence():

    copy_files()

    import subprocess as sp
    
    #cmd = ["python3", "-m", "dora", "run", "dset=rmk-tiny-test"]



    os.chdir("/Demucs2")
    cmd = ["dora", "run", "-d", "dset='rmk_tiny_test'"]

    p = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, text=False)
    copy_process_streams(p)
    p.wait()
    if p.returncode != 0:
        print("Command failed, something went wrong.")



def copy_files():
    # Set the paths for the source and destination directories
    copy_path = "/copy_path"
    demucs2_path = "/Demucs2"

    # Set the file paths for the files to be copied and replaced
    rmk_tiny_test_path = os.path.join(copy_path, "conf/dset/rmk_tiny_test.yaml")
    main_conf_path = os.path.join(copy_path, "conf/config.yaml")
    train_path = os.path.join(copy_path, "demucs/train.py")

    # Set the destination file paths
    rmk_tiny_test_dest = os.path.join(demucs2_path, "conf/dset/rmk_tiny_test.yaml")
    main_conf_dest = os.path.join(demucs2_path, "conf/config.yaml")
    train_dest = os.path.join(demucs2_path, "demucs/train.py")

    # Create the destination directories if they don't exist
    os.makedirs(os.path.dirname(rmk_tiny_test_dest), exist_ok=True)
    os.makedirs(os.path.dirname(main_conf_dest), exist_ok=True)
    os.makedirs(os.path.dirname(train_dest), exist_ok=True)

    # Copy and replace the files
    shutil.copy2(rmk_tiny_test_path, rmk_tiny_test_dest)
    shutil.copy2(main_conf_path, main_conf_dest)
    shutil.copy2(train_path, train_dest)

    print("Files copied and replaced successfully.")


@stub.local_entrypoint()
def main():

    commence.remote()


def copy_process_streams(process: sp.Popen):
    def raw(stream: Optional[IO[bytes]]) -> IO[bytes]:
        assert stream is not None
        if isinstance(stream, io.BufferedIOBase):
            stream = stream.raw
        return stream

    p_stdout, p_stderr = raw(process.stdout), raw(process.stderr)
    stream_by_fd: Dict[int, Tuple[IO[bytes], IO[str]]] = {
        p_stdout.fileno(): (p_stdout, sys.stdout.buffer),  # Use sys.stdout.buffer
        p_stderr.fileno(): (p_stderr, sys.stderr.buffer),  # Use sys.stderr.buffer
    }
    fds = list(stream_by_fd.keys())

    while fds:
        # `select` syscall will wait until one of the file descriptors has content.
        ready, _, _ = select.select(fds, [], [])
        for fd in ready:
            p_stream, std_buffer = stream_by_fd[fd]
            raw_buf = p_stream.read(2 ** 16)
            if not raw_buf:
                fds.remove(fd)
                continue
            std_buffer.write(raw_buf)  # Write bytes directly to std_buffer
            std_buffer.flush()