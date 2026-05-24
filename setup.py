#!/usr/bin/env python3
"""
Setup script untuk WAMaps - Admin Dashboard Lead Scraper
Packaging dengan staffspy module terikut untuk distribution.
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text(encoding="utf-8")

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = [
        line.strip() for line in requirements_file.readlines()
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="wamaps",
    version="1.0.0",
    author="Your Team",
    description="WAMaps - Admin Dashboard Lead Scraper dengan Google Maps, LinkedIn, & Social Media",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourrepo/wamaps",
    py_modules=["desktop_app"],
    packages=find_packages(include=["staffspy", "staffspy.*"]),
    package_data={
        "staffspy": [
            "linkedin/*.py",
            "solvers/*.py",
            "utils/*.py",
            "__init__.py",
        ],
    },
    include_package_data=True,
    install_requires=requirements,
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "wamaps=desktop_app:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Business",
        "Topic :: Office/Business",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="scraper lead-generation linkedin google-maps social-media",
)
