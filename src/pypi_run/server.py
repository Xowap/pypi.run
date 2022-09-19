from functools import lru_cache
from pathlib import Path

from blacksheep import Application

app = Application()
app.serve_files(
    Path(__file__).parent.parent.parent / "front/.output/public",
    fallback_document="200.html",
)


@lru_cache
def render_runner(package_name: str, module: str):
    tpl_path = Path(__file__).parent / "templates" / "runner.py"

    argv = [package_name]

    if module:
        argv = ["-m", module, *argv]

    invocation = f"main([{repr(argv)[1:-1]}, *argv[1:]])"

    with open(tpl_path, encoding="utf-8") as tpl:
        return tpl.read().replace("main()", invocation)


@app.route("/{package_name}", methods=["GET"])
def package(package_name: str):
    return render_runner(package_name, "")


@app.route("/{package_name}/{module}", methods=["GET"])
def package(package_name: str, module: str):
    return render_runner(package_name, module)
