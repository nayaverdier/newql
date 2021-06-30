from pathlib import Path

from setuptools import setup


ROOT_DIRECTORY = Path(__file__).resolve().parent

description = "A simplified GraphQL-esque library"
readme = (ROOT_DIRECTORY / "README.md").read_text()
changelog = (ROOT_DIRECTORY / "CHANGELOG.md").read_text()
long_description = readme + "\n\n" + changelog

version = (ROOT_DIRECTORY / "newql" / "VERSION").read_text().strip()


DEV_REQUIRES = [
    "black==21.6b0",
    "coverage==5.5",
    "flake8==3.9.2",
    "flake8-bugbear==21.4.3",
    "isort==5.9.1",
    "mypy==0.910",
    "pytest==6.2.4",
    "pytest-cov==2.12.1",
    "twine==3.4.1",
]

setup(
    name="newql",
    version=version,
    description=description,
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
    ],
    author="Naya Verdier",
    url="https://github.com/nayaverdier/newql",
    license="MIT",
    packages=["newql"],
    install_requires=[
        "parsimonious>=0.8",
        "typing_inspect;python_version<='3.7'",
        "varname~=0.6",
    ],
    python_requires=">=3.7",
    extras_require={
        "dev": DEV_REQUIRES,
    },
    include_package_data=True,
)
