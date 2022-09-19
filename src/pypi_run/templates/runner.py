#!/usr/bin/env python3
"""
Welcome to package runner!

That's kind of a bit of over-engineering in order to run a one-shot command
from a Python package that is not necessarily installed in the system and that
you want to put in your documentation as a one-liner. For example you can use
this to create a new project instance from a project generator package.
"""

import os
from argparse import ArgumentParser, Namespace
from contextlib import contextmanager
from dataclasses import dataclass
from os import environ
from pathlib import Path
from queue import Queue
from signal import SIGTERM, signal
from subprocess import PIPE, Popen
from sys import argv, path, stderr
from tempfile import TemporaryDirectory
from threading import Thread
from time import sleep
from types import SimpleNamespace
from typing import Optional, Sequence
from urllib.parse import urlparse
from urllib.request import urlretrieve
from venv import EnvBuilder


class PackageRunnerError(Exception):
    pass


def sigterm_handler(_, __):
    raise SystemExit(1)


class Tick:
    """
    Used by the display thread to notify the main thread to re-draw a new moon
    """


@dataclass
class Done:
    """
    Sent when the venv creation is done (either successfully or as a failure).
    The builder is there to be able to run commands afterwards.
    """

    success: bool
    builder: Optional["MakerEnv"] = None


class MakerEnv(EnvBuilder):
    """
    Custom env builder that adds pip and other dependencies, largely copied
    from the Python docs.
    """

    def __init__(self, *args, **kwargs):
        self.requirements = kwargs.pop("requirements")
        super().__init__(*args, **kwargs)
        self.context = None

    def post_setup(self, context: SimpleNamespace) -> None:
        """
        Install the requirements with Pip once the setup was done
        """

        environ["VIRTUAL_ENV"] = context.env_dir
        path.append(context.env_dir)

        self.context = context

        self.install_pip()
        self.run_command(["-m", "pip", "install", *self.requirements])

    def install_script(self, url):
        """
        Underlying code to install Pip
        """

        _, _, url_path, _, _, _ = urlparse(url)
        fn = os.path.split(url_path)[-1]
        bin_path = self.context.bin_path
        dist_path = os.path.join(bin_path, fn)
        urlretrieve(url, dist_path)

        args = [self.context.env_exe, fn]
        p = Popen(args, stdout=PIPE, stderr=PIPE, cwd=bin_path)
        p.wait()

        if p.returncode:
            raise Exception(f"Error: {p.stderr.read().decode()[:1000]}")

        os.unlink(dist_path)

    def run_command(self, command_args, pipe: bool = True):
        """
        Shortcut to run the Python executable from the virtualenv
        """

        args = [self.context.env_exe, *command_args]
        p = Popen(args, stdout=PIPE if pipe else None, stderr=PIPE if pipe else None)
        p.wait()

        if p.returncode:
            if pipe:
                raise Exception(f"Error: {p.stderr.read().decode()[:1000]}")
            else:
                raise Exception(f"Subsequent command failed")

    def install_pip(self):
        """
        Apparently we need to install Pip from the outside
        """

        url = "https://bootstrap.pypa.io/get-pip.py"
        self.install_script(url)


@contextmanager
def temp_venv(requirements: Sequence[str]):
    """
    Creates a temporary virtual environment with the required dependencies
    installed that will be destroyed as soon as you get out from the context.
    """

    running = True
    queue = Queue()
    tick_counter = 0

    def tick():
        while running:
            queue.put(Tick())
            sleep(0.1)

    def install():
        try:
            bldr = MakerEnv(requirements=requirements)
            bldr.create(venv_path)
            queue.put(Done(success=True, builder=bldr))
        except Exception:
            queue.put(Done(success=False))
            raise

    def print_tick():
        nonlocal tick_counter
        moons = "🌑🌒🌓🌔🌕🌖🌗🌘"

        stderr.write(
            "".join(
                [
                    "\r",
                    moons[tick_counter % len(moons)],
                    " Loading... ",
                ]
            )
        )

        tick_counter += 1

    with TemporaryDirectory() as venv_path_str:
        venv_path = Path(venv_path_str)

        Thread(target=tick).start()
        Thread(target=install).start()

        while running and (msg := queue.get()):
            if isinstance(msg, Tick):
                print_tick()
            elif isinstance(msg, Done) and msg.success:
                running = False
                builder = msg.builder
                print("\rDependencies installed!")
            elif isinstance(msg, Done) and not msg.success:
                running = False
                print("\rSorry, something went wrong")
                exit(1)

        yield builder


def parse_args(custom_argv: Optional[Sequence[str]] = None) -> Namespace:
    """
    Arguments parsing for main()
    """

    parser = ArgumentParser()
    parser.add_argument("package")
    parser.add_argument("args", nargs="*")
    parser.add_argument("-m", "--module", default=None)

    return parser.parse_args(custom_argv)


def main(custom_argv: Optional[Sequence[str]] = None):
    """
    We're installing the virtualenv and then executing the specified module
    and forwarding the arguments we received
    """

    args = parse_args(custom_argv)

    if not (module := args.module):
        module = args.package

    with temp_venv([args.package]) as builder:
        builder.run_command(["-m", module, *args.args], pipe=False)


if __name__ == "__main__":
    signal(SIGTERM, sigterm_handler)

    try:
        main()
    except KeyboardInterrupt:
        stderr.write("ok, bye\n")
        exit(1)
    except PackageRunnerError as e:
        stderr.write(f"Error: {e}")
        exit(1)
