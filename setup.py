import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="ccguard",
    version="0.2",
    scripts=[
        "ccguard/ccguard.py",
        "ccguard/ccguard_log.py",
        "ccguard/ccguard_sync.py",
        "ccguard/ccguard_server.py",
    ],
    author="Ivo Bellin Salarin",
    author_email="me@nilleb.com",
    description="Prevent code coverage regressions",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nilleb/ccguard",
    packages=setuptools.find_packages(),
    install_requires=["pycobertura", "gitpython", "redis", "flask"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
