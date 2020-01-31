import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="ccguard",
    version="0.2.1",
    entry_points={
        "console_scripts": [
            "ccguard=ccguard.ccguard:main",
            "ccguard_log=ccguard.ccguard_log:main",
            "ccguard_sync=ccguard.ccguard_sync:main",
            "ccguard_server=ccguard.ccguard_server:main",
        ]
    },
    author="Ivo Bellin Salarin",
    author_email="me@nilleb.com",
    description="Prevent code coverage regressions",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nilleb/ccguard",
    packages=["ccguard"],
    install_requires=["pycobertura", "gitpython", "redis", "flask"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)",
        "Operating System :: OS Independent",
    ],
)
