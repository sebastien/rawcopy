#!/usr/bin/env python
# Encoding: utf-8
# See: <http://docs.python.org/distutils/introduction.html>
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

VERSION = eval(filter(lambda _:_.startswith("__version__"),
    file("src/rawcopy.py").readlines())[0].split("=")[1])

setup(
    name             = "rawcopy",
    version          = VERSION,
    description      = "hardlink-aware low-level tree copy",
    author           = "Sébastien Pierre",
    author_email     = "sebastien.pierre@gmail.com",
    url              = "http://github.com/sebastien/rawcopy",
    download_url     = "https://github.com/sebastien/cuisine/tarball/%s" % (VERSION),
    keywords         = ["copy", "rsync", "filesystem",],
    install_requires = ["",],
    package_dir      = {"":"src"},
    py_modules       = ["rawcopycopy"],
    license          = "License :: OSI Approved :: BSD License",
    classifiers      = [
        "Programming Language :: Python",
        "Development Status :: 3 - Alpha",
        "Natural Language :: English",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Topic :: Utilities"
    ],
)
# EOF - vim: ts=4 sw=4 noet
