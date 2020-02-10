# template-project

This is a Template for any Python based project, it contains what Project Thoth and the AI CoE need:

1. GitHub defaults and Templates for issues
2. configuration for Coala and Black (code formating)
3. basic configuration for Zuul
4. configuration for Thoth (stage environment, Red Hat VPN only)
5. if you are writing a Python module, Kebechet could manage releases of your packages for you
6. if credentials are provided, Python module releases could be published to PyPI

Dependencies should be managed using `pipenv` (`Pipfile`, and the `Pipfile.lock` could be created by `thamos advise`), `pip3` and a `requirements.txt` files could be used.
