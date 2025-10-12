import nox

nox.options.default_venv_backend = "uv"

PYTHON_VERSIONS = ["3.9", "3.10", "3.11", "3.12", "3.13", "3.14"]


@nox.session(python=PYTHON_VERSIONS)
def tests(session: nox.Session):
    """Run the test suite."""
    session.run("uv", "sync", "--dev", "--locked", external=True)
    session.run("uv", "run", "ruff", "check", ".", external=True)
    session.run("uv", "run", "pytest", "tests/", external=True)
