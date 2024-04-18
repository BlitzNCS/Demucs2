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
    .env({"TORCHAUDIO_USE_BACKEND_DISPATCHER": "1"})
    .run_commands(
        "git clone --branch 5 https://github.com/BlitzNCS/Demucs2.git",
        #"git clone https://github.com/BlitzNCS/Demucs2.git",
        #"ls -R",
        "pip install -r Demucs2/requirements.txt",
        "pip install -e Demucs2/",
    )
)

# Define the Modal Stub
stub = Stub("rmk-train", image=image_rmk_train)

output_vol = modal.Volume.from_name("remuse-kit-train-test")

dset_vol = modal.Volume.from_name("rmk-train-dset-v1-170424-1")

meta_vol = modal.Volume.from_name("rmk-train-metadata-test")



@stub.function(timeout=86400, mounts=[modal.Mount.from_local_dir("C:\\Demucs2\\conf", remote_path="/copy_path/conf"), modal.Mount.from_local_dir("C:\\Demucs2\\demucs", remote_path="/copy_path/demucs")], gpu = modal.gpu.A10G(count=2), volumes={"/outputs": output_vol, "/dset_vol": dset_vol, "/metadata": meta_vol})
def commence():

  copy_files()

  import subprocess as sp

  meta_vol.reload()

  os.environ["TORCHAUDIO_USE_BACKEND_DISPATCHER"] = "1"

  
  os.chdir("/Demucs2")
  cmd = ["dora", "run", "-d", "dset='rmk-train-dset-v1-170424-1'"]

  p = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, text=False)
  copy_process_streams(p)
  p.wait()
  if p.returncode != 0:
      print("Command failed, something went wrong.")



  cmd = ["python3", "-m", "tools.export", "9bd070ae"]

  p = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, text=False)
  copy_process_streams(p)
  p.wait()
  if p.returncode != 0:
      print("Command failed, something went wrong.")


  checkpoint_path = "./release_models/9bd070ae.th"

  checkpoint_dest = "/outputs/rmk-out-test"


  os.makedirs(checkpoint_dest, exist_ok=True)
  shutil.copy2(checkpoint_path, checkpoint_dest)

  
  meta_vol.commit()
  output_vol.commit()





def copy_files():
    # Set the paths for the source and destination directories
    copy_path = "/copy_path"
    demucs2_path = "/Demucs2"


    demucs_code_path = os.path.join(copy_path, "demucs/")
    demucs_code_dest  = os.path.join(demucs2_path, "demucs/")

    # Set the file paths for the files to be copied and replaced
    rmk_tiny_test_path = os.path.join(copy_path, "conf/dset/rmk-train-dset-v1-170424-1.yaml")
    main_conf_path = os.path.join(copy_path, "conf/config.yaml")

    train_path = os.path.join(copy_path, "demucs/train.py")
    wav_path = os.path.join(copy_path, "demucs/wav.py")


    # Set the destination file paths
    rmk_tiny_test_dest = os.path.join(demucs2_path, "conf/dset/rmk-train-dset-v1-170424-1.yaml")
    main_conf_dest = os.path.join(demucs2_path, "conf/config.yaml")

    train_dest = os.path.join(demucs2_path, "demucs/train.py")
    wav_dest = os.path.join(demucs2_path, "demucs/wav.py")


    # Create the destination directories if they don't exist
    os.makedirs(os.path.dirname(rmk_tiny_test_dest), exist_ok=True)
    os.makedirs(os.path.dirname(main_conf_dest), exist_ok=True)

    os.makedirs(os.path.dirname(train_dest), exist_ok=True)
    os.makedirs(os.path.dirname(wav_dest), exist_ok=True)


    # Copy and replace the files
    shutil.copy2(rmk_tiny_test_path, rmk_tiny_test_dest)
    shutil.copy2(main_conf_path, main_conf_dest)

    shutil.copy2(train_path, train_dest)
    shutil.copy2(wav_path, wav_dest)

    shutil.copytree(demucs_code_path, demucs_code_dest, dirs_exist_ok=True)


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