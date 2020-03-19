"""A setup.py file for requirements.txt in editable mode."""
# type: ignore
from setuptools import setup


setup(
    name="micropipenv-editable-test",
    version="1.2.3",
    description="A simple setup.py for micropipenv's editable install test",
    author="Fridolin Pokorny",
    author_email="fridolin@redhat.com",
    extras_require={
        "foo": ["daiquiri==2.0.0"]
    }
)
