from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    version='0.0.0',
    name = "yanggui",
    python_requires=">=3.6",
    install_requires=[
        'wxPython',
        'yangson',
        'rstr'
    ],
    packages = ["yanggui"],
    description = "GUI tool for viewing and editing YANG instance data",
    author = "Christian Herber",
    author_email = "christian.hrbr@gmail.com",
    url = "https://github.com/christian-herber/yanggui",
    keywords = ["yang", "gui", "data model", "instance data", "configuration"],
    classifiers = [
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        "Operating System :: OS Independent",
        "Topic :: System :: Systems Administration"],
    long_description = long_description,
    long_description_content_type="text/markdown",
)