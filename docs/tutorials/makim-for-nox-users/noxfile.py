import nox

@nox.session(name="custom-name")
def tests(session: nox.Session) -> None:
    """Run tests with pytest."""
    session.install("pytest")
    session.run("pytest", "--version")

@nox.session
def lint(session: nox.Session):
    """Run linters on the codebase."""
    session.install('flake8')
    # Example of using session.posargs for ad-hoc arguments
    additional_args = session.posargs or []
    session.run('flake8', '--version', *additional_args)
