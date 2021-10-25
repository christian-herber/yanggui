from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    version='0.1.7',
    name = "yanggui",
    python_requires=">=3.8",
    install_requires=[
        'wxPython>=4.1',
        'yangson>=1.4.9',
        'rstr>=2.2',
        'PyPubSub>=4',
        'importlib_metadata>=4.8.1',
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