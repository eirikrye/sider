from setuptools import setup

__version__ = "1.0.0"

PACKAGES = ["sider"]
REQUIRES = ["hiredis", "uvloop"]

setup(
    name="sider",
    version=__version__,
    description="blazing fast asyncio redis client",
    author="Eirik Rye",
    author_email="rye@trojka.no",
    packages=PACKAGES,
    provides=PACKAGES,
    install_requires=REQUIRES,
    requires=REQUIRES,
)
